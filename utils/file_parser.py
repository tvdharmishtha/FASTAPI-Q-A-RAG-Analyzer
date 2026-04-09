from typing import Optional
import os
from pathlib import Path
import json
import csv

try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

def parse_file(file_path: str) -> Optional[str]:
    if not os.path.exists(file_path):
        raise ValueError(f"File not found: {file_path}")

    file_extension = Path(file_path).suffix.lower()

    if file_extension == ".txt":
        return parse_txt(file_path)
    elif file_extension == ".pdf":
        return parse_pdf(file_path)
    elif file_extension == ".docx":
        return parse_docx(file_path)
    elif file_extension == ".csv":
        return parse_csv(file_path)
    elif file_extension == ".json":
        return parse_json(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")

def parse_txt(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise ValueError(f"Error parsing TXT file {file_path}: {e}")

def parse_pdf(file_path: str) -> Optional[str]:
    if not PDF_AVAILABLE:
        raise ImportError("PDF parsing not available. Install PyPDF2.")
    try:
        with open(file_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            return text
    except Exception as e:
        raise ValueError(f"Error parsing PDF file {file_path}: {e}")

def parse_docx(file_path: str) -> Optional[str]:
    if not DOCX_AVAILABLE:
        raise ImportError("DOCX parsing not available. Install python-docx.")
    try:
        doc = Document(file_path)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        raise ValueError(f"Error parsing DOCX file {file_path}: {e}")

def parse_csv(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            text = ""
            for row in reader:
                text += " ".join(row) + "\n"
            return text
    except Exception as e:
        raise ValueError(f"Error parsing CSV file {file_path}: {e}")

def parse_json(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            def extract_text(obj):
                if isinstance(obj, str):
                    return obj
                elif isinstance(obj, list):
                    return " ".join(extract_text(item) for item in obj)
                elif isinstance(obj, dict):
                    return " ".join(extract_text(value) for value in obj.values())
                else:
                    return str(obj)
            return extract_text(data)
    except Exception as e:
        raise ValueError(f"Error parsing JSON file {file_path}: {e}")