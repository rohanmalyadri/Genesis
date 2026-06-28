import os
import shutil
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pipeline.ingest import ingest_pipeline
from app.config import settings

router = APIRouter()

@router.post("/")
async def ingest_document(
    file: UploadFile = File(...),
    use_sharding: bool = Form(True)
):
    """
    Ingest a document into the RAG system.
    If use_sharding is True, it uses the Multi-Tenant Sharding Architecture.
    If use_sharding is False, it uses the standard Enterprise RAG collection.
    """
    # Create temp directory if it doesn't exist
    temp_dir = os.path.join(os.getcwd(), "temp_uploads")
    os.makedirs(temp_dir, exist_ok=True)
    
    file_path = os.path.join(temp_dir, file.filename)
    
    try:
        # Save file locally for processing
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Run ingestion
        await ingest_pipeline.process_file(file_path, use_sharding=use_sharding)
        
        return {
            "filename": file.filename,
            "status": "success",
            "sharded": use_sharding
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
