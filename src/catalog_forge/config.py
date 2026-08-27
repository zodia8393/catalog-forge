from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CATALOG_FORGE_",
        env_file=".env",
        enable_decoding=False,
        extra="ignore",
    )

    database_url: str = "sqlite:///./catalog_forge.sqlite"
    redis_url: str = "redis://localhost:6379/0"
    api_key: str = "local-development-only"
    allowed_hosts: list[str] = Field(default_factory=lambda: ["books.toscrape.com", "fixture"])
    private_host_allowlist: list[str] = Field(default_factory=list)
    allow_private_hosts: bool = False
    max_concurrency_per_host: int = Field(default=8, ge=1, le=100)
    min_host_interval_ms: int = Field(default=100, ge=0, le=60_000)
    request_timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    max_response_bytes: int = Field(default=5_000_000, ge=1_024, le=50_000_000)
    max_attempts: int = Field(default=4, ge=1, le=10)
    low_confidence_threshold: float = Field(default=0.9, ge=0, le=1)
    stream_name: str = "catalog-forge:targets"
    consumer_group: str = "catalog-forge-workers"
    worker_name: str = "worker-1"

    @field_validator("allowed_hosts", "private_host_allowlist", mode="before")
    @classmethod
    def split_hosts(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip().lower() for part in value.split(",") if part.strip()]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
