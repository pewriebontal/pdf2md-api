import os
import uuid
import hashlib
import shutil
import logging
from pathlib import Path
from fastapi import UploadFile
from typing import Tuple

logger = logging.getLogger("pdf2md.file_service")

STORAGE_DIR = Path(
    os.path.abspath(
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage"
        )
    )
)
TEMP_DIR = STORAGE_DIR / "temp"
UPLOADS_DIR = STORAGE_DIR / "uploads"

# Create directories if they don't exist
TEMP_DIR.mkdir(exist_ok=True, parents=True)
UPLOADS_DIR.mkdir(exist_ok=True, parents=True)


def calculate_file_hash(file_path: Path) -> str:
    """
    Calculate SHA-256 hash of a file

    Args:
        file_path: Path to the file

    Returns:
        str: Hex digest of the file hash
    """
    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as f:
        # Read the file in chunks to avoid loading large files into memory
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()


async def save_upload_file(upload_file: UploadFile) -> Tuple[Path, str]:
    """
    Save an uploaded file to the temporary directory and calculate its hash

    Args:
        upload_file: The uploaded file object

    Returns:
        Tuple[Path, str]: Path to the saved file and its hash
    """
    # Create a unique name for the temporary file
    temp_file_id = str(uuid.uuid4())
    temp_file_path = TEMP_DIR / f"{temp_file_id}.pdf"

    # Save the uploaded file
    with open(temp_file_path, "wb") as f:
        content = await upload_file.read()
        f.write(content)

    # Reset the file pointer for potential future reads
    await upload_file.seek(0)

    # Calculate the file hash
    file_hash = calculate_file_hash(temp_file_path)
    logger.info(f"File hash for {upload_file.filename}: {file_hash}")

    return temp_file_path, file_hash


def store_file_permanently(temp_file_path: Path, file_hash: str) -> Path:
    """
    Move a file from temporary storage to permanent storage using its hash as the filename

    Args:
        temp_file_path: Path to the temporary file
        file_hash: Hash of the file to use as the filename

    Returns:
        Path: Path to the permanently stored file
    """
    permanent_file_path = UPLOADS_DIR / f"{file_hash}.pdf"

    # If the file already exists (same hash), no need to move
    if permanent_file_path.exists():
        logger.info(
            f"File with hash {file_hash} already exists at {permanent_file_path}"
        )
        # Simply delete the temp file
        if temp_file_path.exists():
            temp_file_path.unlink()
        return permanent_file_path

    # Move the file to permanent storage
    shutil.move(str(temp_file_path), str(permanent_file_path))
    logger.info(f"Moved file to permanent storage: {permanent_file_path}")

    return permanent_file_path


def cleanup_temp_file(file_path: Path) -> None:
    """
    Delete a temporary file if it exists

    Args:
        file_path: Path to the file to delete
    """
    try:
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Cleaned up temporary file: {file_path}")
    except Exception as e:
        logger.error(f"Error cleaning up file {file_path}: {str(e)}")
