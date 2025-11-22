from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from src.routes.api import router as api_router
from src.config import settings
from src.services.rag_service import rag_service
import os
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    Initializes the vector database with documents on startup.
    """
    print("🚀 Starting up...")
    print(f"📂 Checking documents directory: {settings.documents_dir}")
    
    if os.path.exists(settings.documents_dir):
        print("🔄 Initializing vector database and indexing documents...")
        try:
            # Index all documents in the directory
            # This will create the collection if it doesn't exist
            result = rag_service.load_and_index_documents()
            print(f"✅ Successfully indexed {result['raw_count']} documents into {result['chunk_count']} chunks.")
            print(f"Files processed: {', '.join(result['files'])}")
        except Exception as e:
            print(f"❌ Error initializing database: {str(e)}")
    else:
        print(f"⚠️ Documents directory '{settings.documents_dir}' does not exist. Skipping initialization.")
    
    yield
    
    print("🛑 Shutting down...")

app = FastAPI(title="FAQ Support Bot API", version="1.0.0", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)

# Serve static files (frontend)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    """Serve the main frontend page"""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "FAQ Support Bot API", "status": "running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
