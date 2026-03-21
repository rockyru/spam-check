from fastapi import FastAPI, HTTPException, APIRouter, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import io
import json
import base64
import re
from typing import Optional, List
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import PIL.Image
import google.generativeai as genai
from dotenv import load_dotenv
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from supabase import create_client, Client
import hashlib

from rate_limit import limit_scans, limit_metrics, limit_feedback
from metrics_cache import metrics_cache

load_dotenv()

BASE_DIR = Path(__file__).parent
SCAN_EVENTS_PATH = BASE_DIR / "scan_events.jsonl"
FEEDBACK_PATH = BASE_DIR / "feedback_log.jsonl"

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------- FastAPI app & router ----------

app = FastAPI()
router = APIRouter()

origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "https://spam-check-eta.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Google Gemini ----------

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

MODELS = ["models/gemini-1.5-flash", "models/gemini-1.5-pro"]

# ---------- Content filtering ----------

SLUR_PATTERNS = [
    r"\bnigga\b",
    r"\bnigger\b",
]

LOW_VALUE_WORDS = {"test", "testing", "asd", "qwe", "fgfg"}

MIN_CONTENT_LEN = 25  # below this is considered useless noise


def is_toxic(text: str) -> bool:
    if not text:
        return False
    normalized = text.lower()
    return any(re.search(pat, normalized) for pat in SLUR_PATTERNS)


def is_low_value(text: str) -> bool:
    """
    Filters out obvious junk like 'test', super-short noise, and slurs.
    """
    if not text:
        return True
    t = text.strip().lower()
    if len(t) < MIN_CONTENT_LEN:
        return True
    if t in LOW_VALUE_WORDS:
        return True
    if is_toxic(t):
        return True
    return False

# ---------- Safe Browsing ----------

SAFE_BROWSING_KEY = os.getenv("GOOGLE_SAFE_BROWSING_KEY")
SAFE_BROWSING_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"

# ---------- Schemas ----------

class ScanRequest(BaseModel):
    content: Optional[str] = None
    image: Optional[str] = None  # Base64
    type: str


class FeedbackIn(BaseModel):
    input_type: str
    raw_content: str
    predicted_score: int
    predicted_flags: list[str] = []
    user_label: str  # "safe" | "phishing" | "suspicious"

# ---------- Helpers ----------

def extract_urls(text: str) -> List[str]:
    pattern = re.compile(r"(https?://[^\s]+|[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}[^\s]*)")
    urls = pattern.findall(text or "")
    clean: List[str] = []
    for u in urls:
        u = u.strip(".,);")
        if not u.startswith("http://") and not u.startswith("https://"):
            u = "http://" + u
        if u not in clean:
            clean.append(u)
    return clean


def normalize_url_for_lookup(url: str) -> str:
    try:
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
        p = urlparse(url.strip())
        return (p.netloc + p.path).lower()
    except Exception:
        return url.strip().lower()

async def check_safe_browsing(urls: List[str]) -> dict:
    if not SAFE_BROWSING_KEY:
        raise RuntimeError("GOOGLE_SAFE_BROWSING_KEY not set")

    if not urls:
        return {}

    payload = {
        "client": {"clientId": "spam-checker-demo", "clientVersion": "1.0.0"},
        "threatInfo": {
            "threatTypes": [
                "MALWARE",
                "SOCIAL_ENGINEERING",
                "UNWANTED_SOFTWARE",
                "POTENTIALLY_HARMFUL_APPLICATION",
            ],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": u} for u in urls],
        },
    }

    params = {"key": SAFE_BROWSING_KEY}

    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.post(SAFE_BROWSING_URL, params=params, json=payload)
        resp.raise_for_status()
        data = resp.json()

    matches = data.get("matches", [])
    unsafe_norm = set()
    for m in matches:
        t = m.get("threat", {})
        mu = t.get("url")
        if not mu:
            continue
        p = urlparse(mu)
        unsafe_norm.add(p.netloc + p.path)

    result = {}
    for u in urls:
        p = urlparse(u)
        key = p.netloc + p.path
        result[u] = key in unsafe_norm

    return result

def predict_url_risk_ml(url: str) -> float:
    return 0.0

def _load_jsonl(path: Path):
    if not path.exists():
        return []
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                continue
    return items

async def _feedback_risk_boost(urls: List[str]) -> tuple[int, int, list[str]]:
    if not urls:
        return 0, 0, []

    url_keys = {normalize_url_for_lookup(u) for u in urls}

    try:
        fb_resp = (
            supabase.table("feedback")
            .select("raw_content,user_label")
            .execute()
        )
        feedbacks = fb_resp.data or []
    except Exception as e:
        print(f"DEBUG: Failed to load feedback from Supabase: {e}")
        return 0, 0, []

    extra = 0
    community_extra = 0
    extra_flags: list[str] = []

    for fb in feedbacks:
        raw = fb.get("raw_content", "") or ""
        key = normalize_url_for_lookup(raw)
        if key not in url_keys:
            continue

        label = (fb.get("user_label") or "").lower()
        if label == "phishing":
            extra = min(6, extra + 2)
            community_extra = min(6, community_extra + 2)
            extra_flags.append("USER_REPORTED_PHISHING")
        elif label == "suspicious":
            extra = min(3, extra + 1)
            community_extra = min(3, community_extra + 1)
            extra_flags.append("USER_REPORTED_SUSPICIOUS")
        elif label == "safe":
            extra = max(-3, extra - 1)
            community_extra = max(-3, community_extra - 1)
            extra_flags.append("USER_REPORTED_SAFE")

    return extra, community_extra, list(set(extra_flags))

# ---------- Scoring ----------

async def text_spam_with_safe_browsing(text: str) -> dict:
    urls = extract_urls(text)

    # default when no URLs: no community score
    community_extra = 0

    if not urls:
        score, flags = sms_text_risk(text)
        if score >= 8:
            summary = "High risk: message looks like a scam or phishing SMS."
        elif score >= 4:
            summary = "Medium risk: message has several scam-like patterns."
        elif score > 0:
            summary = "Low risk: some suspicious patterns detected."
        else:
            summary = "No scam patterns or links detected."

        return {
            "score": score,
            "summary": summary,
            "flags": flags,
            "community_score": 0,
        }

    sb_result = await check_safe_browsing(urls)
    any_bad = any(sb_result.values())

    score = 0
    flags: List[str] = []

    if urls:
        flags.append("HAS_LINK")

    if any_bad:
        score = 10
        flags.append("SAFE_BROWSING_HIT")
    else:
        suspicious_tlds = [
            ".zip",
            ".top",
            ".xyz",
            ".click",
            ".link",
            ".loan",
            ".download",
            ".info",
        ]
        suspicious_path_fragments = [
            "/v1/",
            "/js/",
            "/php/",
            ".php",
            "/login",
            "/verify",
            "/secure",
            "/update",
            "/webscr",
            "/cgi-bin",
        ]

        # 1) community boost from feedback (once)
        fb_extra, community_extra, fb_flags = await _feedback_risk_boost(urls)
        score += fb_extra
        flags.extend(fb_flags)

        # 2) heuristic URL rules
        for raw in urls:
            try:
                p = urlparse(raw)
                host = p.netloc.lower()
                path = (p.path or "").lower()

                if any(host.endswith(tld) for tld in suspicious_tlds):
                    score += 2
                    flags.append("SUSPICIOUS_TLD")

                if any(frag in path for frag in suspicious_path_fragments):
                    score += 3
                    flags.append("SUSPICIOUS_PATH")

                segments = [s for s in path.split("/") if s]
                if len(segments) >= 4:
                    score += 1
                    flags.append("DEEP_PATH")

                randomish = [
                    s for s in segments if len(s) >= 5 and re.search(r"\d", s)
                ]
                if randomish:
                    score += 1
                    flags.append("RANDOM_SEGMENT")
            except Exception:
                continue

        # 3) ML placeholder
        ml_scores = [predict_url_risk_ml(u) for u in urls]
        ml_max = max(ml_scores) if ml_scores else 0.0

        if ml_max > 0.8:
            score = max(score, 8)
            flags.append("ML_HIGH_RISK")
        elif ml_max > 0.5:
            score = max(score, 5)
            flags.append("ML_MEDIUM_RISK")

        # brand / pattern rules
        text_low = (text or "").lower()

        if "bdo" in text_low and "account" in text_low and any(
            p in text_low for p in ["unusual activity", "verify your details", "verify your account"]
        ):
            score = max(score, 8)
            flags.append("BRAND_IMPERSONATION")
            flags.append("ACCOUNT_SECURITY_SCARE")

        score = max(0, min(score, 10))

    if any_bad:
        summary = "High risk: known malicious URL"
    elif score >= 8:
        summary = "High risk: likely malicious"
    elif score >= 4:
        summary = "Medium risk: treat with caution"
    else:
        summary = "No known issues detected"

    return {
        "score": score,
        "summary": summary,
        "flags": list(set(flags)),
        "community_score": community_extra,
    }

# ---------- AI analysis ----------

async def get_ai_analysis(text_content: str = None, base64_image: str = None):
    if text_content and not base64_image:
        return await text_spam_with_safe_browsing(text_content)

    if not base64_image or not GOOGLE_API_KEY:
        if text_content:
            return await text_spam_with_safe_browsing(text_content)
        return None

    prompt = """
    Analyze the following for scam, phishing, or spam intent.
    If an image is provided, extract the text and analyze the visual context.
    Return ONLY a valid JSON object: 
    { "score": 0-10, "summary": "A clear 1-sentence verdict", "flags": ["URGENCY", "SUSPICIOUS_LINK", "FAKE_GIVEAWAY"] }
    """

    inputs = [prompt]

    if text_content and text_content.strip():
        inputs.append(f"User Text: {text_content}")

    try:
        if "," in base64_image:
            base64_image = base64_image.split(",")[1]

        image_bytes = base64.b64decode(base64_image)
        img = PIL.Image.open(io.BytesIO(image_bytes))
        inputs.append(img)
    except Exception as e:
        print(f"DEBUG: Image processing failed: {e}")
        if text_content:
            return await text_spam_with_safe_browsing(text_content)
        return None

    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    for model_name in MODELS:
        try:
            print(f"DEBUG: Attempting analysis with {model_name}...")
            model = genai.GenerativeModel(model_name)

            response = await model.generate_content_async(
                inputs,
                safety_settings=safety_settings,
            )

            if not response.text:
                continue

            clean_json = (
                response.text.strip()
                .replace("```json", "")
                .replace("```", "")
            )
            return json.loads(clean_json)

        except Exception as e:
            print(f"DEBUG: Error with {model_name}: {e}")
            continue

    if text_content:
        return await text_spam_with_safe_browsing(text_content)

    return {
        "score": 0,
        "summary": "Image analysis is temporarily unavailable; no known issues detected.",
        "flags": ["MODEL_UNAVAILABLE"],
    }

async def _feedback_strongest_label(raw_content: str) -> str | None:
    if not raw_content:
        return None

    try:
        resp = (
            supabase.table("feedback")
            .select("user_label")
            .eq("raw_content", raw_content)
            .execute()
        )
        feedbacks = resp.data or []
    except Exception as e:
        print(f"DEBUG: Failed to load feedback for override: {e}")
        return None

    strongest = None
    for fb in feedbacks:
        label = (fb.get("user_label") or "").lower()
        if label not in ("phishing", "suspicious", "safe"):
            continue
        if strongest is None:
            strongest = label
        elif strongest == "suspicious" and label == "phishing":
            strongest = "phishing"
        elif strongest == "safe" and label in ("suspicious", "phishing"):
            strongest = label

    return strongest

def sms_text_risk(text: str) -> tuple[int, list[str]]:
    t = (text or "").lower()
    score = 0
    flags: list[str] = []

    if any(p in t for p in ["urgent", "immediately", "right away", "act now", "asap", "within 24 hours"]):
        score += 2
        flags.append("URGENT_LANGUAGE")

    if any(p in t for p in ["you have won", "congratulations", "winner", "jackpot", "lottery", "prize"]):
        score += 3
        flags.append("FAKE_GIVEAWAY")

    if any(p in t for p in ["claim your reward", "claim your prize", "cash prize"]):
        score += 2
        flags.append("REWARD_OFFER")

    if any(p in t for p in ["otp", "one time password", "verification code", "6-digit code", "6 digit code"]):
        score += 2
        flags.append("CODE_REQUEST")

    if any(p in t for p in ["account", "bank", "card", "transaction", "billing"]):
        score += 2
        flags.append("ACCOUNT_MENTION")

    if any(p in t for p in ["suspended", "blocked", "locked", "temporarily disabled"]):
        score += 2
        flags.append("ACCOUNT_THREAT")

    if any(p in t for p in ["package", "parcel", "delivery", "shipment"]):
        score += 2
        flags.append("DELIVERY_MENTION")

    if any(p in t for p in ["unpaid fee", "customs fee", "delivery fee"]):
        score += 2
        flags.append("FEE_REQUEST")

    if any(p in t for p in ["dear customer", "valued customer", "dear user"]):
        score += 1
        flags.append("GENERIC_GREETING")

    if any(p in t for p in ["wrong number", "sorry wrong number"]):
        score += 1
        flags.append("WRONG_NUMBER_BAIT")

    if any(p in t for p in ["lost my phone", "naaksidente ako", "emergency", "hospital"]):
        score += 2
        flags.append("EMERGENCY_STORY")

    if any(p in t for p in ["call this number", "contact this number", "text back this number"]):
        score += 1
        flags.append("CALLBACK_REQUEST")

    score = max(0, min(score, 10))
    flags = list(set(flags))
    return score, flags

def image_hash(base64_image: str) -> str:
    try:
        if "," in base64_image:
            base64_image = base64_image.split(",")[1]
        data = base64.b64decode(base64_image)
        return hashlib.sha256(data).hexdigest()
    except Exception as e:
        print(f"DEBUG: image_hash failed: {e}")
        return ""

# ---------- Routes ----------

@app.post("/api/verify", dependencies=[Depends(limit_scans)])
async def verify(request: ScanRequest, http_req: Request):
    if not request.content and not request.image:
        raise HTTPException(status_code=400, detail="No content or image provided.")

    content = (request.content or "").strip()

    # Block obviously junk / abusive text so it doesn't hit scans
    if content and is_low_value(content):
        ip = http_req.client.host or "unknown"
        print(f"IGNORED_SCAN ip={ip} content={repr(content)}")
        return {
            "score": 0,
            "summary": "This content can't be analyzed.",
            "flags": ["BLOCKED_CONTENT"],
            "raw_key": "",
        }

    input_type = request.type.lower()

    if input_type in ("url", "website"):
        result = await text_spam_with_safe_browsing(content)
    else:
        result = await get_ai_analysis(content, request.image)

    if result is None:
        result = {
            "score": 0,
            "summary": "Analysis is temporarily unavailable; no known issues detected.",
            "flags": ["MODEL_UNAVAILABLE"],
        }

    # stable raw_key
    if content:
        raw_key = content
    elif request.image:
        raw_key = image_hash(request.image)
    else:
        raw_key = ""

    strongest = await _feedback_strongest_label(raw_key)
    if strongest == "phishing":
        result["score"] = max(result.get("score", 0), 9)
        result["summary"] = "High risk: users previously reported this as phishing."
        flags = set(result.get("flags") or [])
        flags.add("USER_REPORTED_PHISHING")
        result["flags"] = list(flags)
    elif strongest == "suspicious":
        if result.get("score", 0) < 7:
            result["score"] = 7
        result["summary"] = "Elevated risk: users previously reported this as suspicious."
        flags = set(result.get("flags") or [])
        flags.add("USER_REPORTED_SUSPICIOUS")
        result["flags"] = list(flags)

    if "community_score" not in result:
        result["community_score"] = 0

    if raw_key:
        try:
            supabase.table("scans").insert({
                "input_type": input_type,
                "raw_content": raw_key,
                "score": result.get("score", 0),
                "community_score": result.get("community_score", 0),
                "flags": result.get("flags", []),
                "summary": result.get("summary", ""),
            }).execute()
        except Exception as e:
            print(f"DEBUG: Failed to write scan to Supabase: {e}")

        event = {
            "ts": datetime.utcnow().isoformat(),
            "input_type": input_type,
            "raw_content": raw_key,
            "score": result.get("score", 0),
            "flags": result.get("flags", []),
            "summary": result.get("summary", ""),
        }
        try:
            with open(SCAN_EVENTS_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            print(f"DEBUG: failed to write scan event: {e}")

    response_payload = dict(result)
    response_payload["raw_key"] = raw_key
    return response_payload

@router.post("/api/feedback", dependencies=[Depends(limit_feedback)])
async def submit_feedback(payload: FeedbackIn, request: Request):
    content = (payload.raw_content or "").strip()
    print("DEBUG FEEDBACK raw_content:", repr(content))

    if is_low_value(content):
        ip = request.client.host or "unknown"
        print(f"IGNORED_FEEDBACK ip={ip} content={repr(content)}")
        return {"status": "ignored"}

    resp = (
        supabase.table("feedback")
        .insert({
            "input_type": payload.input_type,
            "raw_content": payload.raw_content,
            "predicted_score": payload.predicted_score,
            "predicted_flags": payload.predicted_flags,
            "user_label": payload.user_label,
        })
        .execute()
    )

    print("DEBUG feedback insert:", resp)
    return {"ok": True}

@app.get("/api/metrics/summary", dependencies=[Depends(limit_metrics)])
async def metrics_summary():
    cached = metrics_cache.get()

    if cached is not None:
        return cached

    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    try:
        scans_resp = (
            supabase.table("scans")
            .select("*")
            .gte("created_at", week_ago.isoformat())
            .execute()
        )
        scans = scans_resp.data or []
    except Exception as e:
        print(f"DEBUG: Failed to load scans from Supabase: {e}")
        scans = []

    try:
        fb_resp = (
            supabase.table("feedback")
            .select("created_at")
            .gte("created_at", week_ago.isoformat())
            .execute()
        )
        feedbacks = fb_resp.data or []
    except Exception as e:
        print(f"DEBUG: Failed to load feedback from Supabase: {e}")
        feedbacks = []

    scans_24h = 0
    scans_7d = len(scans)

    risk_safe = 0
    risk_med = 0
    risk_high = 0

    sb_hits = 0
    total_scans_for_sb = 0

    daily_counts = {}
    for i in range(7):
        day = (now - timedelta(days=i)).date()
        daily_counts[day.isoformat()] = 0

    for ev in scans:
        try:
            created = ev.get("created_at")
            if not created:
                continue
            ts = datetime.fromisoformat(created)
        except Exception:
            continue

        score = ev.get("score", 0)
        flags = ev.get("flags", []) or []

        if ts >= day_ago:
            scans_24h += 1

        if score <= 3:
            risk_safe += 1
        elif score <= 7:
            risk_med += 1
        else:
            risk_high += 1

        if "HAS_LINK" in flags:
            total_scans_for_sb += 1
            if "SAFE_BROWSING_HIT" in flags:
                sb_hits += 1

        day_key = ts.date().isoformat()
        if day_key in daily_counts:
            daily_counts[day_key] += 1

    daily_scans = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).date()
        key = day.isoformat()
        label = day.strftime("%a")
        daily_scans.append({"date": label, "count": daily_counts.get(key, 0)})

    total_risks = risk_safe + risk_med + risk_high or 1
    risk_distribution = {
        "safe": int(risk_safe / total_risks * 100),
        "medium": int(risk_med / total_risks * 100),
        "high": int(risk_high / total_risks * 100),
    }

    sb_hit_rate = (sb_hits / total_scans_for_sb) if total_scans_for_sb > 0 else 0.0
    feedback_7d = len(feedbacks)

    summary = {
        "totals": {
            "scans_24h": scans_24h,
            "scans_7d": scans_7d,
            "feedback_7d": feedback_7d,
        },
        "risk_distribution": risk_distribution,
        "sb_hit_rate": sb_hit_rate,
        "daily_scans": daily_scans,
    }

    metrics_cache.set(summary)
    return summary

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
