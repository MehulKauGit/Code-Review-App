from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    github_webhook_secret:str
    redis_url:str="redis://localhost:6379/0"
    llm_api_key:str
    llm_model: str = "llama-3.3-70b-versatile"
    debug: bool =False
    app_name: str = "My API"

    model_config= SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()    