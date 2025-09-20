## AI Reply Suggestion API

FastAPI server that accepts an image and an instruction, calls OpenAI (vision + text), and returns a suggested reply along with the full context used.

### Requirements

- Python 3.10+
- OpenAI API key

### Setup

1. Create and activate a virtual environment (recommended).
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure environment variables:
   - Create `.env` and set `OPENAI_API_KEY`.
   - Optionally set `OPENAI_MODEL` (default: `gpt-4o-mini`).

### Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Endpoint

- POST `/analyze`
- Content-Type: `multipart/form-data`
- Fields:
  - `instruction` (string): Instruction for generating the reply.
  - `image` (file): Image file (jpeg/png/webp/etc.).

### Example curl

```bash
curl -X POST \
  -F "instruction=Summarize the situation and suggest a concise reply." \
  -F "image=@/path/to/image.jpg" \
  http://localhost:8000/analyze | jq
```

### Response shape

```json
{
  "suggestion": "Proposed concise reply based on the image and instruction.",
  "context": {
    "model": "gpt-4o-mini",
    "messages": [
      { "role": "system", "content": "..." },
      {
        "role": "user",
        "content": [
          { "type": "text", "text": "<instruction>" },
          {
            "type": "image_url",
            "image_url": { "url": "data:image/jpeg;base64,..." }
          }
        ]
      }
    ],
    "openai_raw": { "id": "...", "created": 0, "model": "..." }
  }
}

```

curl -X POST -F "instruction=Summarize the situation and
   suggest a concise reply." -F
  "image=@C:\Users\VibeHackingUser\Documents\glass\screens
  hots\screenshot_1758196665910.png"
  http://localhost:8000/analyze

   基本 curl 請求

  curl -X POST \
    -F "instruction=Summarize the situation and suggest a 
  concise reply." \
    -F "image=@/path/to/your/image.jpg" \
    http://localhost:8001/analyze

  實際使用範例（你剛才的請求）

  curl -X POST \
    -F "instruction=Summarize the situation and suggest a     
  concise reply." \
    -F "image=@C:\Users\VibeHackingUser\Documents\glass\sc    
  reenshots\screenshot_1758196665910.png" \
    http://localhost:8001/analyze

  範例回覆

  剛才實際調用的完整 JSON 回覆：

  {
    "image_content": "The image shows a coding
  environment, likely Visual Studio Code, where a
  JavaScript file is being edited. The code includes a        
  style definition for a component called `StView`, using     
  CSS for layout. There are also messages in a terminal       
  window indicating that files are being updated and
  changes are being committed to a repository.
  \n\nAdditionally, there's an interface that appears to      
  show an AI suggestion or comment related to the
  code.\n\n### Summary of the Situation:\nThe user is
  working on a JavaScript project within Visual Studio        
  Code, making changes to component styles and pushing        
  updates to a version control system. They are also
  utilizing some sort of AI functionality for code
  assistance.\n\n### Suggested Reply:\n\"Looks like you're    
   making good progress on the project! If you have any       
  questions or need help with the AI suggestions, feel        
  free to ask!\"",
    "suggestion": "\"Great to see you updating your
  project! If you need any assistance with the code or AI     
  suggestions, just let me know!\"",
    "context": {
      "model": "gpt-4o-mini",
      "messages": [
        {
          "role": "system",
          "content": "You are an assistant that analyzes a    
   user's chat context from an image (e.g., screenshot)       
  and extract the content of the image.Record every
  message in the image."
        },
        {
          "role": "user",
          "content": [
            {
              "type": "text",
              "text": "Please analyze the image and
  extract the content of the image. Summarize the
  situation and suggest a concise reply."
            },
            {
              "type": "image_url",
              "image_url": {
                "url": "data:image/png;base64,..."
              }
            }
          ]
        }
      ],
      "openai_raw": {
        "id": "chatcmpl-...",
        "created": 1726743292,
        "model": "gpt-4o-mini-2024-07-18"
      }
    }
  }

  其他指令範例

# 分析商務對話
curl -X POST \
    -F "instruction=This is a business conversation.
  Suggest a professional reply." \
    -F "image=@business_chat.png" \
    http://localhost:8001/analyze

# 分析社交對話
  curl -X POST \
    -F "instruction=This is a casual friend chat. Suggest     
  a friendly response." \
    -F "image=@friend_chat.png" \
    http://localhost:8001/analyze

  # 分析技術討論
  curl -X POST \
    -F "instruction=This is a technical discussion.
  Provide a helpful technical response." \
    -F "image=@tech_discussion.png" \
    http://localhost:8001/analyze

  API 正在 http://localhost:8001 運行，可以接收任何圖片格     
  式（jpeg/png/webp等）並根據你的指令提供相應的回覆建議。     

──────────────────────────────────────────────────────────────
>  
──────────────────────────────────────────────────────────────
  1 background task ·↓ to view                             ◯  




