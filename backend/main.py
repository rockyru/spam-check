import os
import io
import re
import json
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import google.generativeai as genai

load_dotenv()

# Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3-flash-preview')

app = FastAPI()

# Enable CORS so your React app can talk to this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/analyze")
async def analyze_content(
    input_type: str = Form(...), 
    text_content: str = Form(None), 
    file: UploadFile = File(None)
):
    # 1. Prepare the Professional Cybersecurity Prompt
    prompt = """
    Act as a cybersecurity expert. Analyze the provided content (text, URL, or image) for signs of:
    - Phishing or credential theft
    - SMS spam (Smishing)
    - Suspicious URLs (look-alike domains, typosquatting)
    - Social engineering tactics (fake urgency, threats)

    You must respond ONLY with a valid JSON object in this exact format:
    {"score": <int 0-10>, "flags": ["list", "of", "strings"], "summary": "brief explanation"}
    """

    try:
        # 2. Handle Image/Screenshot Input
        if input_type == "image" and file:
            img_bytes = await file.read()
            img = Image.open(io.BytesIO(img_bytes))
            # Gemini 1.5 Flash handles images directly as a list element
            response = model.generate_content([prompt, img])
        
        # 3. Handle Text/URL Input
        else:
            full_input = f"{prompt}\n\nCONTENT TO ANALYZE: {text_content}"
            response = model.generate_content(full_input)

        raw_text = response.text

        # 4. Extract and Clean JSON
        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        
        return {
            "score": 0, 
            "flags": ["Formatting Error"], 
            "summary": "The AI didn't return a clear JSON response. Try again."
        }

    except Exception as e:
        return {
            "score": 0, 
            "flags": [f"System Error: {str(e)}"], 
            "summary": "The server encountered an error processing your request."
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)