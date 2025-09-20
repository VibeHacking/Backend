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

# Add user site-packages to path for PaddleOCR
import site
sys.path.append(site.getusersitepackages())

from paddleocr import PaddleOCR
from PIL import Image
import numpy as np
import io

load_dotenv()

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

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY is not set. Provide it via environment or .env file.")
    raise RuntimeError("OPENAI_API_KEY is not set. Provide it via environment or .env file.")

logger.info(f"Initializing OpenAI client with model: {OPENAI_MODEL}")

# Check if we should use Lemonade server or OpenAI directly
USE_LEMONADE = os.getenv("USE_LEMONADE", "false").lower() == "true"

if USE_LEMONADE:
    logger.info("Configuring client for Lemonade server at localhost:8000")
    client = OpenAI(
        base_url="http://localhost:8000/api/v1",
        api_key="not-needed"  # Lemonade server doesn't require real API key
    )
    ACTUAL_MODEL = "Gemma-3-4b-it-GGUF"  # Lemonade model
else:
    logger.info(f"Using OpenAI API directly with key: {OPENAI_API_KEY[:8]}...")
    client = OpenAI(
        api_key=OPENAI_API_KEY
    )
    ACTUAL_MODEL = OPENAI_MODEL  # Use configured OpenAI model

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


class AnalyzeOCRResponse(BaseModel):
    extracted_text: str
    analysis: str
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
                model=ACTUAL_MODEL,
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
                model=ACTUAL_MODEL,
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
                "model": ACTUAL_MODEL,
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


def extract_text_from_image(image_content: bytes) -> str:
    """Extract text from image using PaddleOCR v5 mobile"""
    try:
        # Initialize PaddleOCR v5 mobile with Chinese (Traditional) and English support
        ocr = PaddleOCR(
            lang='chinese_cht'  # Use Traditional Chinese model (also supports English)
        )

        # Convert image bytes to numpy array
        image_array = np.frombuffer(image_content, dtype=np.uint8)
        image = Image.open(io.BytesIO(image_content))

        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Convert PIL image to numpy array for PaddleOCR
        image_np = np.array(image)

        # Use PaddleOCR to extract text - using predict method for v5
        result = ocr.predict(image_np)

        # Extract text from results (new format)
        extracted_texts = []
        logger.debug(f"Result type: {type(result)}")

        if isinstance(result, list) and len(result) > 0:
            logger.debug(f"Result has {len(result)} items")
            logger.debug(f"First result keys: {result[0].keys() if isinstance(result[0], dict) else 'Not a dict'}")

            # Check for 'rec' key in the result
            if 'rec' in result[0]:
                rec_results = result[0]['rec']
                logger.info(f"Found {len(rec_results)} recognition results")
                for idx, item in enumerate(rec_results):
                    text = item.get('text', '')
                    score = item.get('score', 0)
                    if text:
                        logger.debug(f"Text {idx}: '{text}' (score: {score})")
                        extracted_texts.append(text)
            # Fall back to old format if needed
            elif 'rec_txt' in result[0]:
                rec_txt = result[0]['rec_txt']
                logger.info(f"Found {len(rec_txt)} text results (old format)")
                for txt in rec_txt:
                    if txt:
                        extracted_texts.append(txt)
            else:
                logger.warning(f"Unexpected result format. Available keys: {result[0].keys() if isinstance(result[0], dict) else 'N/A'}")

        extracted_text = '\n'.join(extracted_texts)

        if not extracted_text:
            logger.warning("No text extracted from image")
        else:
            logger.info(f"OCR extraction completed - extracted {len(extracted_text)} characters")

        return extracted_text.strip()

    except Exception as e:
        logger.error(f"PaddleOCR extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"OCR extraction failed: {e}")


@app.post("/analyze-ocr", response_model=AnalyzeOCRResponse)
async def analyze_ocr(
    instruction: str = Form(..., description="Instruction about how to analyze the extracted text"),
    image: UploadFile = File(..., description="Image file (jpeg/png/webp/etc.)"),
):
    logger.info(f"Received analyze-ocr request - instruction: '{instruction}', image filename: {image.filename}")
    try:
        content = await image.read()
        logger.info(f"Image read successfully - size: {len(content)} bytes, content_type: {image.content_type}")

        if not content:
            logger.error("Empty image uploaded")
            raise HTTPException(status_code=400, detail="Empty image uploaded")

        # Step 1: Extract text using OCR
        logger.info("Starting OCR text extraction")
        extracted_text = extract_text_from_image(content)
        logger.info(f"OCR extraction completed - extracted {len(extracted_text)} characters")
        logger.debug(f"Extracted text preview: {extracted_text[:200]}...")

        if not extracted_text:
            logger.warning("No text extracted from image")
            extracted_text = "No text was detected in the image."

        # Step 2: Send extracted text to LLM for analysis
        analysis_messages = [
            {
                "role": "system",
                "content": "You are an assistant that analyzes extracted text and provides helpful insights. "
                "Be clear, concise, and actionable in your analysis."
            },
            {
                "role": "user",
                "content": f"Please analyze the following extracted text and provide insights. {instruction}\n\nExtracted text:\n{extracted_text}"
            },
        ]

        logger.info("Starting LLM analysis of extracted text")
        logger.debug(f"Messages for analysis: {len(analysis_messages)} messages")

        try:
            analysis_response = client.chat.completions.create(
                model=ACTUAL_MODEL,
                messages=analysis_messages,
            )
            logger.info("LLM analysis completed successfully")
        except Exception as openai_error:
            logger.error(f"OpenAI API error during analysis: {type(openai_error).__name__}: {str(openai_error)}")
            raise HTTPException(status_code=500, detail=f"LLM analysis error: {str(openai_error)}")

        analysis_choice = analysis_response.choices[0]
        analysis_text = getattr(getattr(analysis_choice, "message", None), "content", None)
        if not analysis_text:
            logger.warning("No analysis found in choice, using string representation")
            analysis_text = str(analysis_choice)

        logger.info(f"Generated analysis - length: {len(analysis_text)} characters")
        logger.debug(f"Analysis preview: {analysis_text[:100]}...")

        logger.info("Preparing final OCR response")
        return AnalyzeOCRResponse(
            extracted_text=extracted_text,
            analysis=analysis_text,
            context={
                "method": "PaddleOCR v5 + LLM",
                "model": ACTUAL_MODEL,
                "ocr_engine": "PaddleOCR PP-OCRv5",
                "ocr_language": "chinese_cht (Traditional Chinese + English)",
                "openai_raw": {
                    "id": getattr(analysis_response, "id", None),
                    "created": getattr(analysis_response, "created", None),
                    "model": getattr(analysis_response, "model", None),
                },
            },
        )
    except HTTPException as he:
        logger.error(f"HTTP Exception occurred in analyze-ocr: {he.status_code} - {he.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in analyze-ocr endpoint: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
