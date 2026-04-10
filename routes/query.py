from fastapi import APIRouter, HTTPException
from models.request_models import QueryRequest
from models.response_models import QueryResponse
from services.llm_service import LLMService
from services.retriever_service import RetrieverService
from utils.logger import logger
from utils.source_utils import deduplicate_document_sources

router = APIRouter()

llm_service = LLMService()
retriever_service = RetrieverService()
retriever = retriever_service.retriever


@router.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    try:
        # Check cache for the query
        cached_response = retriever_service.get_cached_response(request.query)
        if cached_response:
            logger.info("Returning cached response")
            return QueryResponse(
                query=request.query,
                answer=cached_response['answer'],
                sources=cached_response['sources'],
                cached=True
            )

        # Retrieve relevant chunks
        retrieved_chunks = retriever.retrieve(request.query, request.top_k)

        if not retrieved_chunks:
            return QueryResponse(
                query=request.query,
                answer="No relevant information found in the documents.",
                sources=[],
                cached=False
            )

        # Generate context and answer
        context_parts = []
        for chunk in retrieved_chunks:
            context_parts.append(chunk["content"])
        context = "\n\n".join(context_parts)
        answer = llm_service.generate_answer(request.query, context)

        if not answer:
            raise HTTPException(status_code=500, detail="Failed to generate answer")

        sources = deduplicate_document_sources(retrieved_chunks)

        # Cache the response
        retriever_service.cache_response(request.query, answer, sources)

        logger.info(f"Processed query: {request.query}")

        return QueryResponse(
            query=request.query,
            answer=answer,
            sources=sources,
            cached=False
        )

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
