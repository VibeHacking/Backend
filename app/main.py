import base64
import json
import logging
import site
import sys
from typing import Any

import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel

from app.config import settings
from app.prompts import SYSTEM_PROMPT

sys.path.append(site.getusersitepackages())

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

OPENAI_API_KEY = settings.openai_api_key
OPENAI_MODEL = settings.openai_model
OCR_SERVER_URL = settings.ocr_server_url

# API key not required for local servers

logger.info(f"Initializing OpenAI client with model: {settings.openai_model}")
logger.info("Configuring client for Lemonade server at localhost:8060")
client = OpenAI(
    base_url="http://localhost:8060/api/v1",
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
    context: dict[str, Any]


class AnalyzeOCRResponse(BaseModel):
    extracted_text: str
    analysis: str
    context: dict[str, Any]


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
        logger.info(f"Image encoded to base64 - mime: {mime}, base64 length: {len(b64)}")

        # First, use OCR server to extract text from the image
        logger.info("Sending image to OCR server for text extraction")
        ocr_result = {}
        ocr_content = ""
        try:
            # OCR server expects 'file' parameter, not 'image'
            ocr_response = requests.post(
                f"{settings.ocr_server_url}/ocr",
                files={"file": (image.filename, content, mime)},
                timeout=30
            )
            if ocr_response.status_code == 200:
                ocr_result = ocr_response.json()
                # Extract the full_text field from OCR response
                if "full_text" in ocr_result:
                    ocr_content = ocr_result["full_text"]
                    logger.info(f"OCR extraction successful - extracted text: {len(ocr_content)} characters")
                else:
                    ocr_content = json.dumps(ocr_result) if isinstance(ocr_result, dict) else str(ocr_result)
                    logger.info(f"OCR extraction successful - received JSON data: {len(ocr_content)} characters")
            else:
                logger.warning(f"OCR server returned status {ocr_response.status_code}: {ocr_response.text}")
                ocr_content = f"OCR server error: status {ocr_response.status_code}"
        except Exception as ocr_error:
            logger.warning(f"OCR server error: {str(ocr_error)}")
            ocr_content = f"OCR extraction failed: {str(ocr_error)}"


        # Prepare text-only messages for gpt-oss-20b-GGUF (no image support)
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": f"Analyze and extract content from this OCR data. Context: {instruction}\n\nOCR Data:\n{ocr_content}"
            },
        ]

        # Use gpt-oss-20b-GGUF for content analysis (text-only)
        logger.info("Starting first API call for OCR content analysis using gpt-oss-20b-GGUF")
        logger.debug(f"Messages for content extraction: {len(messages)} messages")

        try:
            response = client.chat.completions.create(
                model="gpt-oss-20b-GGUF",  # Using gpt-oss-20b-GGUF model
                messages=messages,
            )
            logger.info("First API call completed successfully")
        except Exception as openai_error:
            logger.error(f"API error during content analysis: {type(openai_error).__name__}: {str(openai_error)}")
            raise HTTPException(status_code=500, detail=f"API error during content analysis: {str(openai_error)}")

        first_choice = response.choices[0]
        content_text = getattr(getattr(first_choice, "message", None), "content", None)
        if not content_text:
            logger.warning("No content found in first choice, using string representation")
            content_text = str(first_choice)

        logger.info(f"Extracted image content - length: {len(content_text)} characters")
        logger.debug(f"Image content preview: {content_text[:200]}...")

        # Use same system prompt for suggestion generation
        suggestion_messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": f"Generate an optimized reply suggestion. Context: {instruction}\n\nConversation content:\n{content_text}"
            },
        ]

        logger.info("Starting second API call for suggestion generation using gpt-oss-20b-GGUF")
        logger.debug(f"Messages for suggestion: {len(suggestion_messages)} messages")

        try:
            suggestion_response = client.chat.completions.create(
                model="gpt-oss-20b-GGUF",  # Using gpt-oss-20b-GGUF model
                messages=suggestion_messages,
            )
            logger.info("Second API call completed successfully")
        except Exception as openai_error:
            logger.error(f"API error during suggestion generation: {type(openai_error).__name__}: {str(openai_error)}")
            raise HTTPException(status_code=500, detail=f"API error during suggestion generation: {str(openai_error)}")

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
                "model": "gpt-oss-20b-GGUF",
                "ocr_data": ocr_result,
                "pipeline": "OCR -> gpt-oss-20b-GGUF (text-only)",
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

