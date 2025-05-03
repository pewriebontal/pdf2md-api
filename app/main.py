import logging.config
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from .api.router import router as api_router 
from .core.config import settings
from .db.base import init_db

logger = logging.getLogger("pdf2md.main")

if hasattr(settings, "LOGGING_CONFIG"):
    logging.config.dictConfig(settings.LOGGING_CONFIG)
else:
    logging.basicConfig(level=logging.INFO)
    logger.warning("LOGGING_CONFIG not found in settings. Using basic logging.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting PDF to Markdown API")
    logger.info(
        f"LLM enhancement feature is {'AVAILABLE' if settings.llm_available else 'NOT AVAILABLE - API keys not configured'}"
    )
    logger.info(f"Using TORCH_DEVICE: {settings.TORCH_DEVICE}")
    logger.info(f"Maximum upload size: {settings.MAX_UPLOAD_SIZE}MB")
    init_db()
    Path(settings.STORAGE_PATH).mkdir(parents=True, exist_ok=True)
    Path(settings.TEMP_PATH).mkdir(parents=True, exist_ok=True)
    Path(settings.UPLOAD_PATH).mkdir(parents=True, exist_ok=True)
    yield
    logger.info("Shutting down API")


app = FastAPI(
    title="PDF to Markdown API",
    description="Convert PDF documents to Markdown using Marker.",
    version=settings.API_VERSION,
    lifespan=lifespan,
)

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router)


static_dir = Path(settings.UPLOAD_PATH)
if static_dir.is_dir():
    app.mount("/uploads", StaticFiles(directory=static_dir), name="uploads")
    logger.info(f"Mounted static files directory: {static_dir} at /uploads")
else:
    logger.warning(
        f"Static files directory {static_dir} not found. Images may not be served."
    )