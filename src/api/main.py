"""FastAPI application entry point.

Mounts all routers, configures CORS, registers startup/shutdown hooks,
and exposes health-check and OpenAPI documentation endpoints.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import calendar, content, profile, publish
from src.config import get_settings
from src.models.database import create_tables
from src.models.schemas import HealthResponse
from src.utils.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager.

    Runs startup tasks (DB init) before yielding, and shutdown cleanup after.

    Args:
        app: The FastAPI application instance.
    """
    logger.info(
        "app_startup", environment=settings.app_env, mock_mode=settings.use_mock_data
    )
    create_tables()
    yield
    logger.info("app_shutdown")


app = FastAPI(
    title="Autonomous Social Media Growth Agent",
    description=(
        "A production-grade multi-agent AI system for social media profile analysis, "
        "competitive intelligence, content calendar generation (with HITL review), "
        "content creation, and publishing."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not settings.is_production else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(
    profile.router, prefix="/api/v1/profile", tags=["Profile Intelligence"]
)
app.include_router(
    calendar.router, prefix="/api/v1/calendar", tags=["Content Calendar"]
)
app.include_router(
    content.router, prefix="/api/v1/content", tags=["Content Generation"]
)
app.include_router(publish.router, prefix="/api/v1/publish", tags=["Publishing"])


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    """Health check endpoint for load-balancers and monitoring.

    Returns:
        HealthResponse indicating system status and configured services.
    """
    return HealthResponse(
        status="ok",
        version="1.0.0",
        environment=settings.app_env,
        services={
            "llm": "groq" if settings.groq_api_key else "fallback",
            "database": "sqlite" if "sqlite" in settings.database_url else "postgres",
            "mock_mode": str(settings.use_mock_data),
            "publishing_enabled": str(settings.enable_publishing),
        },
    )


@app.get("/metrics", tags=["System"])
async def get_metrics() -> dict:
    """Return lightweight application metrics.

    Returns:
        Dict of runtime metric counts.
    """
    return {
        "status": "ok",
        "note": "Detailed per-agent metrics are available via the agent service layer.",
    }


if __name__ == "__main__":
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
