"""
Adult Learning Coaching Agent — FastAPI Application

This is the entry point for the backend. It:
1. Creates the FastAPI app instance
2. Configures CORS (so the React frontend can talk to us)
3. Registers route handlers
4. Sets up startup/shutdown lifecycle events

Run with:
    uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db

# IMPORTANT: Import models so SQLAlchemy registers them with Base.metadata
# before init_db() calls create_all(). Without this, no tables get created.
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic.

    Code before 'yield' runs on startup.
    Code after 'yield' runs on shutdown.

    This is FastAPI's modern replacement for @app.on_event("startup").
    """
    # --- Startup ---
    print("🚀 Starting Adult Learning Coaching Agent API...")
    await init_db()  # Create tables if they don't exist
    print("✅ Database tables created/verified")

    yield  # App is running, handling requests

    # --- Shutdown ---
    print("👋 Shutting down...")


app = FastAPI(
    title="Adult Learning Coaching Agent API",
    description="AI-powered instructional coaching for distance learning evaluation",
    version="1.0.0",
    lifespan=lifespan,
)

# --- CORS Middleware ---
# CORS = Cross-Origin Resource Sharing
# Without this, your React app (localhost:3000) can't call your API (localhost:8000)
# because browsers block requests between different origins by default.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Health Check Endpoints ---
# These exist so monitoring tools (and you) can verify the API is running.

@app.get("/", tags=["health"])
async def root():
    """Root endpoint — confirms the API is alive."""
    return {
        "service": "Adult Learning Coaching Agent",
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Detailed health check — verifies database connectivity.

    In production, load balancers hit this endpoint to decide
    whether to send traffic to this instance.
    """
    from sqlalchemy import text

    from app.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "environment": settings.APP_ENV,
    }
