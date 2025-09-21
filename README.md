# AI Reply Suggestion API

一個智慧回覆建議系統，使用 **PaddleOCR** 進行圖片文字擷取，並透過 **lemonade-server** 的 **gpt-oss-20b-GGUF** 模型生成高 EQ 的回覆建議。

## 🚀 系統架構

### 核心技術
- **OCR 引擎**: PaddleOCR - 高精度的多語言文字識別系統
- **AI 模型**: lemonade-server 的 gpt-oss-20b-GGUF - 20B 參數的開源大語言模型
- **API 框架**: FastAPI - 現代化、高效能的 Python Web 框架

### 處理流程
1. 接收圖片上傳（支援 jpeg/png/webp 等格式）
2. 透過 PaddleOCR 伺服器擷取圖片中的文字內容
3. 將擷取的文字傳送給 gpt-oss-20b-GGUF 模型進行分析
4. 根據不同情境生成最適合的回覆建議

## 📋 系統需求

- Python 3.13+
- lemonade-server (運行在 localhost:8060)
- OCR 伺服器 (運行在 localhost:4004)

## 🛠️ 安裝步驟

### 1. 複製專案
```bash
git clone <repository-url>
cd Test_backend_server
```

### 2. 建立虛擬環境（建議）
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
```

### 3. 安裝依賴套件
```bash
pip install -r requirements.txt
```

### 4. 環境設定
建立 `.env` 檔案並設定以下參數：
```env
OPENAI_API_KEY=not-needed  # lemonade-server 不需要真實的 API key
USE_LEMONADE=true
OCR_SERVER_URL=http://localhost:4004  # OCR 伺服器位址
```

## 🔧 啟動服務

### 1. 確保相關服務正在運行
- lemonade-server (port 8060)
- OCR 伺服器 (port 4004)

### 2. 啟動 API 伺服器
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

服務將在 `http://localhost:8080` 運行

## 📡 API 使用說明

### Endpoint
- **POST** `/analyze`
- **Content-Type**: `multipart/form-data`

### 請求參數
| 參數 | 類型 | 說明 |
|-----|------|------|
| `instruction` | string | 情境描述（如：romantic、professional、casual 等） |
| `image` | file | 圖片檔案（支援 jpeg/png/webp 等格式） |

### 回應格式
```json
{
  "image_content": "從圖片中擷取並分析的內容",
  "suggestion": "根據情境優化後的回覆建議",
  "context": {
    "model": "gpt-oss-20b-GGUF",
    "ocr_data": { ... },
    "pipeline": "OCR -> gpt-oss-20b-GGUF (text-only)",
    "openai_raw": { ... }
  }
}
```

## 💡 使用範例

### 基本請求
```bash
curl -X POST \
  -F "instruction=這是一個朋友間的對話，請提供友善的回覆" \
  -F "image=@chat_screenshot.png" \
  http://localhost:8080/analyze
```

### 不同情境範例

#### 浪漫/社交情境
```bash
curl -X POST \
  -F "instruction=romantic_social - 需要高 EQ 的回覆" \
  -F "image=@romantic_chat.png" \
  http://localhost:8080/analyze
```

#### 專業/學術情境
```bash
curl -X POST \
  -F "instruction=academic_professional - 需要正式且專業的回覆" \
  -F "image=@business_email.png" \
  http://localhost:8080/analyze
```

#### 輕鬆/幽默情境
```bash
curl -X POST \
  -F "instruction=casual_humor - 加入適當的幽默感" \
  -F "image=@casual_chat.png" \
  http://localhost:8080/analyze
```

## 🎯 系統特色

### 智慧情境識別
- 自動識別對話的潛在意圖和情感需求
- 根據不同情境調整回覆風格和語氣
- 避免低 EQ 的回覆（如"多喝熱水"等）

### 多語言支援
- 支援繁體中文和英文回覆
- 自動根據原始內容選擇適當的語言

### 高 EQ 回覆模式
- **情感驗證優先**：先理解和認同對方的感受
- **避免說教**：不提供不必要的建議或解決方案
- **讀懂潛台詞**：理解"我沒事"背後的真實情感
- **適當的關心**：提供實際的幫助而非空泛的安慰

## 📁 專案結構
```
Test_backend_server/
├── app/
│   └── main.py          # 主要 API 程式碼
├── .env                 # 環境變數設定
├── pyproject.toml       # 專案設定檔
├── README.md           # 本文件
└── uv.lock            # 依賴鎖定檔
```

## 🔍 日誌記錄
系統會自動記錄運行日誌到：
- 控制台輸出（即時顯示）
- `app.log` 檔案（持久儲存）

## 📝 授權
[請加入適當的授權資訊]

## 🤝 貢獻
歡迎提交 Issue 和 Pull Request！

---

*Powered by lemonade-server's gpt-oss-20b-GGUF & PaddleOCR*