from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
from pathlib import Path
import uuid
import hashlib
from config.settings import settings
from models.response_models import UploadResponse
from utils.file_parser import parse_file
from rag.chunker import DocumentChunker
from services.retriever_service import RetrieverService
from utils.logger import logger

router = APIRouter()

# Initialize services (in a real app, use dependency injection)
retriever_service = RetrieverService()
retriever = retriever_service.retriever
chunker = DocumentChunker()

PROJECT_ROOT = Path.cwd().resolve()
UPLOAD_DIR = (PROJECT_ROOT / settings.upload_dir).resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def safe_upload_path(document_id: str, filename: str) -> Path:
    safe_name = Path(filename).name.replace("\\", "_").replace("/", "_")
    upload_path = (UPLOAD_DIR / f"{document_id}_{safe_name}").resolve()
    if UPLOAD_DIR not in upload_path.parents:
        raise HTTPException(status_code=400, detail="Invalid upload path")
    return upload_path

@router.post("/upload", response_model=List[UploadResponse])
async def upload_documents(files: List[UploadFile] = File(...)):
    """Upload and process multiple documents."""
    responses = []
    for file in files:
        filename = Path(file.filename or "").name
        # Validate file type
        if filename.split('.')[-1].lower() not in [ext.strip('.') for ext in settings.allowed_extensions]:
            raise HTTPException(status_code=400, detail=f"Unsupported file type for {filename}")

        upload_path = None
        try:
            contents = await file.read()
            logger.info(f"Received file {filename} with size {len(contents)} bytes")
            if len(contents) > settings.max_file_size:
                raise HTTPException(status_code=413, detail=f"File too large: {filename}")

            # Check for duplicate uploads before writing another copy to disk.
            hash_value = hashlib.md5(contents).hexdigest()
            if retriever_service.is_duplicate(hash_value):
                responses.append(UploadResponse(
                    message="Document already uploaded",
                    document_id=retriever_service.get_document_id(hash_value) or "",
                    chunks_count=0,
                    filename=filename
                ))
                continue

            document_id = str(uuid.uuid4())
            upload_path = safe_upload_path(document_id, filename)
            with open(upload_path, "wb") as f:
                f.write(contents)

            # Parse file
            logger.info(f"Parsing file {upload_path}")
            text = parse_file(str(upload_path))
            if not text:
                raise HTTPException(status_code=400, detail=f"Failed to parse file {filename}")
            logger.info(f"Parsed text length: {len(text)}")

            # Chunk and store in vector database
            logger.info(f"Chunking and storing file {filename}")
            chunks = chunker.chunk_text(text, document_id=document_id, filename=filename)
            retriever_service.store_document(chunks, hash_value, filename, upload_path, document_id)

            responses.append(UploadResponse(
                message="Document uploaded successfully",
                document_id=document_id,
                chunks_count=len(chunks),
                filename=filename
            ))

        except Exception as e:
            if upload_path and upload_path.exists():
                upload_path.unlink()
            logger.error(f"Error uploading document {filename}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=500, detail=f"Internal server error for {filename}: {str(e)}")

    return responses

@router.delete("/files/{document_id}", response_model=dict)
async def delete_document(document_id: str):
    """Delete an uploaded document."""
    try:
        success = retriever_service.delete_document(document_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        return {"status": "success", "message": "Document deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete document")


@router.delete("/files/{document_id}/vector", response_model=dict)
async def remove_document_from_vector_db(document_id: str):
    """Remove an uploaded document from the vector database only."""
    try:
        success = retriever_service.remove_from_vector_db(document_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found in vector database")
        return {
            "status": "success",
            "message": "Removed file from vector database."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing document {document_id} from vector DB: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove document from vector database")


@router.delete("/delete/{document_id}", response_model=dict)
async def delete_document_legacy(document_id: str):
    """Backward-compatible delete route."""
    return await delete_document(document_id)
