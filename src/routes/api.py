from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from typing import List
import os
import shutil
from src.services.rag_service import rag_service
from src.config import settings
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["api"])


class QueryRequest(BaseModel):
    question: str
    k: int = 4


class QueryResponse(BaseModel):
    answer: str
    references: List[dict]
    context_used: int


@router.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """Query the RAG system with a question"""
    try:
        result = rag_service.query(request.question, k=request.k)
        return QueryResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file and add it to the vector database"""
    try:
        # Check file limit
        current_documents = rag_service.get_document_list()
        if len(current_documents) >= 20:
            raise HTTPException(status_code=400, detail="File upload limit reached. Maximum 20 files allowed.")

        # Save file to documents directory
        os.makedirs(settings.documents_dir, exist_ok=True)
        file_path = os.path.join(settings.documents_dir, file.filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Index the file
        result = rag_service.load_and_index_documents(file_path)
        
        return {
            "message": "File uploaded and indexed successfully",
            "filename": file.filename,
            "chunks": result["chunk_count"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


@router.get("/documents")
async def list_documents():
    """Get list of all documents"""
    try:
        documents = rag_service.get_document_list()
        return {"documents": documents}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")


@router.delete("/documents/{filename}")
async def delete_document(filename: str):
    """Delete a document"""
    try:
        success = rag_service.delete_document(filename)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete document")
        return {"message": f"Document {filename} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")


@router.get("/documents/{filename}")
async def get_document(filename: str):
    """Get a specific document file"""
    try:
        file_path = os.path.join(settings.documents_dir, filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Document not found")
        
        # For PDFs, return the file
        if filename.endswith('.pdf'):
            return FileResponse(
                file_path,
                media_type="application/pdf",
                filename=filename
            )
        # For text files, return content
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return {"filename": filename, "content": content}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving document: {str(e)}")

