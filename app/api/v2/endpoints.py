from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.api.models import HealthResponse

router = APIRouter()

# In v2, could add enhanced endpoints or modify existing ones
# This is just a placeholder for future development

@router.get("/health", response_model=HealthResponse)
async def health_check_v2():
    """v2 health check endpoint"""
    return {
        "status": "healthy",
        "llm_available": True,
        "torch_device": "auto",
        "version": "2.0.0",
        "api_version": "v2",
    }

