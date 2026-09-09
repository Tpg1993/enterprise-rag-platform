"""FastAPI Main Application Entrypoint."""

import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root (without overriding explicitly set environment variables)
env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=False)
else:
    load_dotenv(override=False)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.middleware import RequestContextMiddleware
from src.api.routes.chat import router as chat_router
from src.api.routes.documents import router as documents_router
from src.api.routes.health import router as health_router
from src.api.routes.traces import router as traces_router
from src.config.loader import load_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

settings = load_settings()

app = FastAPI(
    title="Enterprise Multi-Architecture RAG & Agentic AI Platform",
    description=(
        "Production-grade modular RAG platform powered by Sarvam AI, "
        "LangChain, LangGraph, and LangSmith."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middleware
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
from fastapi.staticfiles import StaticFiles

from src.api.routes.evaluations import router as evaluations_router

# API v1 Routers
app.include_router(health_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(evaluations_router, prefix="/api/v1")
app.include_router(traces_router)

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/ui", StaticFiles(directory=frontend_dir, html=True), name="ui")


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "title": "Enterprise Multi-Architecture RAG Platform API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
        "ui": "/ui",
    }
