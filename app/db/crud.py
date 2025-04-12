import datetime
from sqlalchemy.orm import Session
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
    return db.query(models.ConversionCache).filter(models.ConversionCache.file_hash == file_hash).first()

def get_conversion_by_hash_and_params(
    db: Session, 
    file_hash: str,
    use_llm: bool = False,
    paginate_output: bool = False,
    extract_images: bool = True,
    force_ocr: bool = False
):
    """
    Get cached conversion with matching parameters
    
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
    return db.query(models.ConversionCache).filter(
        models.ConversionCache.file_hash == file_hash,
        models.ConversionCache.use_llm == use_llm,
        models.ConversionCache.paginate_output == paginate_output,
        models.ConversionCache.extract_images == extract_images,
        models.ConversionCache.force_ocr == force_ocr
    ).first()

def create_conversion(
    db: Session, 
    file_hash: str, 
    original_filename: str, 
    markdown_content: str, 
    use_llm: bool = False,
    paginate_output: bool = False,
    extract_images: bool = True,
    force_ocr: bool = False
):
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
        
    Returns:
        ConversionCache: The created conversion cache entry
    """
    db_conversion = models.ConversionCache(
        file_hash=file_hash,
        original_filename=original_filename,
        markdown_content=markdown_content,
        use_llm=use_llm,
        paginate_output=paginate_output,
        extract_images=extract_images,
        force_ocr=force_ocr
    )
    db.add(db_conversion)
    db.commit()
    db.refresh(db_conversion)
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
    db_conversion = get_conversion_by_hash(db, file_hash)
    if db_conversion:
        db_conversion.last_accessed = datetime.datetime.utcnow()
        db_conversion.access_count += 1
        db.commit()
        db.refresh(db_conversion)
    return db_conversion