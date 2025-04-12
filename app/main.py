import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.endpoints import router
from .core.config import settings
from .core.logging import setup_logging
from .db.base import engine
from .db import models

# Create required directories
static_dir = os.path.join(os.path.dirname(__file__), "static")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(static_dir, exist_ok=True)
os.makedirs(templates_dir, exist_ok=True)

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Set up logging
logger = setup_logging()

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for converting PDF documents to Markdown format using Marker",
    version=settings.API_VERSION,
)

# Configure CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Mount static files directory relative to the app directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include API router
app.include_router(router)

# App startup event
@app.on_event("startup")
async def startup_event():
    logger.info("Starting PDF to Markdown API")
    
    if settings.llm_available:
        logger.info("LLM enhancement feature is AVAILABLE")
        
        available_services = []
        if os.environ.get("GOOGLE_API_KEY"):
            available_services.append("Google Gemini")
        if os.environ.get("OPENAI_API_KEY"):
            available_services.append("OpenAI")
        if os.environ.get("CLAUDE_API_KEY"):
            available_services.append("Claude")
        if os.environ.get("VERTEX_PROJECT_ID"):
            available_services.append("Vertex AI")
            
        logger.info(f"Available LLM services: {', '.join(available_services)}")
    else:
        logger.info("LLM enhancement feature is NOT AVAILABLE - API keys not configured")
    
    logger.info(f"Using TORCH_DEVICE: {settings.TORCH_DEVICE}")
    
    logger.info(f"Maximum upload size: {settings.MAX_UPLOAD_SIZE}MB")