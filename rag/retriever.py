from typing import List, Dict, Any, Optional
import numpy as np
import faiss
import os
import pickle
from config.settings import settings
from services.embedding_service import EmbeddingService
from utils.logger import logger


class Retriever:
    def __init__(self, embedding_service: EmbeddingService):
        self.embedding_service = embedding_service
        self.dimension = embedding_service.dimension
        self.index_file = "faiss_index.idx"
        self.data_file = "retriever_data.pkl"
        self.index: Optional[faiss.Index] = None
        self.chunk_map: Dict[int, Dict[str, Any]] = {}
        self.doc_id_to_indices: Dict[str, List[int]] = {}
        self.uploaded_hashes: set = set()
        self.hash_to_doc_id: Dict[str, str] = {}
        self.document_metadata: Dict[str, Dict[str, Any]] = {}
        self.load_persistent_data()

    def add_chunks(self, chunks: List[Dict[str, Any]]):
        if not chunks:
            return
            
        embeddings = []
        for chunk in chunks:
            embedding = self.embedding_service.generate_embedding(chunk["content"])
            if embedding is not None:
                embeddings.append(embedding)
            else:
                logger.warning(f"Failed to generate embedding for chunk {chunk['id']}")
        
        if not embeddings:
            logger.error("No valid embeddings generated")
            return
            
        embeddings_array = np.array(embeddings).astype('float32')
        
        if self.index is None:
            self.index = faiss.IndexFlatIP(self.dimension)
        
        self.index.add(embeddings_array)
        
        start_idx = len(self.chunk_map)
        for i, chunk in enumerate(chunks):
            chunk_idx = start_idx + i
            self.chunk_map[chunk_idx] = {
                "id": chunk["id"],
                "content": chunk["content"],
                "metadata": chunk["metadata"]
            }
            
            doc_id = chunk["metadata"].get("doc_id")
            if doc_id:
                if doc_id not in self.doc_id_to_indices:
                    self.doc_id_to_indices[doc_id] = []
                self.doc_id_to_indices[doc_id].append(chunk_idx)
        
        logger.info(f"Added {len(chunks)} chunks to FAISS index. Total: {self.index.ntotal}")
        self.save_persistent_data()

    def retrieve(self, query: str, top_k: int = None, doc_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        top_k = top_k or settings.top_k

        if self.index is None or self.index.ntotal == 0:
            logger.warning("FAISS index is empty")
            return []

        query_embedding = self.embedding_service.generate_embedding(query)
        if query_embedding is None:
            logger.error("Failed to generate embedding for query")
            return []

        query_vector = np.array([query_embedding]).astype('float32')
        scores, indices = self.index.search(query_vector, min(top_k * 3, self.index.ntotal))
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            if idx not in self.chunk_map:
                continue
                
            chunk_data = self.chunk_map[idx]
            chunk_doc_id = chunk_data["metadata"].get("doc_id")
            
            if doc_ids and chunk_doc_id not in doc_ids:
                continue
                
            results.append({
                "id": chunk_data["id"],
                "content": chunk_data["content"],
                "metadata": chunk_data["metadata"],
                "score": float(score)
            })
            
            if len(results) >= top_k:
                break
        
        logger.info(f"Retrieved {len(results)} chunks for query (doc_ids filter: {doc_ids})")
        return results

    def save_persistent_data(self):
        if self.index is not None:
            faiss.write_index(self.index, self.index_file)
        elif os.path.exists(self.index_file):
            os.remove(self.index_file)
        with open(self.data_file, 'wb') as f:
            pickle.dump({
                'chunk_map': self.chunk_map,
                'doc_id_to_indices': self.doc_id_to_indices,
                'uploaded_hashes': self.uploaded_hashes,
                'hash_to_doc_id': self.hash_to_doc_id,
                'document_metadata': self.document_metadata
            }, f)
        logger.info("Retriever data saved to disk")

    def load_persistent_data(self):
        if os.path.exists(self.index_file):
            self.index = faiss.read_index(self.index_file)
            logger.info("FAISS index loaded from disk")
        if os.path.exists(self.data_file):
            with open(self.data_file, 'rb') as f:
                data = pickle.load(f)
                self.chunk_map = data.get('chunk_map', {})
                self.doc_id_to_indices = data.get('doc_id_to_indices', {})
                self.uploaded_hashes = data.get('uploaded_hashes', set())
                self.hash_to_doc_id = data.get('hash_to_doc_id', {})
                self.document_metadata = data.get('document_metadata', {})
            logger.info("Retriever data loaded from disk")

    def register_document(self, document_id: str, hash_value: str, filename: str, file_path: str):
        self.uploaded_hashes.add(hash_value)
        self.hash_to_doc_id[hash_value] = document_id
        self.document_metadata[document_id] = {
            "hash": hash_value,
            "filename": filename,
            "file_path": file_path,
        }
        self.save_persistent_data()

    def delete_document(self, document_id: str) -> bool:
        indices_to_delete = set(self.doc_id_to_indices.get(document_id, []))
        if not indices_to_delete:
            indices_to_delete = {
                idx for idx, chunk in self.chunk_map.items()
                if chunk.get("metadata", {}).get("doc_id") == document_id
            }

        if not indices_to_delete and document_id not in self.document_metadata:
            return False

        remaining_chunks = [
            chunk for idx, chunk in sorted(self.chunk_map.items())
            if idx not in indices_to_delete
        ]

        self.index = None
        self.chunk_map = {}
        self.doc_id_to_indices = {}

        if remaining_chunks:
            embeddings = []
            indexed_chunks = []
            for chunk in remaining_chunks:
                embedding = self.embedding_service.generate_embedding(chunk["content"])
                if embedding is None:
                    logger.warning(f"Skipping chunk during delete rebuild: {chunk.get('id')}")
                    continue
                embeddings.append(embedding)
                indexed_chunks.append(chunk)

            if embeddings:
                self.index = faiss.IndexFlatIP(self.dimension)
                self.index.add(np.array(embeddings).astype("float32"))

                for idx, chunk in enumerate(indexed_chunks):
                    self.chunk_map[idx] = chunk
                    doc_id = chunk.get("metadata", {}).get("doc_id")
                    if doc_id:
                        self.doc_id_to_indices.setdefault(doc_id, []).append(idx)

        metadata = self.document_metadata.pop(document_id, None)
        if metadata:
            hash_value = metadata.get("hash")
            if hash_value:
                self.uploaded_hashes.discard(hash_value)
                self.hash_to_doc_id.pop(hash_value, None)

        self.save_persistent_data()
        logger.info(f"Deleted document {document_id} from retriever")
        return True
