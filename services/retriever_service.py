from rag.retriever import Retriever
from services.embedding_service import EmbeddingService
from pathlib import Path
from config.settings import settings
from utils.logger import logger


class RetrieverService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.retriever = Retriever(EmbeddingService())
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.cache = {}
        self._initialized = True

    def is_duplicate(self, hash_value):
        """Check if the document hash already exists."""
        return hash_value in self.retriever.uploaded_hashes

    def get_document_id(self, hash_value):
        """Return the document ID associated with a file hash."""
        return self.retriever.hash_to_doc_id.get(hash_value)

    def store_document(self, chunks, hash_value, filename, file_path, document_id):
        """Store document chunks in the vector database."""
        self.retriever.add_chunks(chunks)
        self.retriever.register_document(document_id, hash_value, filename, str(file_path))
        return document_id

    def cache_response(self, query, answer, sources):
        """Cache the response for a query."""
        self.cache[query] = {"answer": answer, "sources": sources}

    def get_cached_response(self, query):
        """Retrieve a cached response for a query."""
        return self.cache.get(query)

    def delete_document(self, document_id):
        """Delete a document from disk and the vector database."""
        try:
            metadata = self.retriever.document_metadata.get(document_id)
            if metadata is None:
                return False

            upload_dir = (Path.cwd() / settings.upload_dir).resolve()
            file_path = Path(metadata.get("file_path", "")).resolve()
            if upload_dir not in file_path.parents:
                logger.error(f"Refusing to delete file outside upload directory: {file_path}")
                return False

            if file_path.exists():
                file_path.unlink()

            if not self.retriever.delete_document(document_id):
                logger.error(f"Document {document_id} was not present in retriever index")
                return False
            return True
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            return False

    def remove_from_vector_db(self, document_id):
        """Remove a document from the vector database without deleting the file."""
        try:
            if document_id not in self.retriever.document_metadata:
                return False
            return self.retriever.delete_document(document_id)
        except Exception as e:
            logger.error(f"Failed to remove document {document_id} from vector DB: {e}")
            return False
