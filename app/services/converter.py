import os
import logging
import json
from typing import Dict, Any, Optional, List
from pathlib import Path

from sqlalchemy.orm import Session
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
from marker.config.parser import ConfigParser
from PIL import Image

from app.celery_app import celery_app
from app.core.config import settings
from app.db.base import SessionLocal
from app.db import crud

logger = logging.getLogger("pdf2md.converter")

IMAGE_STORAGE_BASE = Path("uploads")


def get_converter(
    use_llm: bool = False,
    force_ocr: bool = False,
    extract_images: bool = True,
    paginate_output: bool = False,
) -> PdfConverter:
    """
    Create and configure a PdfConverter instance

    Args:
        use_llm: Whether to use LLM for improved conversion
        force_ocr: Whether to force OCR processing on the entire document
        extract_images: Whether to extract images from the PDF
        paginate_output: Whether to paginate the output

    Returns:
        PdfConverter: Configured converter instance
    """
    config = {
        "output_format": "markdown",
        "use_llm": use_llm,
        "force_ocr": force_ocr,
        "disable_image_extraction": not extract_images,
        "paginate_output": paginate_output,
    }

    if use_llm:
        if "GOOGLE_API_KEY" in os.environ:
            config["gemini_api_key"] = os.environ["GOOGLE_API_KEY"]
        if "OPENAI_API_KEY" in os.environ:
            config["openai_api_key"] = os.environ["OPENAI_API_KEY"]
        if "CLAUDE_API_KEY" in os.environ:
            config["claude_api_key"] = os.environ["CLAUDE_API_KEY"]
        if "VERTEX_PROJECT_ID" in os.environ:
            config["vertex_project_id"] = os.environ["VERTEX_PROJECT_ID"]

    config_parser = ConfigParser(config)

    llm_service = config_parser.get_llm_service() if use_llm else None

    return PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=create_model_dict(),
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=llm_service,
    )


@celery_app.task(bind=True)
def convert_pdf_task(
    self,
    temp_file_path: str,
    file_hash: str,
    original_filename: str,
    use_llm: bool = False,
    force_ocr: bool = False,
    extract_images: bool = True,
    paginate_output: bool = False,
) -> Dict[str, Any]:
    logger.info(
        f"Starting conversion task {self.request.id} for {original_filename} ({temp_file_path})"
    )
    logger.info(
        f"Parameters: use_llm={use_llm}, force_ocr={force_ocr}, extract_images={extract_images}, paginate_output={paginate_output}"
    )

    base_storage_path = Path(settings.STORAGE_PATH)
    image_output_dir = base_storage_path / IMAGE_STORAGE_BASE / file_hash / "images"

    result_data: Dict[str, Optional[Any]] = {
        "file_hash": file_hash,
        "original_filename": original_filename,
        "use_llm": use_llm,
        "force_ocr": force_ocr,
        "extract_images": extract_images,
        "paginate_output": paginate_output,
        "markdown": None,
        "metadata": None,
        "image_paths": None,
        "error": None,
    }
    saved_image_paths: List[str] = []  # List to store relative paths of saved images

    db: Session = SessionLocal()

    try:
        if not os.path.exists(temp_file_path):
            raise FileNotFoundError(f"Temporary file not found: {temp_file_path}")

        converter = get_converter(
            use_llm=use_llm,
            force_ocr=force_ocr,
            extract_images=extract_images,
            paginate_output=paginate_output,
        )

        rendered = converter(temp_file_path)
        text, metadata, images_data = text_from_rendered(rendered)

        if extract_images and images_data:
            try:
                image_output_dir.mkdir(parents=True, exist_ok=True)
                logger.info(
                    f"Saving images for task {self.request.id} to {image_output_dir}"
                )

                # Assuming images_data is a dict {filename: PIL.Image}
                # Adjust if marker-pdf returns a different structure
                if isinstance(images_data, dict):
                    for img_filename, img_obj in images_data.items():
                        if isinstance(img_obj, Image.Image):
                            safe_filename = img_filename.replace(" ", "_")
                            save_path = image_output_dir / safe_filename
                            img_obj.save(save_path)
                            relative_path = str(
                                Path(file_hash) / "images" / safe_filename
                            )
                            saved_image_paths.append(relative_path)
                        else:
                            logger.warning(
                                f"Item '{img_filename}' in images_data is not a PIL Image object."
                            )
                else:
                    logger.warning(
                        f"Expected images_data to be a dict, but got {type(images_data)}. Cannot save images."
                    )

            except Exception as img_err:
                logger.error(
                    f"Error saving images for task {self.request.id}: {img_err}",
                    exc_info=True,
                )

        page_marker = getattr(settings, "PAGE_NUMBER", "{PAGE_NUMBER}")
        if (
            paginate_output
            and hasattr(rendered, "metadata")
            and "page_stats" in rendered.metadata
        ):
            page_count = len(rendered.metadata["page_stats"])
            paginated_text = ""

            separator = f"\n\n{page_marker}\n\n"
            page_texts = text.split(separator)

            for i, page_text in enumerate(page_texts):
                # Add page number header before the segment for all pages if splitting occurred
                # Or only for page 2 onwards if the first segment shouldn't have a header
                if i > 0:  # Add header starting from the second segment (Page 2)
                    paginated_text += (
                        f"\n\n## Page {i + 1}\n\n"  # Use i+1 for 1-based numbering
                    )
                paginated_text += page_text.strip()

            text = paginated_text.strip()

        result_data["markdown"] = text
        result_data["metadata"] = metadata
        result_data["image_paths"] = saved_image_paths

        try:
            crud.create_conversion(
                db=db,
                file_hash=file_hash,
                original_filename=original_filename,
                markdown_content=text,
                use_llm=use_llm,
                paginate_output=paginate_output,
                extract_images=extract_images,
                force_ocr=force_ocr,
                status="COMPLETED",
                image_paths=saved_image_paths,
            )
            logger.info(f"Conversion result for task {self.request.id} saved to DB.")
        except Exception as db_err:
            logger.error(
                f"Failed to save result to DB for task {self.request.id}: {db_err}",
                exc_info=True,
            )

        logger.info(
            f"Conversion task {self.request.id} completed successfully for {original_filename}"
        )

        return {"status": "SUCCESS", "data": result_data}

    except Exception as e:
        logger.error(
            f"Conversion task {self.request.id} failed for {original_filename} ({temp_file_path}): {e}",
            exc_info=True,
        )
        result_data["error"] = str(e)
        self.update_state(
            state="FAILURE", meta={"exc_type": type(e).__name__, "exc_message": str(e)}
        )
        return {"status": "FAILURE", "data": result_data}

    finally:
        db.close()
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(
                    f"Removed temporary file: {temp_file_path} (Task ID: {self.request.id})"
                )
            except OSError as rm_err:
                logger.error(
                    f"Error removing temporary file {temp_file_path}: {rm_err}",
                    exc_info=True,
                )
