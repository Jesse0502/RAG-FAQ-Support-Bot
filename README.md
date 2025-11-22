# FAQ Support Bot

A full-stack RAG (Retrieval-Augmented Generation) FAQ support bot with a modern web interface. Built with FastAPI, LangChain, Google Generative AI (Gemini), and Qdrant.

## Features

- 🤖 **RAG-powered chatbot** - Ask questions about your documents and get AI-powered answers
- 📁 **File browser** - Browse and view documents in the sidebar
- 📄 **Document viewer** - View PDF and text files directly in the browser
- 📤 **File upload** - Upload your own documents and they'll be automatically indexed
- 🗑️ **File Management** - Upload and delete documents (with auto-reindexing)
- 🔗 **Source references** - Click on references to jump to the source document
- 💬 **Chat interface** - Modern, responsive chat UI with typing indicators

## Architecture

- **Backend**: FastAPI with RAG service using LangChain
- **Vector Database**: Qdrant for document embeddings
- **LLM**: Google Gemini 2.5 Flash
- **Frontend**: Custom HTML/CSS/JavaScript (served by FastAPI)

## Getting Started

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up your API keys

Create a `.env` file in the root directory:


### 3. Run the Application

```bash
uvicorn main:app --reload
```

## Project Structure

```
faqsupportbot/
├── main.py                 # FastAPI application entry point
├── src/
│   ├── config.py           # Configuration settings
│   ├── services/
│   │   └── rag_service.py  # RAG service implementation
│   └── routes/
│       └── api.py          # API endpoints
├── src/documents/          # Document storage directory
├── static/                 # Frontend assets
│   ├── index.html
│   ├── styles.css
│   └── script.js
├── Dockerfile              # Docker configuration
└── requirements.txt        # Python dependencies
```

## Deployment

This application is ready to be deployed on platforms like Railway, Render, or any Docker-compatible hosting service.

1.  **Push to GitHub**
2.  **Connect to Hosting Provider** (e.g., Railway)
3.  **Set Environment Variables** in the hosting dashboard

## Technologies

- **FastAPI** - High-performance web framework
- **LangChain** - Framework for building LLM applications
- **Qdrant** - Vector database for embeddings
- **Google Generative AI** - Gemini models for LLM and embeddings
- **Uvicorn** - ASGI server
