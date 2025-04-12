import logging
import os
from pathlib import Path
from fastapi import APIRouter, Depends, File, UploadFile, Form, BackgroundTasks, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..core.config import settings
from ..db.base import get_db
from ..db.crud import get_conversion_by_hash_and_params, create_conversion, update_conversion_access
from ..services.file_service import save_upload_file, store_file_permanently, cleanup_temp_file
from ..services.converter import convert_pdf
from . import models

# Set up logging
logger = logging.getLogger("pdf2md.api")

# Set up templates - path is relative to app directory
templates_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=templates_path)

# Create router
router = APIRouter()

@router.get("/")
async def read_root(request: Request):
    """Render the home page"""
    return templates.TemplateResponse("index.html", {"request": request})

@router.post("/convert", response_model=models.ConversionResponse)
async def convert_pdf_endpoint(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    use_llm: bool = Form(False),
    paginate_output: bool = Form(False),
    extract_images: bool = Form(True),
    force_ocr: bool = Form(False),
):
    """
    Convert a PDF file to Markdown with caching
    
    - **file**: The PDF file to convert
    - **use_llm**: Whether to use an LLM to improve accuracy
    - **paginate_output**: Whether to paginate the output
    - **extract_images**: Whether to extract images from the PDF
    - **force_ocr**: Force OCR processing on the entire document
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Check file size (limit to settings.MAX_UPLOAD_SIZE by default)
    # Getting content length from headers or approximating it
    content_length = 0
    if hasattr(file, 'size'):
        content_length = file.size
    elif 'content-length' in file.headers:
        content_length = int(file.headers['content-length'])
    
    if content_length > settings.MAX_UPLOAD_SIZE * 1024 * 1024:
        raise HTTPException(
            status_code=413, 
            detail=f"File too large. Maximum allowed size is {settings.MAX_UPLOAD_SIZE}MB"
        )
        
    # Check if LLM is requested but no API keys are configured
    if use_llm and not settings.llm_available:
        logger.warning("LLM enhancement requested but no API keys configured - continuing without LLM")
        use_llm = False  # Disable LLM silently and continue with conversion
    
    try:
        # Save the uploaded file and calculate its hash
        temp_file_path, file_hash = await save_upload_file(file)
        
        # Schedule cleanup of the temp file
        background_tasks.add_task(cleanup_temp_file, temp_file_path)
        
        # Check if we already have this file in the cache with matching parameters
        cached_conversion = get_conversion_by_hash_and_params(
            db, 
            file_hash,
            use_llm=use_llm,
            paginate_output=paginate_output,
            extract_images=extract_images,
            force_ocr=force_ocr
        )
        
        # If we have a cached version, return it
        if cached_conversion:
            # Update access statistics
            update_conversion_access(db, file_hash)
            
            logger.info(f"Cache hit for file: {file.filename} (hash: {file_hash})")
            
            return models.ConversionResponse(
                success=True,
                message=f"Successfully retrieved cached conversion for {file.filename}",
                markdown=cached_conversion.markdown_content,
                cached=True,
                file_hash=file_hash
            )
        
        # Store the file permanently using its hash as the filename
        permanent_file_path = store_file_permanently(temp_file_path, file_hash)
        
        # Log the conversion request
        logger.info(f"Converting file: {file.filename} (hash: {file_hash})")
        
        # Convert the PDF
        markdown, metadata = convert_pdf(
            str(permanent_file_path),
            use_llm=use_llm,
            force_ocr=force_ocr,
            extract_images=extract_images,
            paginate_output=paginate_output
        )
        
        # Store the conversion in the cache
        create_conversion(
            db=db,
            file_hash=file_hash,
            original_filename=file.filename,
            markdown_content=markdown,
            use_llm=use_llm,
            paginate_output=paginate_output,
            extract_images=extract_images,
            force_ocr=force_ocr
        )
        
        # Return the markdown
        return models.ConversionResponse(
            success=True,
            message=f"Successfully converted {file.filename}",
            markdown=markdown,
            cached=False,
            file_hash=file_hash
        )
        
    except Exception as e:
        logger.exception(f"Error converting PDF: {str(e)}")
        return models.ConversionResponse(
            success=False,
            message="Conversion failed",
            error=str(e),
        )

@router.get("/health", response_model=models.HealthResponse)
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "llm_available": settings.llm_available,
        "torch_device": settings.TORCH_DEVICE,
        "version": settings.API_VERSION
    }