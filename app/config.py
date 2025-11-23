import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    LLM_API_KEY: str | None = None
    EMBEDDING_API_KEY: str | None = None
    DATABASE_URL: str | None = None
    MODEL_VERSION: str = Field(default="dosm-rag-local")
    LOG_LEVEL: str = Field(default="INFO")
    API_KEY: str | None = None  # If set, required via X-API-Key header on protected endpoints

    # Pydantic v2 configuration: ignore unrelated environment variables
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
