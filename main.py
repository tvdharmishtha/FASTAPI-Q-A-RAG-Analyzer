from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import os
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from contextlib import asynccontextmanager
import json

from config.settings import settings
from routes.upload import router as upload_router
from routes.query import router as query_router
from services.embedding_service import EmbeddingService
from services.llm_service import LLMService, clear_llm_cache
from services.retriever_service import RetrieverService
from models.response_models import AskResponse
from utils.logger import logger
from utils.source_utils import deduplicate_document_sources

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=settings.description
)
app.state.limiter = limiter

embedding_service = EmbeddingService()
llm_service = LLMService()
retriever_service = RetrieverService()
retriever = retriever_service.retriever


def find_cached_answer(question: str):
    return next((entry for entry in cache_storage if entry["question"] == question), None)


def store_cached_answer(question: str, answer: str, sources: list[str]):
    cache_storage.append({
        "question": question,
        "answer": answer,
        "sources": sources
    })


def clear_qa_cache() -> int:
    primary_entries_removed = len(cache_storage) + len(retriever_service.cache)
    cache_storage.clear()
    retriever_service.cache.clear()
    llm_entries_removed = clear_llm_cache()
    return max(primary_entries_removed, llm_entries_removed)


def strip_cache_prefix(answer: str) -> tuple[str, bool]:
    marker = "[Loaded from Cache]"
    if marker not in answer:
        return answer, False

    cleaned = answer.replace("⚡", "").replace("âš¡", "").replace(marker, "", 1).strip()
    return cleaned, True


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."}
    )


app.include_router(upload_router, prefix="/api", tags=["upload"])
app.include_router(query_router, prefix="/api", tags=["query"])

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return {"message": "Document Q&A RAG System API", "version": settings.version, "docs": "Visit /docs for Swagger UI"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/api/ask", response_model=AskResponse)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def ask_question(request: Request):
    from models.request_models import AskRequest
    body = await request.json()
    ask_request = AskRequest(**body)

    # Check cache first
    cached_response = find_cached_answer(ask_request.question)
    if cached_response:
        logger.info("Cache hit for query")
        return AskResponse(
            answer=cached_response["answer"],
            sources=cached_response.get("sources", []),
            cached=True
        )

    # Retrieve chunks from retriever
    retrieved_chunks = retriever.retrieve(
        ask_request.question,
        doc_ids=ask_request.doc_ids
    )

    if not retrieved_chunks:
        return AskResponse(
            answer="I don't know based on the provided documents",
            sources=[],
            cached=False
        )

    context_parts = []
    for chunk in retrieved_chunks:
        filename = chunk["metadata"].get("filename", "Unknown Document")
        context_parts.append(f"Document: {filename}\nContent: {chunk['content']}")
    context = "\n\n".join(context_parts)

    # Generate answer using LLM
    answer = llm_service.generate_answer(ask_request.question, context)

    if not answer:
        return AskResponse(
            answer="I don't know based on the provided documents",
            sources=[],
            cached=False
        )

    answer, llm_cache_hit = strip_cache_prefix(answer)

    sources = deduplicate_document_sources(retrieved_chunks)

    # Store the response in cache
    store_cached_answer(ask_request.question, answer, sources)

    logger.info(f"Processed ask: {ask_request.question}")

    return AskResponse(
        answer=answer,
        sources=sources,
        cached=llm_cache_hit
    )


# Track active WebSocket connections
active_connections = set()

@app.websocket("/ws/ask")
async def websocket_ask(websocket: WebSocket):
    client = websocket.client
    client_id = f"{client.host}:{client.port}"

    if client_id in active_connections:
        logger.warning(f"Duplicate WebSocket connection attempt from {client_id}")
        await websocket.close()
        return

    active_connections.add(client_id)
    logger.info(f"WebSocket connected: {client_id}")

    await websocket.accept()

    try:
        while True:
            logger.debug(f"Waiting for message from {client_id}")
            data = await websocket.receive_text()
            logger.debug(f"Message received from {client_id}: {data}")

            message = json.loads(data)
            question = message.get("question", "")
            doc_ids = message.get("doc_ids")

            if not question:
                logger.debug(f"No question provided by {client_id}")
                await websocket.send_json({"error": "Question is required"})
                continue

            cached_response = find_cached_answer(question)
            if cached_response:
                logger.info("WebSocket cache hit for query")
                await websocket.send_json({
                    "answer": cached_response["answer"],
                    "sources": cached_response.get("sources", []),
                    "cached": True,
                    "done": True
                })
                continue

            retrieved_chunks = retriever.retrieve(question, doc_ids=doc_ids)

            if not retrieved_chunks:
                logger.debug(f"No chunks retrieved for {client_id}")
                await websocket.send_json({
                    "answer": "I don't know based on the provided documents",
                    "sources": [],
                    "cached": False,
                    "done": True
                })
                continue

            context_parts = []
            for chunk in retrieved_chunks:
                filename = chunk["metadata"].get("filename", "Unknown Document")
                context_parts.append(f"Document: {filename}\nContent: {chunk['content']}")
            context = "\n\n".join(context_parts)

            answer_parts = []
            llm_cache_hit = False
            for chunk_text in llm_service.stream_answer(question, context):
                logger.debug(f"Sending chunk to {client_id}: {chunk_text[:50]}...")
                display_text, chunk_from_cache = strip_cache_prefix(chunk_text)
                llm_cache_hit = llm_cache_hit or chunk_from_cache
                answer_parts.append(display_text)
                if display_text:
                    await websocket.send_text(json.dumps({"chunk": display_text}))

            sources = deduplicate_document_sources(retrieved_chunks)
            store_cached_answer(question, "".join(answer_parts), sources)
            logger.debug(f"Sending sources to {client_id}")
            await websocket.send_json({"sources": sources, "cached": llm_cache_hit, "done": True})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket error ({client_id}): {e}")
        try:
            await websocket.send_json({"error": str(e)})
        except:
            pass
    finally:
        active_connections.remove(client_id)
        logger.info(f"WebSocket connection removed: {client_id}")


# Simulated cache storage
cache_storage = []

@app.post("/api/clear_cache")
async def clear_cache():
    try:
        entries_removed = clear_qa_cache()
        logger.info(f"Cache cleared ({entries_removed} entries removed)")
        return {"status": "success", "cleared_count": entries_removed}
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")


@app.post("/clear-cache")
async def clear_cache_legacy():
    response = await clear_cache()
    return {
        "success": response["status"] == "success",
        "entriesRemoved": response["cleared_count"],
    }
