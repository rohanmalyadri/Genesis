import os
import re
import tempfile
import uuid

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.config import settings
from pipeline.ingest import ingest_pipeline

router = APIRouter()

CHUNK = 1024 * 1024


def _safe_name(filename: str) -> str:
    """Drop any directory part and unsafe characters from an uploaded filename."""
    name = os.path.basename((filename or "").replace("\\", "/"))
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(". ")
    return name or "upload"


@router.post("/")
async def ingest_document(
    file: UploadFile = File(...),
    use_sharding: bool = Form(True),
    skip_graph: bool = Form(False),
    chunk_size: int = Form(512),
):
    """
    Ingest a document into Genesis RAG.
    use_sharding=True uses the multi-tenant sharded index, otherwise the single
    enterprise collection. Graph extraction is skipped automatically if Neo4j is
    not available.
    """
    name = _safe_name(file.filename)
    ext = os.path.splitext(name)[1].lower()
    if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(settings.ALLOWED_UPLOAD_EXTENSIONS)}",
        )

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    tmp_dir = tempfile.mkdtemp(prefix="genesis_upload_")
    file_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}{ext}")

    try:
        size = 0
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(CHUNK):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=413, detail=f"File larger than {settings.MAX_UPLOAD_MB} MB")
                buffer.write(chunk)

        result = await ingest_pipeline.process_file(
            file_path, use_sharding=use_sharding, skip_graph=skip_graph,
            original_name=name, chunk_size=max(128, min(chunk_size, 2048)),
        )
        return {"filename": name, "sharded": use_sharding, **result}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        os.rmdir(tmp_dir)
