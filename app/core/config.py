# app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Literal
import os


class Settings(BaseSettings):
    # App environment
    env: Literal["development", "production", "testing"] = "development"
    debug: bool = True

    # App metadata
    app_name: str = "JAMM OS"
    host: str = "0.0.0.0"
    port: int = 8000

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Database
    DATABASE_URL: str

    # AWS / S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = ""

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
