"""Engine status endpoints — proxy to the Rust gRPC ukip-engine service."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.auth import require_role
from backend.services.engine_delegation import ENGINE_DELEGATION_THRESHOLD

router = APIRouter(prefix="/engine", tags=["engine"])


@router.get("/health")
async def engine_health(request: Request, _=Depends(require_role("super_admin", "admin"))):
    """Return engine availability and registered pipeline info."""
    engine = getattr(request.app.state, "engine_client", None)
    if not engine:
        return {"engine_available": False, "message": "Engine not configured", "pipelines": []}

    if not await engine._ensure_channel():
        return {"engine_available": False, "message": "Engine unreachable", "pipelines": []}

    try:
        from backend.proto.ukip.engine.v1 import engine_pb2
        resp = await engine._stub.Health(
            engine_pb2.HealthRequest(),
            metadata=engine._metadata(),
            timeout=5,
        )
        pipelines = list(resp.pipelines) if hasattr(resp, "pipelines") else []
        delegation_status = {
            "analytics": "enabled" if resp.healthy else "fallback",
            "disambiguation": "enabled (threshold={})".format(ENGINE_DELEGATION_THRESHOLD) if resp.healthy else "fallback",
            "normalization": "enabled (threshold={})".format(ENGINE_DELEGATION_THRESHOLD) if resp.healthy else "fallback",
            "connectors": "opt-in" if resp.healthy else "fallback",
        }
        return {
            "engine_available": resp.healthy,
            "pipelines": pipelines,
            "delegation": delegation_status,
            "delegation_threshold": ENGINE_DELEGATION_THRESHOLD,
        }
    except Exception:
        return {"engine_available": False, "pipelines": [], "delegation": {}}


@router.get("/jobs/{job_id}")
async def engine_job_status(
    job_id: str,
    request: Request,
    _=Depends(require_role("super_admin", "admin")),
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
