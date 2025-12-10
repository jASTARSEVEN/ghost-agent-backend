import os
from typing import Optional
from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = Field(..., description="Database connection URL")
    SUPABASE_URL: Optional[str] = Field(None, description="Supabase URL")
    
    # JWT
    SECRET_KEY: str = Field(..., min_length=32, description="JWT secret key")
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, ge=1, le=1440)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1, le=365)
    
    # App
    APP_NAME: str = Field(default="GhostAgent Backend")
    DEBUG: bool = Field(default=False)
    
    # Gemini AI (Deprecated - kept for rollback)
    GEMINI_API_KEY: str = Field(default="", description="Gemini API key")
    GEMINI_MODEL: str = Field(default="gemini-2.5-pro", description="Gemini model name")
    
    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: str = Field(default="", description="Azure OpenAI endpoint")
    AZURE_OPENAI_API_KEY: str = Field(default="", description="Azure OpenAI API key")
    AZURE_API_VERSION: str = Field(default="2025-01-01-preview", description="Azure API version")
    AZURE_DEPLOYMENT_NAME: str = Field(default="dataripple-gpt-4o", description="Azure deployment name")
    
    # Extraction Configuration
    EXTRACTION_CHUNK_SIZE: int = Field(default=30000, ge=1000, le=100000, description="Characters per chunk")
    EXTRACTION_CHUNK_OVERLAP: int = Field(default=500, ge=0, le=10000, description="Overlap between chunks")
    EXTRACTION_MAX_PARALLEL: int = Field(default=5, ge=1, le=20, description="Max parallel chunk processing")
    EXTRACTION_TIMEOUT_PER_CHUNK: int = Field(default=90, ge=10, le=300, description="Timeout per chunk in seconds")

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("DATABASE_URL is required and cannot be empty")
        return v
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="allow",
        env_file_encoding="utf-8"
    )


settings = Settings()