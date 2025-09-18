uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload       

curl -X POST \
  -F "instruction=This is a chat between friends" \                      
  -F "image=@/Users/ddd/Desktop/example.png" \
  http://localhost:8000/analyze | jq
