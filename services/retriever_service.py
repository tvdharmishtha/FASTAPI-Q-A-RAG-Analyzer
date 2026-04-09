from rag.retriever import Retriever
from services.embedding_service import EmbeddingService


class RetrieverService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.retriever = Retriever(EmbeddingService())
        return cls._instance