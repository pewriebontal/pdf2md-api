from typing import Optional
from pydantic import BaseModel, Field

class ConversionRequest(BaseModel):
    """Model for PDF conversion request parameters"""
    use_llm: bool = Field(False, description="Whether to use LLM for enhanced conversion quality")
    paginate_output: bool = Field(False, description="Whether to paginate the output by pages")
    extract_images: bool = Field(True, description="Whether to extract images from the PDF")
    force_ocr: bool = Field(False, description="Whether to force OCR processing on the entire document")

class ConversionResponse(BaseModel):
    """Model for PDF conversion API response"""
    success: bool
    message: str
    markdown: Optional[str] = None
    error: Optional[str] = None
    cached: bool = False
    file_hash: Optional[str] = None

class HealthResponse(BaseModel):
    """Model for health check response"""
    status: str
    llm_available: bool
    torch_device: str
    version: str