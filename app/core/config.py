from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DEMO_APP_",
        case_sensitive=False,
        extra="ignore"
    )

    app_name: str = "devops-demo-app"
    app_version: str = "0.1.0"
    environment: str = "local"
    log_level: str = "INFO"
    log_json: bool = False

    default_min_delay_ms: int = 50
    default_max_delay_ms: int = 500
    default_error_rate: float = 0.2


@lru_cache
def get_settings() -> Settings:
    return Settings()