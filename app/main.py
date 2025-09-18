from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict
import base64
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set. Provide it via environment or .env file.")

client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI(title="AI Reply Suggestion API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeResponse(BaseModel):
    image_content: str
    suggestion: str
    context: Dict[str, Any]


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    instruction: str = Form(..., description="Instruction about what kinds of situation the image is about.(ex. serious and professional, lomantic, etc.)"),
    image: UploadFile = File(..., description="Image file (jpeg/png/webp/etc.)"),
):
    try:
        content = await image.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty image uploaded")

        mime = image.content_type or "image/jpeg"
        b64 = base64.b64encode(content).decode("utf-8")
        data_url = f"data:{mime};base64,{b64}"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an assistant that analyzes a user's chat context from an image "
                    "(e.g., screenshot) and extract the content of the image."
                    "Record every message in the image."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Please analyze the image and extract the content of the image. {instruction}"},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ]

        # OpenAI chat completion (vision + text via data URL)
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
        )

        first_choice = response.choices[0]
        content_text = getattr(getattr(first_choice, "message", None), "content", None)
        if not content_text:
            content_text = str(first_choice)

        suggesstio_messages = [
            {
                "role": "system",
                "content": "You are an assistant that generates a concise, helpful reply suggestion. "
                "Be brief, actionable, and maintain a friendly tone."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Please generate a concise, helpful reply suggestion. {instruction}"},
                    {"type": "text", "text": f"The content of the image is: {content_text}"},
                ],
            },
        ]
        
        suggestion_response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=suggesstio_messages,
        )

        suggestion_choice = suggestion_response.choices[0]
        suggestion_text = getattr(getattr(suggestion_choice, "message", None), "content", None)
        if not suggestion_text:
            suggestion_text = str(suggestion_choice)

        return AnalyzeResponse(
            image_content=content_text,
            suggestion=suggestion_text,
            context={
                "model": OPENAI_MODEL,
                "messages": messages,
                "openai_raw": {
                    "id": getattr(response, "id", None),
                    "created": getattr(response, "created", None),
                    "model": getattr(response, "model", None),
                },
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
