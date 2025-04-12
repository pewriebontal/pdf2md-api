import os
import secrets
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    """Application settings"""
    PROJECT_NAME: str = "PDF to Markdown API"
    API_VERSION: str = "1.0.0"
    
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ENVIRONMENT: str = "development"
    
    # CORS settings
    BACKEND_CORS_ORIGINS: List[str] = ["*"]
    
    # Security
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    
    # LLM service API keys
    GOOGLE_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    CLAUDE_API_KEY: Optional[str] = None
    VERTEX_PROJECT_ID: Optional[str] = None
    
    # Performance/hardware settings
    TORCH_DEVICE: str = "auto"
    
    # File size limits (in MB)
    MAX_UPLOAD_SIZE: int = 50
    
    @property
    def llm_available(self) -> bool:
        """Check if any LLM API keys are configured"""
        return any([
            self.GOOGLE_API_KEY,
            self.OPENAI_API_KEY,
            self.CLAUDE_API_KEY,
            self.VERTEX_PROJECT_ID
        ])
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Allow extra fields

# Create settings instance
settings = Settings()