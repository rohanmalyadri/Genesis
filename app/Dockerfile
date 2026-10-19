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

# Install dependencies first (cached), then the app source
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

RUN useradd -m appuser && mkdir -p /app/chroma_db && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
