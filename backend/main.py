from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import io
import json
import base64
import re
from typing import Optional, List
from urllib.parse import urlparse

import httpx
import PIL.Image
import google.generativeai as genai
from dotenv import load_dotenv
from google.generativeai.types import HarmCategory, HarmBlockThreshold

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Google Gemini (for image+text)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

MODELS = ["models/gemini-1.5-flash", "models/gemini-1.5-pro"]

# Google Safe Browsing (for URL checks)
SAFE_BROWSING_KEY = os.getenv("GOOGLE_SAFE_BROWSING_KEY")
SAFE_BROWSING_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"


class ScanRequest(BaseModel):
    content: Optional[str] = None
    image: Optional[str] = None  # Base64 string
    type: str


def extract_urls(text: str) -> List[str]:
    # Simple URL extraction: http/https plus bare domains.
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


async def check_safe_browsing(urls: list[str]) -> dict:
    if not SAFE_BROWSING_KEY:
        raise RuntimeError("GOOGLE_SAFE_BROWSING_KEY not set")

    if not urls:
        return {}

    payload = {
        "client": {
            "clientId": "spam-checker-demo",
            "clientVersion": "1.0.0",
        },
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

async def text_spam_with_safe_browsing(text: str) -> dict:
    urls = extract_urls(text)
    if not urls:
        return {
            "score": 0,
            "summary": "Not spam (no URL detected)",
            "flags": [],
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
        # Heuristic scoring when Safe Browsing has no match
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

                randomish = [s for s in segments if len(s) >= 5 and re.search(r"\d", s)]
                if randomish:
                    score += 1
                    flags.append("RANDOM_SEGMENT")
            except Exception:
                continue

        score = max(0, min(score, 10))

    # Clear, human summary
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
    }


async def get_ai_analysis(text_content: str = None, base64_image: str = None):
    """
    Analyze content for scams.
    - If only text: use Safe Browsing on URLs in the text.
    - If image is present: use Gemini (image + optional text) if GOOGLE_API_KEY is set.
    """

    # Text-only path: Safe Browsing
    if text_content and not base64_image:
        return await text_spam_with_safe_browsing(text_content)

    # If no image or no Gemini key, still run Safe Browsing on any text
    if not base64_image or not GOOGLE_API_KEY:
        if text_content:
            return await text_spam_with_safe_browsing(text_content)
        return None

    # Image + optional text → Gemini
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

    # If Gemini fails, fall back to Safe Browsing on text if present
    if text_content:
        return await text_spam_with_safe_browsing(text_content)

    return None


@app.post("/api/verify")
async def verify(request: ScanRequest):
    if not request.content and not request.image:
        raise HTTPException(status_code=400, detail="No content or image provided.")

    result = await get_ai_analysis(request.content, request.image)

    if not result:
        raise HTTPException(status_code=500, detail="All models are currently busy.")

    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
