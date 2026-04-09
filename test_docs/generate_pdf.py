from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

c = canvas.Canvas("sample.pdf", pagesize=letter)
width, height = letter

text = """FastAPI Q&A RAG System - Documentation

Introduction
This document provides an overview of the FastAPI Q&A RAG System. The system uses Retrieval-Augmented Generation (RAG) to answer questions based on uploaded documents.

Key Features
1. Document Upload: Supports PDF, TXT, DOCX, CSV, and JSON files
2. Chunking: Documents are split into chunks with 1000 chars and 200 overlap
3. Embeddings: Uses BAAI/bge-small-en-v1.5 for text embeddings
4. Vector Storage: Uses FAISS for efficient similarity search
5. LLM: Uses Groq mixtral-8x7b-32768 for answer generation
6. Caching: Both embeddings and LLM responses are cached
7. Rate Limiting: 10 requests per minute per user
8. Streaming: WebSocket support for streaming responses

Architecture
The system consists of:
- FastAPI backend
- FAISS vector store
- Groq LLM
- Embedding service
- File parser

API Endpoints
POST /api/upload - Upload documents
POST /api/query - Query documents (HTTP)
POST /api/ask - Query documents with doc_ids filter
GET /health - Health check

Usage Instructions
1. Start the server: uvicorn main:app --reload
2. Upload a document using /api/upload
3. Ask questions using /api/ask or /ws/ask

Rate Limits
The system allows 10 requests per minute per IP address."""

c.setFont("Helvetica", 12)
text_object = c.beginText(72, height - 72)
text_object.setFont("Helvetica", 12)

for line in text.split('\n'):
    text_object.textLine(line)

c.drawText(text_object)
c.showPage()
c.save()
print("PDF created: test_docs/sample.pdf")