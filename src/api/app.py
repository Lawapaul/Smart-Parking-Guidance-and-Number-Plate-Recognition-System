"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router as parking_router
from src.utils.data_manager import init_db


app = FastAPI(
    title="Smart Parking System",
    description="Real-time parking detection and vehicle plate recognition backend",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parking_router)


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize database tables on startup."""
    init_db()


@app.get("/")
async def root() -> dict[str, str]:
    """Return a basic service message."""
    return {"message": "Smart Parking System API", "docs": "/docs", "version": "2.0.0"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Return service health."""
    return {"status": "ok", "service": "Smart Parking System"}
