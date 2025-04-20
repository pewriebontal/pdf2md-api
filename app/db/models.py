import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    UniqueConstraint,
    Index,
    JSON,
)
from .base import Base


class ConversionCache(Base):
    """Model for tracking and caching PDF to Markdown conversions"""

    __tablename__ = "conversion_cache"

    id = Column(Integer, primary_key=True, index=True)
    file_hash = Column(String(64), index=True, nullable=False)
    original_filename = Column(String(255))

    status = Column(String(50), default="PENDING", index=True, nullable=False)
    markdown_content = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    image_paths = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.datetime.utcnow)
    access_count = Column(Integer, default=0)

    use_llm = Column(Boolean, default=False, nullable=False)
    paginate_output = Column(Boolean, default=False, nullable=False)
    extract_images = Column(Boolean, default=True, nullable=False)
    force_ocr = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "file_hash",
            "use_llm",
            "paginate_output",
            "extract_images",
            "force_ocr",
            name="uix_conversion_params",
        ),
    )
