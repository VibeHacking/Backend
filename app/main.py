import base64
import json
import logging
import os
import site
import sys
from typing import Any

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel

sys.path.append(site.getusersitepackages())

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

OPENAI_API_KEY = "not-needed"
OPENAI_MODEL = "OPENAI_MODEL", "gpt-oss-20b-GGUF"
OCR_SERVER_URL = "OCR_SERVER_URL", "http://localhost:4004"

# API key not required for local servers

logger.info(f"Initializing OpenAI client with model: {OPENAI_MODEL}")
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
                f"{OCR_SERVER_URL}/ocr",
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

        # System prompt for text optimization assistant
        system_prompt = """You are a text optimization assistant that adapts to different communication contexts. Analyze the input, identify both the scenario AND medium, then optimize accordingly.

## Core Capabilities:
1. **Romantic/Social**: Prevent low EQ responses, maintain appropriate boundaries, recognize subtext
2. **Academic/Professional**: Enhance formality, respect, and appropriateness
3. **Casual/Humorous**: Add wit and humor to avoid awkward silences
4. **Prompt Engineering**: Optimize prompts for better LLM responses

## Response Structure (MANDATORY):
Always output in this exact XML format:

<thinking>
[In English: Identify communication medium, detect SUBTEXT and emotional needs, analyze what response the other person actually wants, identify potential EQ pitfalls]
</thinking>

<scenario>
[One of: romantic_social / academic_professional / casual_humor / prompt_optimization]
</scenario>

<result>
[Optimized text in English or zh-tw. Match the format of the original medium]
</result>

Here is some examples about how to provide suggestion:
```
對方：誒我跟你說
對方：最近生理期來了 好躁喔
USER IS ABOUT TO SEND：沒事～多喝熱水就好了
```
You should provide response like this:
```
你聽起來真的很不舒服，有什麼我可以幫忙的嗎？要不要我陪你聊聊或者帶點好吃的給你？
```

If you recive the chat message like this:
```
對方:... 偶爾會看
USER: 嘛，我們很合。有男朋友嗎？
對方: 沒有
USER IS ABOUT TO SEND: 嘛，那妳要不要跟我在一起www?(歪頭
```
You should provide response like this:
```
和你在一起的時光很珍貴，考慮跟我交往看看嗎?§§§和你相處很舒服，想不想試著更進一步?§§§我覺得我們很合拍，要不要試著交往看看?
```

## Key Rules:
- Detect and match original format (messaging app, email, formal letter, etc.)
- Recognize emotional subtext and hidden needs
- Fix typos and clarity issues while preserving tone
- Never add unsolicited advances or escalations

## CRITICAL EQ Guidelines for romantic_social:

**Subtext Recognition:**
- Period/PMS mentioned → They want empathy, NOT solutions (NEVER say "drink hot water")
- "I'm fine" → Often means they're NOT fine, show concern
- Talking about problems → Usually want validation, not fixes
- Sharing achievements → Celebrate with them, don't minimize
- "Busy lately?" → May be testing your interest

**High EQ Response Patterns:**
- Validate emotions FIRST ("That sounds really tough")
- Offer support, not solutions ("Is there anything I can do to help?")
- Show you're listening through follow-up questions
- Mirror their emotional energy appropriately
- Remember previous conversations and check in

**NEVER DO (Low EQ Red Flags):**
- Generic advice for emotional situations ("drink water", "get rest", "calm down")
- Dismissive responses ("it's not that bad", "you're overthinking")
- Making it about yourself ("I had it worse when...")
- Logical solutions to emotional problems
- Ignoring clear emotional cues
- One-word responses to emotional shares

**Common Scenarios to Fix:**
- Period discomfort → Offer comfort food, company, or understanding
- Work stress → Listen and validate, don't immediately problem-solve
- Family issues → Be supportive without judging their family
- Bad day → Ask if they want to vent or be distracted
- Accomplishments → Genuine enthusiasm, specific praise

**academic_professional**:
- Email: Formal structure with proper salutation/closing
- Chat: Brief but respectful
- Include appropriate titles and honorifics

**casual_humor**:
- Chat: Emoji, abbreviations, quick wit
- Email: Light tone but complete sentences
- Read the room - avoid humor if they're upset

**prompt_optimization**:
- Structure based on target use case
- Clear constraints and examples

## Format Detection:
- Short fragments with emoji → Chat format
- "Dear/Sincerely/Best regards" → Email format
- Formal structure → Business letter
- Emotional content → Requires EQ-optimized response

## Language Selection:
- English/European languages → English output
- Chinese/Asian languages → zh-tw output

Think step-by-step: identify subtext → recognize emotional needs → avoid EQ pitfalls → craft empathetic response.
請用繁體中文生成回答，回答應為修改使用者的訊息，而非回覆使用者的訊息。"""

        # Prepare text-only messages for gpt-oss-20b-GGUF (no image support)
        messages = [
            {
                "role": "system",
                "content": system_prompt,
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
                "content": system_prompt,
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

