"""FastAPI main application"""
import sys
import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

# Import database initialization
from database import init_db

# Import routes
from routes.parking import router as parking_router

# Import services
from services.parking_detector import get_service as get_parking_service
from services.plate_detector import get_service as get_plate_service

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Smart Parking System",
    description="Real-time parking detection and vehicle plate recognition",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(parking_router)


def internal_detectors_enabled() -> bool:
    """Enable internal detector threads only when explicitly requested."""
    return os.getenv("ENABLE_INTERNAL_DETECTORS", "").strip().lower() in {"1", "true", "yes", "on"}


@app.on_event("startup")
async def startup_event():
    """Initialize database and optionally start detection services"""
    logger.info("Starting up Smart Parking System...")

    try:
        # Initialize database
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialized")

        if internal_detectors_enabled():
            logger.info("Starting parking detector service...")
            parking_service = get_parking_service()
            parking_service.start()

            logger.info("Starting plate detector service...")
            plate_service = get_plate_service()
            plate_service.start()

            logger.info("All services started successfully")
        else:
            logger.info("Internal detector services disabled; waiting for external parking4.py / plate4.py updates")
    except Exception as e:
        logger.error(f"Error during startup: {e}", exc_info=True)


@app.on_event("shutdown")
async def shutdown_event():
    """Stop detection services if they were started"""
    logger.info("Shutting down Smart Parking System...")

    try:
        if internal_detectors_enabled():
            parking_service = get_parking_service()
            parking_service.stop()

            plate_service = get_plate_service()
            plate_service.stop()

            logger.info("All services stopped")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Smart Parking System API",
        "docs": "/docs",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "ok",
        "service": "Smart Parking System"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
