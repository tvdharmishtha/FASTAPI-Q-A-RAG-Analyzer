from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class DocumentChunk(BaseModel):
    id: str
    content: str
    metadata: Dict[str, Any]
    score: Optional[float] = None


class Source(BaseModel):
    text: str
    doc_id: str
    score: float


class UploadResponse(BaseModel):
    message: str
    document_id: str
    chunks_count: int


class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: List[Source]


class AskResponse(BaseModel):
    answer: str
    sources: List[Source]
