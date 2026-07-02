from pydantic import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    bot_token: str
    crm_endpoint_url: HttpUrl
    retry_attempts: int = 3
    retry_delay_seconds: float = 3.0
    crm_request_timeout_seconds: float = 10.0
    redis_url: str = "redis://redis:6379/0"


settings = Settings()
