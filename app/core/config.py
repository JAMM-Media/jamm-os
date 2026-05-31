# app/core/config.py

import logging
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Literal
import os

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # App environment
    env: Literal["development", "production", "testing"] = "development"
    debug: bool = True

    # App metadata
    app_name: str = "JAMM PX"
    host: str = "0.0.0.0"
    port: int = 8000

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Database
    DATABASE_URL: str

    # AWS / S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = ""
    AWS_SES_FROM_EMAIL: str = ""

    # Postmark
    POSTMARK_API_KEY: str = ""

    # Dropbox Sign (e-signature)
    DROPBOX_SIGN_API_KEY: str = ""
    DROPBOX_SIGN_WEBHOOK_SECRET: str = ""

    # Client Portal
    PORTAL_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    PORTAL_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PORTAL_SESSION_HARD_EXPIRE_DAYS: int = 30
    PORTAL_INVITE_TOKEN_EXPIRE_HOURS: int = 72
    FRONTEND_URL: str = "http://localhost:3000"

    # Encryption
    ENCRYPTION_KEY: str = ""

    # QuickBooks OAuth
    QUICKBOOKS_CLIENT_ID: str = ""
    QUICKBOOKS_CLIENT_SECRET: str = ""
    QUICKBOOKS_REDIRECT_URI: str = ""
    QUICKBOOKS_ENVIRONMENT: str = "sandbox"
    QUICKBOOKS_REALM_ID: str = ""

    # Anthropic (Concierge)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_CONCIERGE_KEY: str = ""

    # Stripe
    stripe_secret_key: str | None = None
    stripe_publishable_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_connect_client_id: str | None = None

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY is not configured — concierge endpoints will return HTTP 503")
    return settings
