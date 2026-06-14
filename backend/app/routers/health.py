"""
Health check endpoints.
"""
from fastapi import APIRouter

from backend.app.schemas import success_response

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns basic service status for monitoring and load balancer health checks.
    """
    return success_response(
        data={
            "status": "healthy",
            "service": "srt-flow"
        },
        message="Service is running"
    )


@router.get("/health/ready")
async def readiness_check():
    """
    Readiness check endpoint.
    
    Checks if the service is ready to accept requests.
    Can be extended to check database connectivity, etc.
    """
    # TODO: Add database connectivity check when database module is ready
    return success_response(
        data={
            "ready": True,
            "checks": {
                "database": "not_implemented",
                "queue": "not_implemented"
            }
        },
        message="Service is ready"
    )
