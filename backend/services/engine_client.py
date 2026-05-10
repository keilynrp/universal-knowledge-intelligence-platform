"""Async gRPC client for the Rust ukip-engine service."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class EngineClient:
    """Wraps gRPC calls to ukip-engine with graceful fallback on unavailability."""

    def __init__(self, grpc_url: str, auth_token: str = ""):
        self.grpc_url = grpc_url
        self.auth_token = auth_token
        self._channel = None
        self._stub = None

    async def _ensure_channel(self) -> bool:
        if not self.grpc_url:
            return False
        if self._channel is None:
            try:
                import grpc.aio
                self._channel = grpc.aio.insecure_channel(self.grpc_url)
                from backend.proto.ukip.engine.v1 import engine_pb2_grpc
                self._stub = engine_pb2_grpc.EngineStub(self._channel)
            except Exception as exc:
                logger.warning("Failed to connect to engine at %s: %s", self.grpc_url, exc)
                return False
        return True

    def _metadata(self) -> list[tuple[str, str]]:
        return [("x-engine-token", self.auth_token)] if self.auth_token else []

    async def health(self) -> bool:
        """Return True if the engine is reachable and healthy."""
        if not await self._ensure_channel():
            return False
        try:
            from backend.proto.ukip.engine.v1 import engine_pb2
            resp = await self._stub.Health(
                engine_pb2.HealthRequest(),
                metadata=self._metadata(),
                timeout=5,
            )
            return resp.healthy
        except Exception as exc:
            logger.debug("Engine health check failed: %s", exc)
            return False

    async def process_sync(
        self,
        *,
        pipeline: str,
        job_id: str,
        import_batch_id: int,
        domain: str,
        publications: list,
        org_id: int | None = None,
        options: dict | None = None,
    ) -> Any | None:
        """
        Call ProcessSync on the engine.

        Returns the proto ProcessResponse on success, None on failure.
        `publications` should be a list of proto Publication messages.
        """
        if not await self._ensure_channel():
            return None
        try:
            from backend.proto.ukip.engine.v1 import engine_pb2
            req = engine_pb2.ProcessRequest(
                pipeline=pipeline,
                job_id=job_id,
                import_batch_id=import_batch_id,
                domain=domain,
                publications=publications,
                options=options or {},
            )
            if org_id is not None:
                req.org_id = org_id
            resp = await self._stub.ProcessSync(
                req,
                metadata=self._metadata(),
                timeout=300,
            )
            return resp
        except Exception as exc:
            logger.error("Engine process_sync failed: %s", exc)
            return None

    async def process_async(
        self,
        *,
        pipeline: str,
        job_id: str,
        import_batch_id: int,
        domain: str,
        publications: list,
        org_id: int | None = None,
        options: dict | None = None,
    ) -> Any | None:
        """
        Call ProcessAsync on the engine (fire-and-forget).

        Returns the proto JobAccepted on success, None on failure.
        """
        if not await self._ensure_channel():
            return None
        try:
            from backend.proto.ukip.engine.v1 import engine_pb2
            req = engine_pb2.ProcessRequest(
                pipeline=pipeline,
                job_id=job_id,
                import_batch_id=import_batch_id,
                domain=domain,
                publications=publications,
                options=options or {},
            )
            if org_id is not None:
                req.org_id = org_id
            resp = await self._stub.ProcessAsync(
                req,
                metadata=self._metadata(),
                timeout=30,
            )
            return resp
        except Exception as exc:
            logger.error("Engine process_async failed: %s", exc)
            return None

    async def get_job_status(self, job_id: str) -> Any | None:
        """Return JobStatusResponse or None if not found/engine unavailable."""
        if not await self._ensure_channel():
            return None
        try:
            from backend.proto.ukip.engine.v1 import engine_pb2
            return await self._stub.GetJobStatus(
                engine_pb2.JobStatusRequest(job_id=job_id),
                metadata=self._metadata(),
                timeout=10,
            )
        except Exception as exc:
            logger.debug("Engine get_job_status failed: %s", exc)
            return None

    async def close(self) -> None:
        """Close the gRPC channel."""
        if self._channel:
            await self._channel.close()
            self._channel = None
            self._stub = None
