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

        context = "\n\n".join([chunk["content"] for chunk in retrieved_chunks])
        answer = llm_service.generate_answer(request.query, context)

        if not answer:
            raise HTTPException(status_code=500, detail="Failed to generate answer")

        sources = [
            Source(
                text=chunk["content"],
                doc_id=chunk["metadata"].get("doc_id", ""),
                score=chunk["score"]
            )
            for chunk in retrieved_chunks
        ]

        logger.info(f"Processed query: {request.query}")

        return QueryResponse(
            query=request.query,
            answer=answer,
            sources=sources
        )

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")