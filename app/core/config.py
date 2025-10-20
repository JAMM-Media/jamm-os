from pydantic import BaseModel  # noqa: F401
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "JAMM OS Backend"
    debug: bool = True
    database_url: str = "postgresql://postgres:postgres@localhost:5432/accounting_dev"
    cors_origins: str = "*"  # comma-separated in prod

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
