from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SCRAPER_",
        extra="ignore",
    )

    target_url: str = "http://192.168.0.186:8080/backoffice/#/login"
    username: str = Field(min_length=1)
    password: SecretStr = Field(min_length=1)
    headless: bool = True
    ignore_https_errors: bool = False
    navigation_timeout_ms: int = Field(default=30_000, ge=1_000)
    selector_timeout_ms: int = Field(default=10_000, ge=1_000)
    search_timeout_ms: int = Field(default=15_000, ge=1_000)

    @field_validator("target_url")
    @classmethod
    def validate_target_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("target_url debe ser una URL HTTP o HTTPS válida")
        return value

    @property
    def client_url(self) -> str:
        """Build the Angular client route while preserving the backoffice path."""

        base_url = self.target_url.split("#", 1)[0]
        return f"{base_url}#/admin/client"


@lru_cache
def get_settings() -> Settings:
    return Settings()
