FROM python:3.11-slim

WORKDIR /app

# System libraries: libmagic (file type detection), tesseract (OCR), poppler (PDF), build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmagic1 \
    tesseract-ocr \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies (cached layer), then the app source.
# PyTorch is NOT installed: embeddings run on the ONNX runtime to keep memory under 512 MB.
COPY pyproject.toml README.md ./
COPY app ./app
COPY routes ./routes
COPY services ./services
COPY retrieval ./retrieval
COPY agents ./agents
COPY pipeline ./pipeline
COPY security ./security
COPY prompts ./prompts
COPY tools ./tools
RUN pip install --no-cache-dir . \
    && python -m spacy download en_core_web_sm

# Download the embedding model at build time so the first request does not have to
ENV FASTEMBED_CACHE_PATH=/app/.cache/fastembed
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/all-MiniLM-L6-v2')"

COPY demo_docs ./demo_docs

RUN useradd -m appuser && mkdir -p /app/chroma_db && chown -R appuser:appuser /app
USER appuser

ENV PORT=8000
EXPOSE 8000

# Render sets $PORT; locally and in docker compose it defaults to 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
