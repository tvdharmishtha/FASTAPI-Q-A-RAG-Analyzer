from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
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
from services.llm_service import LLMService
from services.retriever_service import RetrieverService
from models.response_models import AskResponse, Source
from utils.logger import logger

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
    
    retrieved_chunks = retriever.retrieve(
        ask_request.question,
        doc_ids=ask_request.doc_ids
    )

    if not retrieved_chunks:
        return AskResponse(
            answer="I don't know based on the provided documents",
            sources=[]
        )

    context_parts = []
    for chunk in retrieved_chunks:
        filename = chunk["metadata"].get("filename", "Unknown Document")
        context_parts.append(f"Document: {filename}\nContent: {chunk['content']}")
    context = "\n\n".join(context_parts)
    
    answer = llm_service.generate_answer(ask_request.question, context)

    if not answer:
        return AskResponse(
            answer="I don't know based on the provided documents",
            sources=[]
        )

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

    logger.info(f"Processed ask: {ask_request.question}")

    return AskResponse(
        answer=answer,
        sources=sources
    )


@app.websocket("/ws/ask")
async def websocket_ask(websocket: WebSocket):
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            question = message.get("question", "")
            doc_ids = message.get("doc_ids")

            if not question:
                await websocket.send_json({"error": "Question is required"})
                continue

            retrieved_chunks = retriever.retrieve(question, doc_ids=doc_ids)

            if not retrieved_chunks:
                await websocket.send_json({
                    "answer": "I don't know based on the provided documents",
                    "sources": [],
                    "done": True
                })
                continue

            context_parts = []
            for chunk in retrieved_chunks:
                filename = chunk["metadata"].get("filename", "Unknown Document")
                context_parts.append(f"Document: {filename}\nContent: {chunk['content']}")
            context = "\n\n".join(context_parts)

            for chunk_text in llm_service.stream_answer(question, context):
                await websocket.send_text(json.dumps({"chunk": chunk_text}))

            sources = []
            for chunk in retrieved_chunks:
                doc_meta_name = chunk["metadata"].get("filename") or chunk["metadata"].get("doc_id", "")
                # Truncate text to first 100 characters for concise display
                truncated_text = chunk["content"][:100] + "..." if len(chunk["content"]) > 100 else chunk["content"]
                sources.append({
                    "text": truncated_text,
                    "doc_id": doc_meta_name,
                    "score": chunk["score"]
                })
                
            await websocket.send_json({"sources": sources, "done": True})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"error": str(e)})
        except:
            pass