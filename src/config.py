import os
import yaml
from typing import Optional, List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "SEO Enterprise Platform"
    DEBUG: bool = False
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json") # json or text
    
    # Auth Settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key-change-it")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Infrastructure
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Automation / Global Deployment Settings
    AUTOMATION_PLATFORM: str = "filesystem" # filesystem, github, ftp, webhook
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_REPO: str = os.getenv("GITHUB_REPO", "user/repo")
    GITHUB_BRANCH: str = os.getenv("GITHUB_BRANCH", "main")
    
    FTP_HOST: str = os.getenv("FTP_HOST", "")
    FTP_USER: str = os.getenv("FTP_USER", "")
    FTP_PASSWORD: str = os.getenv("FTP_PASSWORD", "")
    
    # LLM Settings
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    
    CRAWL_TIMEOUT: int = 30
    CRAWLER_PROXY: Optional[str] = os.getenv("CRAWLER_PROXY", None)
    CRAWLER_BASIC_AUTH: Optional[str] = os.getenv("CRAWLER_BASIC_AUTH", None) # user:pass
    CRAWLER_BEARER_TOKEN: Optional[str] = os.getenv("CRAWLER_BEARER_TOKEN", None)
    
    # Storage Settings
    TASK_STORE_PATH: str = "tasks.json"
    AUDIT_LOG_PATH: str = "audit.log"

    class Config:
        env_file = ".env"


def load_config(config_path: Optional[str] = "config.yaml") -> Settings:
    """Load settings from environment and optionally a YAML file."""
    settings = Settings()
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                yaml_content = yaml.safe_load(f)
                if yaml_content:
                    for key, value in yaml_content.items():
                        if hasattr(settings, key):
                            setattr(settings, key, value)
        except Exception as e:
            print(f"Error loading {config_path}: {e}")
    return settings

config = load_config()
