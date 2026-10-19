from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.middleware import ApiGuardMiddleware
from routes import query, search, health, pagerank

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic (e.g., connect to Qdrant, Redis)
    print(f"Starting {settings.PROJECT_NAME}...")
    from services.semantic_cache import semantic_cache
    from retrieval.chroma_shard_manager import shard_manager
    await semantic_cache.init_index()
    await shard_manager.initialize_shards()
    yield
    # Shutdown logic
    print(f"Shutting down {settings.PROJECT_NAME}...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
    debug=settings.DEBUG
)

# CORS configuration (credentials are only allowed with an explicit origin list)
allow_all = "*" in settings.ALLOWED_HOSTS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all else settings.ALLOWED_HOSTS,
    allow_credentials=not allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ApiGuardMiddleware)

# Include routers
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(query.router, prefix=settings.API_V1_STR + "/query", tags=["Query"])
app.include_router(search.router, prefix=settings.API_V1_STR + "/search", tags=["Search"])
from routes import ingest
app.include_router(ingest.router, prefix=settings.API_V1_STR + "/ingest", tags=["Ingest"])
app.include_router(pagerank.router, prefix=settings.API_V1_STR + "/pagerank", tags=["PageRank"])

@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "version": "0.1.0",
        "docs": "/docs",
        "made_by": "Rohan Malyadri, Obscuron X Labs",
    }
