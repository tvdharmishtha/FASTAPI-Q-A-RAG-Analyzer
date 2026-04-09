# Document Q&A RAG System

A FastAPI backend for a document Q&A system using Retrieval-Augmented Generation (RAG) with Groq AI and fastembed for lightweight local embeddings.

## Features

- Upload documents (PDF, TXT, DOCX)
- Ask questions about uploaded documents
- Retrieve relevant information using embeddings
- Generate answers using LLM

## Architecture

- **Clean Architecture**: Separated concerns with layers (routes, services, RAG, models, utils)
- **Pydantic Models**: Type-safe request/response models
- **Modular Design**: Easily extensible components

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables:
   - Copy `.env` and fill in your Groq API key

3. Run the application:
   ```bash
   uvicorn main:app --reload
   ```

## API Endpoints

### Upload Document
- **POST** `/api/upload`
- Upload a document file to be processed and indexed

### Query Documents
- **POST** `/api/query`
- Query the system with a question
- Returns an answer based on relevant document chunks

## Usage

1. Start the server
2. Upload documents via `/api/upload`
3. Ask questions via `/api/query`

## Notes

- Documents are stored in-memory (for demo purposes)
- In production, use a persistent vector database
- Add authentication and rate limiting as needed