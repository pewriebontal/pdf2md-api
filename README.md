# PDF to Markdown Converter

A minimalist tool for converting PDF documents to clean Markdown format.

## Overview

PDF to Markdown provides a simple interface for converting PDFs to properly formatted Markdown. The service uses an intelligent caching system that stores converted documents based on file hashes to avoid redundant processing.

## Features

- Clean PDF to Markdown conversion with proper handling of tables, lists, and formatting
- File hash-based intelligent caching system
- Multiple conversion options:
  - LLM enhancement (with server-side API key)
  - Pagination
  - Image extraction
  - OCR processing
- Responsive design that works on desktop, tablet, and mobile devices

## Technology Stack

- Backend: Python with FastAPI
- Database: SQLite with SQLAlchemy
- Frontend: HTML/CSS/JavaScript

## Installation

```bash
# Clone the repository
git clone https://github.com/pewriebontal/pdf2md-api
cd pdf2md-api

# Set up a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create necessary directories
mkdir -p storage/temp storage/uploads storage/logs

# Run the application
python run.py
```

## Usage

1. Access the application at `http://localhost:8000`
2. Upload a PDF file via drag & drop or file selection
3. Configure conversion settings if needed
4. Convert the file
5. Download or copy the resulting Markdown

## API Endpoints

- `GET /`: Web interface
- `POST /convert`: Convert PDF to Markdown
- `GET /health`: Health check endpoint

## Environment Variables

Create a `.env` file in the project root with the following variables:

```
# Server settings
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=development  # or production

# Optional LLM integration
# GOOGLE_API_KEY=your_api_key
# OPENAI_API_KEY=your_api_key
# CLAUDE_API_KEY=your_api_key
```

## License

PRIVATE
