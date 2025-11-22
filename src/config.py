import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    # Load sensitive variables from .env only - no hardcoded defaults
    # These must be set in your .env file
    qdrant_url: str
    qdrant_api_key: str
    google_api_key: str
    
    # Non-sensitive configuration with defaults
    collection_name: str = "my_knowledge_base"
    documents_dir: str = "src/documents"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # Ignore extra fields from .env file
    )


settings = Settings()

