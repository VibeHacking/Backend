from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = Field(default="not-needed", description="OpenAI API key")
    openai_model: str = Field(default="gpt-oss-20b-GGUF", description="OpenAI model to use")
    ocr_server_url: str = Field(default="http://localhost:4004", description="OCR server URL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()