"""
AmplifAI Backend — Main application entry point.

Startup order:
1. Configure logging
2. Start APScheduler (daily YouTube sync)
3. Mount API router

Shutdown order:
1. Stop APScheduler gracefully
"""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.api.v1.router import api_router
from src.scheduler.jobs import start_scheduler, stop_scheduler

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.APP_DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AmplifAI backend v%s [%s]", settings.APP_VERSION, settings.APP_ENV)
    start_scheduler()
    yield
    logger.info("Shutting down AmplifAI backend")
    stop_scheduler()


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="AmplifAI API",
    description="Facial Emotion Playlist Generator — Backend API",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(api_router)


@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "service": "AmplifAI", "version": settings.APP_VERSION}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}