from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field


class ConversionRequest(BaseModel):
    """Model for PDF conversion request parameters"""

    use_llm: bool = Field(
        False, description="Whether to use LLM for enhanced conversion quality"
    )
    paginate_output: bool = Field(
        False, description="Whether to paginate the output by pages"
    )
    extract_images: bool = Field(
        True, description="Whether to extract images from the PDF"
    )
    force_ocr: bool = Field(
        False, description="Whether to force OCR processing on the entire document"
    )


class ConversionResponse(BaseModel):
    """Model for PDF conversion API response (Direct/Cached)"""

    success: bool
    message: str
    markdown: Optional[str] = None
    image_paths: Optional[List[str]] = None
    error: Optional[str] = None
    cached: bool = False
    file_hash: Optional[str] = None


class AsyncTaskResponse(BaseModel):
    """Model for response when a task is enqueued"""

    success: bool
    message: str
    task_id: Optional[str] = None
    file_hash: Optional[str] = None
    error: Optional[str] = None


class TaskStatusResponse(BaseModel):
    """Model for response when checking task status"""

    task_id: str
    status: str  # e.g., PENDING, STARTED, SUCCESS, FAILURE, RETRY, REVOKED
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    cached: bool = False


class QueueStatusResponse(BaseModel):
    """Response model for queue status."""

    pending_tasks: int = Field(
        ..., description="Estimated number of tasks waiting in the queue."
    )


class HealthResponse(BaseModel):
    """Model for health check response"""

    status: str
    llm_available: bool
    torch_device: str
    version: str
