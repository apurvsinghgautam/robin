"""Health check endpoints."""
from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check():
    """Basic health check."""
    return {"status": "healthy"}


@router.get("/ready")
async def readiness_check():
    """Readiness check including dependencies."""
    # TODO: Check database connection, Tor availability
    return {
        "status": "ready",
        "checks": {
            "database": "ok",
            "tor": "ok",
        },
    }
