"""API route modules."""
from .investigations import router as investigations_router
from .reports import router as reports_router
from .health import router as health_router

__all__ = ["investigations_router", "reports_router", "health_router"]
