from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from typing import Annotated, Optional
import json

class Settings(BaseSettings):
    # API Configuration
    PROJECT_NAME: str = "Genesis RAG"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False

    # Infrastructure
    CHROMA_PERSIST_DIRECTORY: str = "chroma_db"
    NUM_SHARDS: int = 16
    REDIS_URL: str = "redis://localhost:6379"
    
    # AI Services
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3-flash-preview"
    GEMINI_PRO_MODEL: str = "gemini-3.1-pro-preview"
    
    # Observability
    OPIK_API_KEY: Optional[str] = None
    OPIK_HOST: str = "http://localhost:8080"
    OPIK_PROJECT_NAME: str = "genesis-rag"
    
    # RAG Tuning
    ROUTER_USE_LLM: bool = False   # classify queries with Gemini (costs one extra call per question)
    PAGERANK_ALPHA: float = 0.3
    COHERE_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    TAVILY_API_KEY: Optional[str] = None

    # Security
    # Origins allowed by CORS. Accepts "*", a comma separated list or a JSON list.
    ALLOWED_HOSTS: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    API_KEY: Optional[str] = None            # if set, every /api request needs X-API-Key
    RATE_LIMIT_PER_MINUTE: int = 120         # per client IP, 0 disables
    MAX_UPLOAD_MB: int = 25
    # Memory savers for small hosts (set these on Render's free plan)
    OUTPUT_GUARD_ENGINE: str = "presidio"   # "presidio" (spaCy based) or "regex" (light)
    EXTRACT_ENTITIES: bool = True            # spaCy entity tags on chunks (needs the spaCy model)
    GRAPH_ENABLED: bool = True               # Neo4j knowledge graph; False skips it entirely
    PDF_ENGINE: str = "pdfplumber"          # "pdfplumber" (tables as markdown) or "poppler" (pdftotext: much lighter)
    CHUNK_TOKENIZER: str = "approx"         # "approx" (4 chars per token) or "tiktoken" (exact, +40 MB)
    SEED_DEMO_DOCS: bool = False   # index demo_docs/ on startup when the knowledge base is empty
    ALLOWED_UPLOAD_EXTENSIONS: Annotated[list[str], NoDecode] = [
        ".pdf", ".docx", ".html", ".htm", ".txt", ".md", ".py", ".png", ".jpg", ".jpeg"
    ]
    
    # Graph Database
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # Relation Extraction
    ENTITY_ALIAS_MAP: dict[str, str] = {
        "usa": "United States",
        "u.s.": "United States",
        "u.s.a.": "United States",
        "ml": "Machine Learning",
        "ai": "Artificial Intelligence",
        "llm": "Large Language Model"
    }
    REBEL_MODEL_ID: str = "Babelscape/rebel-large"
    REBEL_CACHE_DIR: str = "/tmp/models"
    DOMAIN: str = "standard" # standard | medical | legal
    
    @field_validator("ALLOWED_HOSTS", "ALLOWED_UPLOAD_EXTENSIONS", mode="before")
    @classmethod
    def _split_list(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
