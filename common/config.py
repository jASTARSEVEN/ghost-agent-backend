import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    SUPABASE_URL: str | None = os.getenv("SUPABASE_URL")
    
    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60)
    REFRESH_TOKEN_EXPIRE_DAYS: int = os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7)
    
    # App
    APP_NAME: str = "GhostAgent Backend"
    DEBUG: bool = False
    
    # Gemini AI (Deprecated - kept for rollback)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
    
    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    AZURE_API_VERSION: str = os.getenv("AZURE_API_VERSION", "2025-01-01-preview")
    AZURE_DEPLOYMENT_NAME: str = os.getenv("AZURE_DEPLOYMENT_NAME", "dataripple-gpt-4o")
    
    # Extraction Configuration
    EXTRACTION_CHUNK_SIZE: int = int(os.getenv("EXTRACTION_CHUNK_SIZE", "30000"))  # characters per chunk (optimized for speed)
    EXTRACTION_CHUNK_OVERLAP: int = int(os.getenv("EXTRACTION_CHUNK_OVERLAP", "500"))  # overlap between chunks
    EXTRACTION_MAX_PARALLEL: int = int(os.getenv("EXTRACTION_MAX_PARALLEL", "5"))  # max parallel chunk processing
    EXTRACTION_TIMEOUT_PER_CHUNK: int = int(os.getenv("EXTRACTION_TIMEOUT_PER_CHUNK", "90"))  # seconds (increased for safety)
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="allow")


settings = Settings()