import os
from typing import List, Dict, Any
from langchain_community.document_loaders import (
    DirectoryLoader,
    TextLoader,
    PyPDFLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_qdrant import QdrantVectorStore
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from src.config import settings


class RAGService:
    def __init__(self):
        # Ensure API key is set as environment variable
        # LangChain Google GenAI components require GOOGLE_API_KEY env var
        if not settings.google_api_key:
            raise ValueError(
                "GOOGLE_API_KEY not found. Please set it in your .env file."
            )
        
        # Set environment variable - this is required for LangChain Google components
        os.environ["GOOGLE_API_KEY"] = settings.google_api_key
        
        # Initialize embeddings and LLM
        # They will automatically use GOOGLE_API_KEY from environment
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004"
        )
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash"
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        )
        self.vector_store = None
        self._initialize_vector_store()

    def _initialize_vector_store(self):
        """Initialize connection to Qdrant vector store"""
        # Create Qdrant client first
        self.qdrant_client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
        
        # Check if collection exists, create if it doesn't
        try:
            collections = self.qdrant_client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if settings.collection_name not in collection_names:
                print(f"Collection '{settings.collection_name}' not found. Creating it...")
                # Get embedding dimension
                try:
                    # Try to get dimension from a test embedding
                    test_embedding = self.embeddings.embed_query("test")
                    embedding_dim = len(test_embedding)
                except Exception as e:
                    print(f"Could not determine embedding dimension from model: {e}")
                    # Fallback for text-embedding-004
                    embedding_dim = 768
                
                self.qdrant_client.create_collection(
                    collection_name=settings.collection_name,
                    vectors_config=rest.VectorParams(
                        size=embedding_dim,
                        distance=rest.Distance.COSINE
                    )
                )
                print(f"Created collection '{settings.collection_name}' with dimension {embedding_dim}")
        except Exception as e:
            print(f"Error checking/creating collection: {e}")
            # We'll try to proceed, maybe it exists or will be created later
            pass
        
        # Create payload index for filename (required for deletion)
        try:
            self.qdrant_client.create_payload_index(
                collection_name=settings.collection_name,
                field_name="metadata.filename",
                field_schema=rest.PayloadSchemaType.KEYWORD,
            )
        except Exception:
            pass # Index might already exist or connection error

        # Initialize vector store with client
        self.vector_store = QdrantVectorStore(
            client=self.qdrant_client,
            collection_name=settings.collection_name,
            embedding=self.embeddings,
        )

    def load_and_index_documents(self, file_path: str = None) -> Dict[str, Any]:
        """Load documents from directory or specific file and index them"""
        if file_path:
            # Load single file
            if file_path.endswith('.pdf'):
                loader = PyPDFLoader(file_path)
            else:
                loader = TextLoader(file_path)
            raw_documents = loader.load()
        else:
            # Load all documents from directory
            loader = DirectoryLoader(settings.documents_dir)
            raw_documents = loader.load()

        # Add metadata for source tracking
        for doc in raw_documents:
            if not doc.metadata.get('source'):
                doc.metadata['source'] = doc.metadata.get('source', file_path or 'unknown')
            # Store original filename
            doc.metadata['filename'] = os.path.basename(doc.metadata.get('source', ''))

        # Split documents
        documents = self.text_splitter.split_documents(raw_documents)

        # Add to vector store
        if self.vector_store and documents:
            try:
                # Delete existing vectors for this file if updating (versioning)
                if file_path:
                    filename = os.path.basename(file_path)
                    try:
                        print(f"Removing existing vectors for '{filename}'...")
                        self.qdrant_client.delete(
                            collection_name=settings.collection_name,
                            points_selector=rest.FilterSelector(
                                filter=rest.Filter(
                                    must=[
                                        rest.FieldCondition(
                                            key="metadata.filename",
                                            match=rest.MatchValue(value=filename),
                                        )
                                    ]
                                )
                            ),
                        )
                    except Exception as e:
                        print(f"Warning: Could not delete existing vectors for {filename}: {e}")

                # Try to add documents
                self.vector_store.add_documents(documents)
            except Exception as e:
                # If collection doesn't exist, create it first
                if "doesn't exist" in str(e) or "not found" in str(e).lower():
                    # Create the collection first
                    # Get embedding dimension by embedding a test string
                    test_embedding = self.embeddings.embed_query("test")
                    embedding_dim = len(test_embedding)
                    
                    try:
                        self.qdrant_client.create_collection(
                            collection_name=settings.collection_name,
                            vectors_config=rest.VectorParams(
                                size=embedding_dim,
                                distance=rest.Distance.COSINE
                            )
                        )
                    except Exception as create_error:
                        # Collection might have been created by another process
                        if "already exists" not in str(create_error).lower() and "duplicate" not in str(create_error).lower():
                            raise
                    
                    # Now try adding documents again
                    self.vector_store.add_documents(documents)
                else:
                    raise

        return {
            "raw_count": len(raw_documents),
            "chunk_count": len(documents),
            "files": list(set([doc.metadata.get('filename', 'unknown') for doc in documents]))
        }

    def query(self, question: str, k: int = 4) -> Dict[str, Any]:
        """Query the RAG system and return answer with references"""
        if not self.vector_store:
            self._initialize_vector_store()

        # Check if collection exists
        try:
            collections = self.qdrant_client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if settings.collection_name not in collection_names:
                return {
                    "answer": "No documents have been indexed yet. Please upload and index some documents first.",
                    "references": [],
                    "context_used": 0
                }
        except Exception:
            # If we can't check, try to proceed anyway
            pass

        # Retrieve relevant documents
        try:
            print(f"Querying Qdrant for: {question}")
            retriever = self.vector_store.as_retriever(search_kwargs={"k": k})
            docs = retriever.invoke(question)
            print(f"Found {len(docs)} documents")
            for i, doc in enumerate(docs):
                print(f"Doc {i+1} preview: {doc.page_content[:100]}...")
        except Exception as e:
            print(f"Error during retrieval: {e}")
            if "doesn't exist" in str(e) or "not found" in str(e).lower():
                return {
                    "answer": "No documents have been indexed yet. Please upload and index some documents first.",
                    "references": [],
                    "context_used": 0
                }
            raise

        if not docs:
            return {
                "answer": "I couldn't find any relevant information in the documents to answer your question.",
                "references": [],
                "context_used": 0
            }

        # Prepare context with source information
        context_parts = []
        for i, doc in enumerate(docs):
            filename = doc.metadata.get('filename', os.path.basename(doc.metadata.get('source', 'unknown')))
            context_parts.append(f"[Source: {filename}]\n{doc.page_content}")
        context = "\n\n---\n\n".join(context_parts)

        # Create prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful assistant that answers questions based on the provided context.
            Format your response using HTML tags (e.g., <b>, <ul>, <li>, <p>, <br>).
            Do not include <html>, <head>, or <body> tags, just the content.
            When you use information from a source, DO NOT use inline citations in the text.
            Instead, list all unique references at the end of your answer in a separate section in the <li> tags.
            If the answer is not specifically mentioned in the context, respond with general knowledge and say you did not find the information in the context."""),
            ("human", """Context:
{context}

Question: {question}

Answer the question based on the context above using HTML formatting. List unique references at the end.""")
        ])

        # Create chain
        chain = (
            RunnablePassthrough()
            | prompt
            | self.llm
            | StrOutputParser()
        )

        # Get answer
        answer = chain.invoke({"context": context, "question": question})

        # Prepare references with metadata
        references = []
        seen_sources = set()
        for doc in docs:
            source = doc.metadata.get('source', 'unknown')
            filename = doc.metadata.get('filename', os.path.basename(source))
            page = doc.metadata.get('page', 0)
            
            # Use filename as unique identifier to prevent duplicate references from same file
            # (even if from different pages, showing the file once is usually sufficient for the UI)
            ref_id = filename
            
            if ref_id not in seen_sources:
                references.append({
                    "id": ref_id,
                    "filename": filename,
                    "source": source,
                    "page": page,
                    "preview": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
                })
                seen_sources.add(ref_id)

        return {
            "answer": answer,
            "references": references,
            "context_used": len(docs)
        }

    def delete_document(self, filename: str) -> bool:
        """Delete a document and its vectors"""
        try:
            # 1. Delete file from disk
            file_path = os.path.join(settings.documents_dir, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # 2. Delete vectors from Qdrant
            if self.vector_store:
                try:
                    # Ensure client is initialized
                    if not hasattr(self, 'qdrant_client'):
                        self._initialize_vector_store()
                        
                    print(f"Removing vectors for '{filename}'...")
                    self.qdrant_client.delete(
                        collection_name=settings.collection_name,
                        points_selector=rest.FilterSelector(
                            filter=rest.Filter(
                                must=[
                                    rest.FieldCondition(
                                        key="metadata.filename",
                                        match=rest.MatchValue(value=filename),
                                    )
                                ]
                            )
                        ),
                    )
                    return True
                except Exception as e:
                    print(f"Error deleting vectors: {e}")
                    return False
            return True
        except Exception as e:
            print(f"Error deleting document: {e}")
            return False

    def get_document_list(self) -> List[Dict[str, Any]]:
        """Get list of all indexed documents"""
        # This is a simplified version - in production you'd query Qdrant metadata
        documents = []
        if os.path.exists(settings.documents_dir):
            for filename in os.listdir(settings.documents_dir):
                filepath = os.path.join(settings.documents_dir, filename)
                if os.path.isfile(filepath):
                    documents.append({
                        "filename": filename,
                        "path": filepath,
                        "size": os.path.getsize(filepath)
                    })
        return documents


rag_service = RAGService()

