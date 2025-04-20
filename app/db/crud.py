import datetime
import json
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from . import models


def get_conversion_by_hash(db: Session, file_hash: str):
    """
    Get cached conversion result by file hash

    Args:
        db: Database session
        file_hash: SHA-256 hash of the PDF file

    Returns:
        ConversionCache: The cached conversion if found, None otherwise
    """
    return (
        db.query(models.ConversionCache)
        .filter(models.ConversionCache.file_hash == file_hash)
        .first()
    )


def get_conversion_by_hash_and_params(
    db: Session,
    file_hash: str,
    use_llm: bool,
    paginate_output: bool,
    extract_images: bool,
    force_ocr: bool,
) -> Optional[models.ConversionCache]:
    """
    Retrieve a cached conversion based on file hash and all conversion parameters.

    Args:
        db: Database session
        file_hash: SHA-256 hash of the PDF file
        use_llm: Whether LLM was used
        paginate_output: Whether pagination was applied
        extract_images: Whether images were extracted
        force_ocr: Whether OCR was forced

    Returns:
        ConversionCache: The cached conversion if found, None otherwise
    """
    return (
        db.query(models.ConversionCache)
        .filter(
            models.ConversionCache.file_hash == file_hash,
            models.ConversionCache.use_llm == use_llm,
            models.ConversionCache.paginate_output == paginate_output,
            models.ConversionCache.extract_images == extract_images,
            models.ConversionCache.force_ocr == force_ocr,
        )
        .first()
    )


def create_conversion(
    db: Session,
    file_hash: str,
    original_filename: str,
    markdown_content: str,
    use_llm: bool = False,
    paginate_output: bool = False,
    extract_images: bool = True,
    force_ocr: bool = False,
    status: str = "COMPLETED",
    error_message: Optional[str] = None,
    image_paths: Optional[List[str]] = None,
) -> models.ConversionCache:
    """
    Create a new conversion cache entry

    Args:
        db: Database session
        file_hash: SHA-256 hash of the PDF file
        original_filename: Original filename of the PDF
        markdown_content: Converted markdown content
        use_llm: Whether LLM was used
        paginate_output: Whether pagination was applied
        extract_images: Whether images were extracted
        force_ocr: Whether OCR was forced
        status: Status of the conversion
        error_message: Error message if any
        image_paths: List of image file paths

    Returns:
        ConversionCache: The created conversion cache entry
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    image_paths_json = json.dumps(image_paths) if image_paths else None

    db_conversion = models.ConversionCache(
        file_hash=file_hash,
        original_filename=original_filename,
        status=status,
        markdown_content=markdown_content,
        error_message=error_message,
        image_paths=image_paths_json,
        created_at=now,
        last_accessed=now,
        access_count=1,
        use_llm=use_llm,
        paginate_output=paginate_output,
        extract_images=extract_images,
        force_ocr=force_ocr,
    )
    db.add(db_conversion)
    try:
        db.commit()
        db.refresh(db_conversion)
    except Exception as e:
        db.rollback()
        raise e
    return db_conversion


def update_conversion_access(db: Session, file_hash: str):
    """
    Update last accessed time and increment access count

    Args:
        db: Database session
        file_hash: SHA-256 hash of the PDF file

    Returns:
        ConversionCache: The updated conversion cache entry
    """
    db_conversion = (
        db.query(models.ConversionCache)
        .filter(models.ConversionCache.file_hash == file_hash)
        .first()
    )
    if db_conversion:
        db_conversion.last_accessed = datetime.datetime.now(datetime.timezone.utc)
        db_conversion.access_count = (db_conversion.access_count or 0) + 1
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Error updating access stats for {file_hash}: {e}")
    return db_conversion


def count_pending_conversions(db: Session) -> int:
    """
    Count the number of conversion tasks currently in PENDING status.
    """
    return (
        db.query(models.ConversionCache)
        .filter(models.ConversionCache.status == "PENDING")
        .count()
    )
