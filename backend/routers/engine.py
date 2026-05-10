"""Engine status endpoints — proxy to the Rust gRPC ukip-engine service."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.auth import get_current_user

router = APIRouter(prefix="/engine", tags=["engine"])


@router.get("/health")
async def engine_health(request: Request, _=Depends(get_current_user)):
    """Return engine availability status."""
    engine = getattr(request.app.state, "engine_client", None)
    if not engine:
        return {"engine_available": False, "message": "Engine not configured"}
    healthy = await engine.health()
    return {"engine_available": healthy}


@router.get("/jobs/{job_id}")
async def engine_job_status(
    job_id: str,
    request: Request,
    _=Depends(get_current_user),
):
    """Return the status of an async engine job."""
    engine = getattr(request.app.state, "engine_client", None)
    if not engine:
        raise HTTPException(status_code=404, detail="Engine not configured")
    status = await engine.get_job_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {
        "job_id": status.job_id,
        "status": status.status,
        "progress": status.progress,
    }
