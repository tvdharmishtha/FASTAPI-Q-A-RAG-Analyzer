from typing import List, Optional
import hashlib
from sentence_transformers import SentenceTransformer
from config.settings import settings
from utils.logger import logger

EMBEDDING_CACHE = {}
MAX_CACHE_SIZE = 5000


class EmbeddingService:
    def __init__(self):
        self.model = SentenceTransformer(settings.embedding_model)
        self.dimension = self.model.get_sentence_embedding_dimension()
        logger.info(f"Loaded embedding model: {settings.embedding_model}, dim: {self.dimension}")

    def _get_cache_key(self, text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        cache_key = self._get_cache_key(text)
        
        if cache_key in EMBEDDING_CACHE:
            logger.debug(f"Cache hit for embedding: {cache_key[:8]}...")
            return EMBEDDING_CACHE[cache_key]
        
        try:
            embeddings = self.model.encode([text])
            if len(embeddings) > 0:
                embedding = embeddings[0].tolist()
                if len(EMBEDDING_CACHE) >= MAX_CACHE_SIZE:
                    EMBEDDING_CACHE.clear()
                EMBEDDING_CACHE[cache_key] = embedding
                return embedding
            return None
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None

    def generate_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        try:
            embeddings = self.model.encode(texts)
            return [e.tolist() for e in embeddings]
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            return [None] * len(texts)
