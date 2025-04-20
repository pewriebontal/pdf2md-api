import os
from pathlib import Path
from typing import List, Optional, Union, Dict, Any
from pydantic import AnyHttpUrl, field_validator, ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # --- Core API Settings ---
    API_VERSION: str = "2.0.0"
    PROJECT_NAME: str = "PDF to Markdown API"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = False

    # --- CORS ---
    BACKEND_CORS_ORIGINS: List[str] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        raise ValueError(v)

    # --- Database ---
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/./storage/pdf2md.db"

    # --- Celery ---
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # --- File Storage ---
    STORAGE_PATH: str = str(BASE_DIR / "storage")
    TEMP_PATH: str = str(BASE_DIR / "storage" / "temp")
    UPLOAD_PATH: str = str(BASE_DIR / "storage" / "uploads")

    # --- Conversion Settings ---
    MAX_UPLOAD_SIZE: int = 50  # In Megabytes
    TORCH_DEVICE: str = "cpu"  # or "cuda" if GPU is available

    # --- LLM Enhancement (Optional) ---
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    # Derived property to check if any LLM key is set
    @property
    def llm_available(self) -> bool:
        return bool(self.OPENAI_API_KEY or self.ANTHROPIC_API_KEY)

    # --- Logging Configuration ---
    LOGGING_CONFIG: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "pdf2md": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "celery": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "marker": {
                "handlers": ["console"],
                "level": "WARNING",
                "propagate": False,
            },
        },
        "root": {
            "handlers": ["console"],
            "level": "WARNING",
        },
    }

    # Pydantic settings configuration
    model_config = SettingsConfigDict(
        env_file=f"{BASE_DIR}/.env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
