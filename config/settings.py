import os
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API Configuration
    app_name: str = "Document Q&A RAG System"
    version: str = "1.0.0"
    description: str = "A FastAPI backend for document Q&A using RAG"

    # Embedding Service Configuration
    embedding_model: str = "all-MiniLM-L6-v2"

    # LLM Service Configuration
    llm_model: str = "llama-3.3-70b-versatile"
    groq_api_key: Optional[str] = None
    groq_api_url: str = "https://api.groq.com/openai/v1"

    # Vector Store Configuration (for simplicity, we'll use in-memory, but can be extended)
    vector_store_type: str = "in_memory"

    # Chunking Configuration
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # Retrieval Configuration
    top_k: int = 5

    # File Upload Configuration
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: list = [".pdf", ".txt", ".docx"]
    upload_dir: str = "uploads"

    # Logging Configuration
    log_level: str = "INFO"

    # Rate Limiting
    rate_limit_per_minute: int = 10

    class Config:
        env_file = ".env"


settings = Settings()
