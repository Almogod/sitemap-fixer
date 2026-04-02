import os
import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr
from typing import Optional, List

class Settings(BaseSettings):
    # App Settings
    APP_ENV: str = Field(default="enterprise") # development, production, enterprise
    APP_NAME: str = "UrlForge | Autonomous SEO Engine"
    DEBUG: bool = Field(default=False)
    
    # Timeouts & Retries (Profile specific)
    TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    CONCURRENCY: int = 5
    
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FORMAT: str = Field(default="json") # json or text
    
    # Auth / Security settings (Locked layer removed)
    ALLOWED_ORIGINS: List[str] = Field(default=["*"])
    
    # Infrastructure
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    DATABASE_URL: str = Field(default="sqlite:///./database.db")
    
    # Automation / Global Deployment Settings
    AUTOMATION_PLATFORM: str = "filesystem" # filesystem, github, ftp, webhook
    GITHUB_TOKEN: Optional[SecretStr] = Field(default=None)
    GITHUB_REPO: str = Field(default="user/repo")
    GITHUB_BRANCH: str = Field(default="main")
    
    FTP_HOST: str = Field(default="")
    FTP_USER: str = Field(default="")
    FTP_PASSWORD: Optional[SecretStr] = Field(default=None)
    
    # LLM Settings
    LLM_PROVIDER: str = Field(default="openai")
    OPENAI_API_KEY: Optional[SecretStr] = Field(default=None)
    GEMINI_API_KEY: Optional[SecretStr] = Field(default=None)
    OLLAMA_HOST: str = Field(default="http://localhost:11434")
    
    CRAWL_TIMEOUT: int = 30
    CRAWLER_PROXY: Optional[str] = Field(default=None)
    CRAWLER_BASIC_AUTH: Optional[str] = Field(default=None) # user:pass
    CRAWLER_BEARER_TOKEN: Optional[str] = Field(default=None)
    
    # Storage Settings
    # Path for traditional JSON (deprecated soon)
    TASK_STORE_PATH: str = "tasks.json"
    AUDIT_LOG_PATH: str = "audit.log"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


def get_settings() -> Settings:
    settings = Settings()
    
    # Apply Enterprise Defaults
    if settings.APP_ENV == "enterprise":
        settings.TIMEOUT = 10
        settings.MAX_RETRIES = 1
        settings.CONCURRENCY = 50
    elif settings.APP_ENV == "production":
        settings.TIMEOUT = 15
        settings.MAX_RETRIES = 2
        settings.CONCURRENCY = 20

    return settings

config = get_settings()
