from fastapi import FastAPI, HTTPException, APIRouter
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
    "https://spam-check-eta.vercel.app/",
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

# ---------- Safe Browsing ----------

SAFE_BROWSING_KEY = os.getenv("GOOGLE_SAFE_BROWSING_KEY")
SAFE_BROWSING_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"

# ---------- Schemas ----------

class ScanRequest(BaseModel):
    content: Optional[str] = None
    image: Optional[str] = None  # Base64
    type: str


# IMPORTANT: this now matches useScanner.sendFeedback
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


async def _feedback_risk_boost(urls: List[str]) -> tuple[int, list[str]]:
    if not urls:
        return 0, []

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
        return 0, []

    extra = 0
    extra_flags: list[str] = []

    for fb in feedbacks:
        raw = fb.get("raw_content", "") or ""
        key = normalize_url_for_lookup(raw)
        if key not in url_keys:
            continue

        label = fb.get("user_label")
        if label == "phishing":
            extra = max(extra, 5)
            extra_flags.append("USER_REPORTED_PHISHING")
        elif label == "suspicious":
            extra = max(extra, 2)
            extra_flags.append("USER_REPORTED_SUSPICIOUS")
        elif label == "safe":
            extra_flags.append("USER_REPORTED_SAFE")

    return extra, list(set(extra_flags))

# ---------- Scoring ----------

async def text_spam_with_safe_browsing(text: str) -> dict:
    urls = extract_urls(text)

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

        ml_scores = [predict_url_risk_ml(u) for u in urls]
        ml_max = max(ml_scores) if ml_scores else 0.0

        if ml_max > 0.8:
            score = max(score, 8)
            flags.append("ML_HIGH_RISK")
        elif ml_max > 0.5:
            score = max(score, 5)
            flags.append("ML_MEDIUM_RISK")

        fb_extra, fb_flags = await _feedback_risk_boost(urls)
        score += fb_extra
        flags.extend(fb_flags)

        # NEW: brand / pattern rules for PH scams
        text_low = (text or "").lower()

        # BDO account security scare (like your example)
        if "bdo" in text_low and "account" in text_low and any(
            p in text_low for p in ["unusual activity", "verify your details", "verify your account"]
        ):
            score = max(score, 8)  # force High
            flags.append("BRAND_IMPERSONATION")
            flags.append("ACCOUNT_SECURITY_SCARE")

        # You can add more brand rules similarly, e.g. GCash, BPI, etc.
        # if "gcash" in text_low and "account" in text_low and "verify" in text_low:
        #     score = max(score, 8)
        #     flags.append("EWALLET_IMPERSONATION")
        #     flags.append("ACCOUNT_SECURITY_SCARE")

        score = max(0, min(score, 10))

    if any_bad:
        summary = "High risk: known malicious URL"
    elif score >= 8:
        summary = "High risk: likely malicious"
    elif score >= 4:
        summary = "Medium risk: treat with caution"
    else:
        summary = "No known issues detected"

    return {"score": score, "summary": summary, "flags": list(set(flags))}

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

    # Final fallback: model unavailable, but don't 500 the user
    return {
        "score": 0,
        "summary": "Image analysis is temporarily unavailable; no known issues detected.",
        "flags": ["MODEL_UNAVAILABLE"],
    }


async def _feedback_strongest_label(raw_content: str) -> str | None:
    """
    Look up feedback rows for this raw_content and return the strongest label:
    'phishing' > 'suspicious' > 'safe'. None if no feedback.
    """
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
    """
    Simple heuristic risk scoring for SMS without URLs.
    Score: 0–10, higher = more likely scam/smishing.
    """
    t = (text or "").lower()
    score = 0
    flags: list[str] = []

    # 1) Urgency / pressure
    if any(p in t for p in ["urgent", "immediately", "right away", "act now", "asap", "within 24 hours"]):
        score += 2
        flags.append("URGENT_LANGUAGE")

    # 2) Money / prizes / rewards
    if any(p in t for p in ["you have won", "congratulations", "winner", "jackpot", "lottery", "prize"]):
        score += 3
        flags.append("FAKE_GIVEAWAY")

    if any(p in t for p in ["claim your reward", "claim your prize", "cash prize"]):
        score += 2
        flags.append("REWARD_OFFER")

    # 3) Bank / account / OTP / verification
    if any(p in t for p in ["otp", "one time password", "verification code", "6-digit code", "6 digit code"]):
        score += 2
        flags.append("CODE_REQUEST")

    if any(p in t for p in ["account", "bank", "card", "transaction", "billing"]):
        score += 2
        flags.append("ACCOUNT_MENTION")

    if any(p in t for p in ["suspended", "blocked", "locked", "temporarily disabled"]):
        score += 2
        flags.append("ACCOUNT_THREAT")

    # 4) Delivery / parcel scams
    if any(p in t for p in ["package", "parcel", "delivery", "shipment"]):
        score += 2
        flags.append("DELIVERY_MENTION")

    if any(p in t for p in ["unpaid fee", "customs fee", "delivery fee"]):
        score += 2
        flags.append("FEE_REQUEST")

    # 5) Generic greeting / impersonation
    if any(p in t for p in ["dear customer", "valued customer", "dear user"]):
        score += 1
        flags.append("GENERIC_GREETING")

    # 6) Social engineering patterns
    if any(p in t for p in ["wrong number", "sorry wrong number"]):
        score += 1
        flags.append("WRONG_NUMBER_BAIT")

    if any(p in t for p in ["lost my phone", "naaksidente ako", "emergency", "hospital"]):
        score += 2
        flags.append("EMERGENCY_STORY")

    # 7) Callback / contact tricks
    if any(p in t for p in ["call this number", "contact this number", "text back this number"]):
        score += 1
        flags.append("CALLBACK_REQUEST")

    # Normalize
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

@app.post("/api/verify")
async def verify(request: ScanRequest):
    if not request.content and not request.image:
        raise HTTPException(status_code=400, detail="No content or image provided.")

    input_type = request.type.lower()

    if input_type in ("url", "website"):
        text = request.content or ""
        result = await text_spam_with_safe_browsing(text)
    else:
        result = await get_ai_analysis(request.content, request.image)

    if result is None:
        result = {
            "score": 0,
            "summary": "Analysis is temporarily unavailable; no known issues detected.",
            "flags": ["MODEL_UNAVAILABLE"],
        }

    # NEW: stable raw_key for scans and feedback
    if request.content:
        raw_key = request.content
    elif request.image:
        raw_key = image_hash(request.image)
    else:
        raw_key = ""

    # override based on feedback for this key
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

    # use raw_key instead of request.content
    try:
        supabase.table("scans").insert({
            "input_type": input_type,
            "raw_content": raw_key,
            "score": result.get("score", 0),
            "flags": result.get("flags", []),
            "summary": result.get("summary", ""),
        }).execute()
    except Exception as e:
        print(f"DEBUG: Failed to write scan to Supabase: {e}")

    # optional JSONL log
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

    # include raw_key in response so frontend can reuse it
    response_payload = dict(result)
    response_payload["raw_key"] = raw_key
    return response_payload

@router.post("/api/feedback")
async def submit_feedback(payload: FeedbackIn):
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


@app.get("/api/metrics/summary")
async def metrics_summary():
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

    print("DEBUG daily_counts:", daily_counts)


    return {
        "totals": {
            "scans_24h": scans_24h,
            "scans_7d": scans_7d,
            "feedback_7d": feedback_7d,
        },
        "risk_distribution": risk_distribution,
        "sb_hit_rate": sb_hit_rate,
        "daily_scans": daily_scans,
    }

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
