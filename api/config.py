from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    github_webhook_secret:str
    redis_url:str="redis://localhost:6379/0"
    llm_api_key:str
    llm_model: str = "openai/gpt-oss-120b"
    debug: bool =False
    app_name: str = "My API"
    github_app_id: int
    github_app_installation_id: str
    github_app_private_key_path: str

    model_config= SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()    