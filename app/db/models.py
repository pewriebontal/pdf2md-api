import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, UniqueConstraint
from .base import Base

class ConversionCache(Base):
    """Model for caching PDF to Markdown conversions"""
    __tablename__ = "conversion_cache"

    id = Column(Integer, primary_key=True, index=True)
    file_hash = Column(String(64), index=True)  # Remove unique=True
    original_filename = Column(String(255))
    markdown_content = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.datetime.utcnow)
    access_count = Column(Integer, default=1)
    
    # Conversion parameters
    use_llm = Column(Boolean, default=False)
    paginate_output = Column(Boolean, default=False)
    extract_images = Column(Boolean, default=True)
    force_ocr = Column(Boolean, default=False)
    
    # Create a composite unique constraint
    __table_args__ = (
        UniqueConstraint('file_hash', 'use_llm', 'paginate_output', 'extract_images', 'force_ocr', 
                         name='uix_conversion_params'),
    )