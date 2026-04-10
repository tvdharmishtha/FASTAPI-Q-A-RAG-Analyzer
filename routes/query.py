from fastapi import APIRouter, HTTPException
from models.request_models import QueryRequest
from models.response_models import QueryResponse, Source, DocumentChunk
from services.llm_service import LLMService
from services.retriever_service import RetrieverService
from utils.logger import logger

router = APIRouter()

llm_service = LLMService()
retriever_service = RetrieverService()
retriever = retriever_service.retriever


@router.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    try:
        retrieved_chunks = retriever.retrieve(request.query, request.top_k)

        if not retrieved_chunks:
            return QueryResponse(
                query=request.query,
                answer="No relevant information found in the documents.",
                sources=[]
            )

        context_parts = []
        for chunk in retrieved_chunks:
            filename = chunk["metadata"].get("filename", "Unknown Document")
            context_parts.append(f"Document: {filename}\nContent: {chunk['content']}")
        context = "\n\n".join(context_parts)
        answer = llm_service.generate_answer(request.query, context)

        if not answer:
            raise HTTPException(status_code=500, detail="Failed to generate answer")

        sources = []
        for chunk in retrieved_chunks:
            doc_meta_name = chunk["metadata"].get("filename") or chunk["metadata"].get("doc_id", "")
            # Truncate text to first 100 characters for concise display
            truncated_text = chunk["content"][:100] + "..." if len(chunk["content"]) > 100 else chunk["content"]
            sources.append(
                Source(
                    text=truncated_text,
                    doc_id=doc_meta_name,
                    score=chunk["score"]
                )
            )

        logger.info(f"Processed query: {request.query}")

        return QueryResponse(
            query=request.query,
            answer=answer,
            sources=sources
        )

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")