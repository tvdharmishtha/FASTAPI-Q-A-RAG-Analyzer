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

@router.post("/upload", response_model=List[UploadResponse])
async def upload_documents(files: List[UploadFile] = File(...)):
    """Upload and process multiple documents."""
    responses = []
    for file in files:
        # Validate file type
        if file.filename.split('.')[-1].lower() not in [ext.strip('.') for ext in settings.allowed_extensions]:
            raise HTTPException(status_code=400, detail=f"Unsupported file type for {file.filename}")

        # Save file temporarily
        temp_path = Path(f"temp_{uuid.uuid4()}_{file.filename}")
        try:
            contents = await file.read()
            logger.info(f"Received file {file.filename} with size {len(contents)} bytes")
            with open(temp_path, "wb") as f:
                f.write(contents)

            hash_value = hashlib.md5(contents).hexdigest()
            if hash_value in retriever.uploaded_hashes:
                responses.append(UploadResponse(
                    message="Document already uploaded",
                    document_id=retriever.hash_to_doc_id.get(hash_value, ""),
                    chunks_count=0
                ))
                continue

            # Parse file
            logger.info(f"Parsing file {temp_path}")
            text = parse_file(str(temp_path))
            if not text:
                raise HTTPException(status_code=400, detail=f"Failed to parse file {file.filename}")
            logger.info(f"Parsed text length: {len(text)}")

            # Generate document ID
            document_id = str(uuid.uuid4())
            logger.info(f"Generated document ID: {document_id}")

            retriever.uploaded_hashes.add(hash_value)
            retriever.hash_to_doc_id[hash_value] = document_id

            # Chunk the document
            logger.info(f"Chunking text for document {document_id}")
            chunks = chunker.chunk_text(text, document_id)
            logger.info(f"Created {len(chunks)} chunks")

            # Add chunks to retriever
            logger.info(f"Adding chunks to retriever")
            retriever.add_chunks(chunks)

            logger.info(f"Document {file.filename} uploaded and processed with ID {document_id}")

            responses.append(UploadResponse(
                message="Document uploaded and processed successfully",
                document_id=document_id,
                chunks_count=len(chunks)
            ))

        except Exception as e:
            logger.error(f"Error uploading document {file.filename}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Internal server error for {file.filename}: {str(e)}")
        finally:
            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()

    return responses