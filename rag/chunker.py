from typing import List
from config.settings import settings
from utils.logger import logger


class DocumentChunker:
    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap

    def chunk_text(self, text: str, document_id: str, filename: str = "") -> List[dict]:
        """Split text into overlapping chunks."""
        if not text:
            logger.warning("Empty text provided to chunker")
            return []

        chunks = []
        start = 0
        chunk_id = 0
        step = self.chunk_size - self.chunk_overlap

        while start < len(text):
            end = min(start + self.chunk_size, len(text))

            chunk_text = text[start:end]
            chunk = {
                "id": f"{document_id}_chunk_{chunk_id}",
                "content": chunk_text,
                "metadata": {
                    "doc_id": document_id,
                    "filename": filename,
                    "chunk_id": chunk_id,
                    "start": start,
                    "end": end,
                }
            }
            chunks.append(chunk)

            # Move start position with overlap
            start += step
            if start >= len(text):
                break
            chunk_id += 1

        logger.info(f"Created {len(chunks)} chunks for document {document_id}")
        return chunks