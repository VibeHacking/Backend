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
