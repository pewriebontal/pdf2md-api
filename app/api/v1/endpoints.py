import logging
import os
import json
import re
from pathlib import Path
from functools import lru_cache
from typing import Optional, List
from fastapi import (
    APIRouter,
    Depends,
    File,
    UploadFile,
    Form,
    HTTPException,
    Request,
    Response,
    status,
    Query,
)
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from celery.result import AsyncResult
import markdown2

from app.celery_app import celery_app
from app.core.config import settings
from app.db.base import get_db
from app.db.crud import (
    get_conversion_by_hash_and_params as db_get_conversion_by_hash_and_params,
    update_conversion_access,
    count_pending_conversions,
)
from app.services.file_service import (
    save_upload_file,
    store_file_permanently,
    cleanup_temp_file,
)
from app.services.converter import convert_pdf_task
from app.api.models import (
    ConversionResponse,
    AsyncTaskResponse,
    QueueStatusResponse,
    HealthResponse,
)
from app.db import models as db_models

# Set up logging
logger = logging.getLogger("pdf2md.api.v1")

templates_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "templates"
)
templates = Jinja2Templates(directory=templates_path)

router = APIRouter()


# --- In-Memory Cache ---
# Note: In-memory cache currently only stores markdown.
# For simplicity, won't cache image paths in memory for now.
@lru_cache(maxsize=128)
def get_cached_markdown_from_memory(
    file_hash: str,
    use_llm: bool,
    paginate_output: bool,
    extract_images: bool,
    force_ocr: bool,
) -> Optional[str]:
    return None


def update_memory_cache(
    file_hash: str,
    use_llm: bool,
    paginate_output: bool,
    extract_images: bool,
    force_ocr: bool,
    markdown: Optional[str],
):
    if markdown is None:
        return

    cache_key = (file_hash, use_llm, paginate_output, extract_images, force_ocr)
    try:
        cache_info = get_cached_markdown_from_memory.cache_info()
        current_size = cache_info.currsize if cache_info.currsize is not None else 0
        max_size = cache_info.maxsize if cache_info.maxsize is not None else 0

        if current_size < max_size:
            pass
    except Exception as e:
        logger.warning(f"Could not update memory cache: {e}")


@router.get("/")
async def read_root(request: Request):
    """Render the home page"""
    return templates.TemplateResponse("index.html", {"request": request})


@router.post(
    "/convert",
    response_model=None,
    responses={
        200: {
            "model": ConversionResponse,
            "description": "Cached result returned directly",
        },
        202: {
            "model": AsyncTaskResponse,
            "description": "Task successfully enqueued",
        },
        400: {"description": "Invalid input (e.g., not a PDF)"},
        413: {"description": "File too large"},
        500: {
            "model": AsyncTaskResponse,
            "description": "Failed to enqueue task",
        },
    },
)
async def convert_pdf_endpoint(
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    use_llm: bool = Form(False),
    paginate_output: bool = Form(False),
    extract_images: bool = Form(True),
    force_ocr: bool = Form(False),
):
    """
    Accepts a PDF file, checks cache, and enqueues a conversion task if not cached.
    Returns a direct result if cached (200 OK) or a task ID (202 Accepted).

    - file: The PDF file to convert
    - use_llm: Whether to use an LLM to improve accuracy
    - paginate_output: Whether to paginate the output
    - extract_images: Whether to extract images from the PDF
    - force_ocr: Force OCR processing on the entire document
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported",
        )

    file_size = file.size if hasattr(file, "size") and file.size else 0
    if not file_size and hasattr(file, "headers") and "content-length" in file.headers:
        try:
            file_size = int(file.headers["content-length"])
        except (ValueError, TypeError):
            logger.warning("Could not determine file size from headers.")
            file_size = 0

    if file_size > settings.MAX_UPLOAD_SIZE * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum allowed size is {settings.MAX_UPLOAD_SIZE}MB",
        )

    effective_use_llm = use_llm
    if use_llm and not settings.llm_available:
        logger.warning(
            "LLM enhancement requested but no API keys configured - proceeding without LLM"
        )
        effective_use_llm = False

    temp_file_path = None
    try:
        temp_file_path_obj, file_hash = await save_upload_file(file)
        temp_file_path = str(temp_file_path_obj)

        cached_markdown = get_cached_markdown_from_memory(
            file_hash, effective_use_llm, paginate_output, extract_images, force_ocr
        )
        if cached_markdown is not None:
            logger.info(
                f"In-memory cache hit for file: {file.filename} (hash: {file_hash}) - Markdown only"
            )
            db_conversion: Optional[db_models.ConversionCache] = (
                db_get_conversion_by_hash_and_params(
                    db,
                    file_hash,
                    effective_use_llm,
                    paginate_output,
                    extract_images,
                    force_ocr,
                )
            )
            image_paths = None
            if db_conversion and db_conversion.image_paths:
                try:
                    image_paths = json.loads(db_conversion.image_paths)
                except json.JSONDecodeError:
                    logger.error(
                        f"Failed to decode image_paths JSON for hash {file_hash}"
                    )
                    image_paths = None

            if db_conversion:
                update_conversion_access(db, file_hash)

            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except OSError as rm_err:
                    logger.error(
                        f"Error removing temporary file after memory cache hit {temp_file_path}: {rm_err}"
                    )

            memory_cache_response = ConversionResponse(
                success=True,
                message="Successfully retrieved cached conversion (memory/DB)",
                markdown=cached_markdown,
                image_paths=image_paths,
                cached=True,
                file_hash=file_hash,
            )
            return Response(
                content=memory_cache_response.model_dump_json(),
                status_code=status.HTTP_200_OK,
                media_type="application/json",
            )

        cached_conversion: Optional[db_models.ConversionCache] = (
            db_get_conversion_by_hash_and_params(
                db,
                file_hash,
                effective_use_llm,
                paginate_output,
                extract_images,
                force_ocr,
            )
        )

        if cached_conversion:
            update_conversion_access(db, file_hash)
            logger.info(
                f"Database cache hit for file: {file.filename} (hash: {file_hash})."
            )

            image_paths = None
            if cached_conversion.image_paths:
                try:
                    image_paths = json.loads(cached_conversion.image_paths)
                except json.JSONDecodeError:
                    logger.error(
                        f"Failed to decode image_paths JSON from DB for hash {file_hash}"
                    )
                    image_paths = None

            update_memory_cache(
                file_hash,
                bool(cached_conversion.use_llm),
                bool(cached_conversion.paginate_output),
                bool(cached_conversion.extract_images),
                bool(cached_conversion.force_ocr),
                cached_conversion.markdown_content,
            )

            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    logger.info(
                        f"Removed temporary file immediately due to cache hit: {temp_file_path}"
                    )
                except OSError as rm_err:
                    logger.error(
                        f"Error removing temporary file after cache hit {temp_file_path}: {rm_err}"
                    )

            db_cache_response = ConversionResponse(
                success=True,
                message=f"Successfully retrieved cached conversion for {file.filename}",
                markdown=cached_conversion.markdown_content,
                image_paths=image_paths,
                cached=True,
                file_hash=file_hash,
            )
            return Response(
                content=db_cache_response.model_dump_json(),
                status_code=status.HTTP_200_OK,
                media_type="application/json",
            )

        logger.info(
            f"Cache miss for file: {file.filename} (hash: {file_hash}). Enqueuing conversion task."
        )

        priority_level = 5 if effective_use_llm else 4
        task = convert_pdf_task.apply_async(
            args=[temp_file_path, file_hash, file.filename],
            kwargs={
                "use_llm": effective_use_llm,
                "force_ocr": force_ocr,
                "extract_images": extract_images,
                "paginate_output": paginate_output,
            },
            priority=priority_level,
        )

        logger.info(f"Task enqueued with ID: {task.id} for file {file.filename}")

        enqueue_response = AsyncTaskResponse(
            success=True,
            message=f"Conversion task for {file.filename} enqueued.",
            task_id=task.id,
            file_hash=file_hash,
        )
        return Response(
            content=enqueue_response.model_dump_json(),
            status_code=status.HTTP_202_ACCEPTED,
            media_type="application/json",
        )

    except HTTPException as http_exc:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(
                    f"Removed temporary file after HTTP exception: {temp_file_path}"
                )
            except OSError as rm_err:
                logger.error(
                    f"Error removing temporary file after HTTP exception {temp_file_path}: {rm_err}"
                )
        raise http_exc
    except Exception as e:
        logger.exception(
            f"Error processing file upload or enqueuing task for {file.filename if file else 'unknown file'}: {str(e)}"
        )
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(
                    f"Removed temporary file after general exception: {temp_file_path}"
                )
            except OSError as rm_err:
                logger.error(
                    f"Error removing temporary file after general exception {temp_file_path}: {rm_err}"
                )
        error_response_payload = AsyncTaskResponse(
            success=False,
            message="Failed to enqueue conversion task due to an internal error.",
            error=str(e),
        )
        return Response(
            content=error_response_payload.model_dump_json(),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            media_type="application/json",
        )


@router.get(
    "/tasks/{task_id}",
    response_model=None,
    responses={
        200: {
            "model": ConversionResponse,
            "description": "Task completed successfully, result returned",
        },
        202: {"description": "Task is still pending or running"},
        404: {"description": "Task result not found after completion"},
        500: {"model": ConversionResponse, "description": "Task failed"},
    },
)
async def get_task_status(task_id: str, db: Session = Depends(get_db)):
    task_result = AsyncResult(task_id, app=celery_app)

    if task_result.ready():
        if task_result.successful():
            result_data = task_result.result
            if result_data and result_data.get("status") == "SUCCESS":
                task_info = result_data.get("data", {})
                file_hash = task_info.get("file_hash")
                use_llm = task_info.get("use_llm")
                paginate_output = task_info.get("paginate_output")
                extract_images = task_info.get("extract_images")
                force_ocr = task_info.get("force_ocr")

                if file_hash:
                    db_conversion: Optional[db_models.ConversionCache] = (
                        db_get_conversion_by_hash_and_params(
                            db,
                            file_hash,
                            use_llm,
                            paginate_output,
                            extract_images,
                            force_ocr,
                        )
                    )
                    if db_conversion:
                        update_conversion_access(db, file_hash)
                        image_paths = None
                        if db_conversion.image_paths:
                            try:
                                image_paths = json.loads(db_conversion.image_paths)
                            except json.JSONDecodeError:
                                logger.error(
                                    f"Failed to decode image_paths JSON from DB for task {task_id}, hash {file_hash}"
                                )
                                image_paths = None

                        update_memory_cache(
                            db_conversion.file_hash,
                            bool(db_conversion.use_llm),
                            bool(db_conversion.paginate_output),
                            bool(db_conversion.extract_images),
                            bool(db_conversion.force_ocr),
                            db_conversion.markdown_content,
                        )
                        success_payload = ConversionResponse(
                            success=True,
                            message="Conversion successful.",
                            markdown=db_conversion.markdown_content,
                            image_paths=image_paths,
                            cached=False,
                            file_hash=file_hash,
                        )
                        return Response(
                            content=success_payload.model_dump_json(),
                            status_code=status.HTTP_200_OK,
                            media_type="application/json",
                        )
                    else:
                        logger.error(
                            f"Task {task_id} succeeded but result not found in DB for hash {file_hash}"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail="Conversion result not found.",
                        )
                else:
                    logger.error(
                        f"Task {task_id} succeeded but file_hash missing in result data."
                    )
                    missing_hash_payload = ConversionResponse(
                        success=False,
                        message="Internal error retrieving conversion result.",
                        error="Missing file hash in task result.",
                    )
                    return Response(
                        content=missing_hash_payload.model_dump_json(),
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        media_type="application/json",
                    )

            else:
                error_info = (
                    result_data.get("data", {}).get("error", "Unknown error")
                    if result_data
                    else "Unknown error"
                )
                logger.error(
                    f"Task {task_id} completed with status FAILURE: {error_info}"
                )
                internal_failure_payload = ConversionResponse(
                    success=False, message="Conversion failed.", error=error_info
                )
                return Response(
                    content=internal_failure_payload.model_dump_json(),
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    media_type="application/json",
                )
        else:
            try:
                error_info = (
                    str(task_result.info)
                    if task_result.info
                    else "Unknown task failure"
                )
            except Exception:
                error_info = "Unknown task failure (could not retrieve info)"
            logger.error(f"Task {task_id} failed: {error_info}")
            exception_failure_payload = ConversionResponse(
                success=False, message="Conversion failed.", error=error_info
            )
            return Response(
                content=exception_failure_payload.model_dump_json(),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                media_type="application/json",
            )
    else:
        return Response(status_code=status.HTTP_202_ACCEPTED)


@router.get("/queue/status", response_model=QueueStatusResponse)
async def get_queue_status(db: Session = Depends(get_db)):
    pending_count = count_pending_conversions(db)
    return QueueStatusResponse(pending_tasks=pending_count)


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "llm_available": settings.llm_available,
        "torch_device": settings.TORCH_DEVICE,
        "version": settings.API_VERSION,
    }


@router.get("/view/{file_hash}", response_class=HTMLResponse)
async def view_conversion(
    request: Request,
    file_hash: str,
    use_llm: bool = Query(False),
    paginate_output: bool = Query(False),
    extract_images: bool = Query(True),
    force_ocr: bool = Query(False),
    db: Session = Depends(get_db),
):
    """
    Retrieves a completed conversion and renders its Markdown content as HTML.
    """
    logger.info(
        f"Request to view conversion for hash: {file_hash} with params: llm={use_llm}, paginate={paginate_output}, images={extract_images}, ocr={force_ocr}"
    )

    conversion: Optional[db_models.ConversionCache] = (
        db_get_conversion_by_hash_and_params(
            db, file_hash, use_llm, paginate_output, extract_images, force_ocr
        )
    )

    if not conversion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversion with specified hash and parameters not found.",
        )

    if conversion.status != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Conversion is not complete. Current status: {conversion.status}",
        )

    markdown_content = conversion.markdown_content or ""
    original_filename = conversion.original_filename or "Converted Document"

    def replace_image_path(match):
        alt_text = match.group(1)
        original_path = match.group(2)

        # Construct the correct web-accessible path
        # URL should be /uploads/<file_hash>/images/<original_path>
        new_path = f"/uploads/{file_hash}/images/{original_path.lstrip('/')}"

        logger.debug(f"Rewriting image path: '{original_path}' -> '{new_path}'")
        return f"![{alt_text}]({new_path})"

    # Use regex to find Markdown image tags where the path is not an absolute URL
    # This regex finds ![alt](path) where path does NOT start with http(s)://

    modified_markdown = re.sub(
        r"!\[(.*?)\]\(((?!https?://)[^)]+)\)", replace_image_path, markdown_content
    )

    html_content = markdown2.markdown(
        modified_markdown,
        extras=["tables", "fenced-code-blocks", "strike", "code-friendly", "task_list"],
    )

    return templates.TemplateResponse(
        "view.html",
        {"request": request, "filename": original_filename, "content": html_content},
    )
