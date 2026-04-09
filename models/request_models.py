from pydantic import BaseModel
from typing import Optional, List


class AskRequest(BaseModel):
    question: str
    doc_ids: Optional[List[str]] = None


class UploadRequest(BaseModel):
    file_name: str
    content: bytes


class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5
