import os
import logging
from typing import Dict, Any, Tuple

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
from marker.config.parser import ConfigParser

logger = logging.getLogger("pdf2md.converter")

def get_converter(
    use_llm: bool = False, 
    force_ocr: bool = False, 
    extract_images: bool = True, 
    paginate_output: bool = False
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
    # Create config dictionary with our parameters
    config = {
        "output_format": "markdown",
        "use_llm": use_llm,
        "force_ocr": force_ocr,
        "disable_image_extraction": not extract_images,
        "paginate_output": paginate_output
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
        llm_service=llm_service
    )

def convert_pdf(
    file_path: str,
    use_llm: bool = False,
    force_ocr: bool = False,
    extract_images: bool = True,
    paginate_output: bool = False
) -> Tuple[str, Dict[str, Any]]:
    """
    Convert a PDF file to Markdown
    
    Args:
        file_path: Path to the PDF file
        use_llm: Whether to use LLM for improved conversion
        force_ocr: Whether to force OCR processing
        extract_images: Whether to extract images
        paginate_output: Whether to paginate the output
        
    Returns:
        Tuple[str, Dict[str, Any]]: Markdown text and metadata
    """
    logger.info(f"Starting conversion of {file_path}")
    logger.info(f"Parameters: use_llm={use_llm}, force_ocr={force_ocr}, extract_images={extract_images}, paginate_output={paginate_output}")
    
    converter = get_converter(
        use_llm=use_llm,
        force_ocr=force_ocr,
        extract_images=extract_images,
        paginate_output=paginate_output
    )
    
    # Convert the PDF
    rendered = converter(file_path)
    
    # Extract the markdown text
    text, metadata, images = text_from_rendered(rendered)
    
    # Add pagination if requested
    if paginate_output and hasattr(rendered, 'metadata') and 'page_stats' in rendered.metadata:
        page_count = len(rendered.metadata['page_stats'])
        paginated_text = ""
        page_texts = text.split("\n\n{PAGE_NUMBER}\n\n")
        
        for i, page_text in enumerate(page_texts):
            if i > 0:  # Skip adding page number to the first segment
                paginated_text += f"\n\n## Page {i}\n\n"
            paginated_text += page_text
        
        text = paginated_text
    
    logger.info(f"Conversion completed for {file_path}")
    
    return text, {"metadata": metadata, "images": images}