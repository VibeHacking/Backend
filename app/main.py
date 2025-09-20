from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict
import base64
import os
import logging
import sys
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY is not set. Provide it via environment or .env file.")
    raise RuntimeError("OPENAI_API_KEY is not set. Provide it via environment or .env file.")

logger.info(f"Initializing OpenAI client with model: {OPENAI_MODEL}")
logger.info("Configuring client for Lemonade server at localhost:8000")
client = OpenAI(
    base_url="http://localhost:8000/api/v1",
    api_key="not-needed"  # Lemonade server doesn't require real API key
)

app = FastAPI(title="AI Reply Suggestion API", version="1.0.0")
logger.info("FastAPI application initialized")

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
    logger.info(f"Received analyze request - instruction: '{instruction}', image filename: {image.filename}")
    try:
        content = await image.read()
        logger.info(f"Image read successfully - size: {len(content)} bytes, content_type: {image.content_type}")

        if not content:
            logger.error("Empty image uploaded")
            raise HTTPException(status_code=400, detail="Empty image uploaded")

        mime = image.content_type or "image/jpeg"
        b64 = base64.b64encode(content).decode("utf-8")
        data_url = f"data:{mime};base64,{b64}"
        logger.info(f"Image encoded to base64 - mime: {mime}, base64 length: {len(b64)}")

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
        logger.info("Starting first OpenAI API call for image content extraction")
        logger.debug(f"Messages for content extraction: {len(messages)} messages")

        try:
            response = client.chat.completions.create(
                model="Gemma-3-4b-it-GGUF",  # Using available Lemonade model
                messages=messages,
            )
            logger.info("First OpenAI API call completed successfully")
        except Exception as openai_error:
            logger.error(f"OpenAI API error during content extraction: {type(openai_error).__name__}: {str(openai_error)}")
            raise HTTPException(status_code=500, detail=f"OpenAI API error during content extraction: {str(openai_error)}")

        first_choice = response.choices[0]
        content_text = getattr(getattr(first_choice, "message", None), "content", None)
        if not content_text:
            logger.warning("No content found in first choice, using string representation")
            content_text = str(first_choice)

        logger.info(f"Extracted image content - length: {len(content_text)} characters")
        logger.debug(f"Image content preview: {content_text[:200]}...")

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

        logger.info("Starting second OpenAI API call for suggestion generation")
        logger.debug(f"Messages for suggestion: {len(suggesstio_messages)} messages")

        try:
            suggestion_response = client.chat.completions.create(
                model="Gemma-3-4b-it-GGUF",  # Using available Lemonade model
                messages=suggesstio_messages,
            )
            logger.info("Second OpenAI API call completed successfully")
        except Exception as openai_error:
            logger.error(f"OpenAI API error during suggestion generation: {type(openai_error).__name__}: {str(openai_error)}")
            raise HTTPException(status_code=500, detail=f"OpenAI API error during suggestion generation: {str(openai_error)}")

        suggestion_choice = suggestion_response.choices[0]
        suggestion_text = getattr(getattr(suggestion_choice, "message", None), "content", None)
        if not suggestion_text:
            logger.warning("No suggestion found in choice, using string representation")
            suggestion_text = str(suggestion_choice)

        logger.info(f"Generated suggestion - length: {len(suggestion_text)} characters")
        logger.debug(f"Suggestion preview: {suggestion_text[:100]}...")

        logger.info("Preparing final response")
        return AnalyzeResponse(
            image_content=content_text,
            suggestion=suggestion_text,
            context={
                "model": "Gemma-3-4b-it-GGUF",
                "messages": messages,
                "openai_raw": {
                    "id": getattr(response, "id", None),
                    "created": getattr(response, "created", None),
                    "model": getattr(response, "model", None),
                },
            },
        )
    except HTTPException as he:
        logger.error(f"HTTP Exception occurred: {he.status_code} - {he.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in analyze endpoint: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
