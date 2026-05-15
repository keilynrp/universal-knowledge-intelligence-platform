"""Async gRPC client for the Rust ukip-engine service."""
from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

_JOB_ID_RE = re.compile(r"[^a-zA-Z0-9_\-]")


def _sanitize_job_id(raw: str) -> str:
    """Strip non-alphanumeric/dash/underscore chars and truncate to 128 chars."""
    return _JOB_ID_RE.sub("", raw)[:128]


class EngineClient:
    """Wraps gRPC calls to ukip-engine with graceful fallback on unavailability."""

    def __init__(self, grpc_url: str, auth_token: str = ""):
        self.grpc_url = grpc_url
        self.auth_token = auth_token
        self._channel = None
        self._stub = None
        self._use_tls = os.environ.get("ENGINE_GRPC_TLS", "") == "1"

    async def _ensure_channel(self) -> bool:
        if not self.grpc_url:
            return False
        if self._channel is None:
            try:
                import grpc
                import grpc.aio
                if self._use_tls:
                    self._channel = grpc.aio.secure_channel(
                        self.grpc_url, grpc.ssl_channel_credentials()
                    )
                else:
                    # Warn if insecure channel to non-localhost
                    host = self.grpc_url.split(":")[0] if ":" in self.grpc_url else self.grpc_url
                    if host not in ("localhost", "127.0.0.1", "::1"):
                        logger.warning(
                            "ENGINE_GRPC_TLS is not enabled but connecting to non-localhost "
                            "host '%s' — credentials will be sent in plaintext",
                            host,
                        )
                    self._channel = grpc.aio.insecure_channel(self.grpc_url)
                from backend.proto.ukip.engine.v1 import engine_pb2_grpc
                self._stub = engine_pb2_grpc.EngineStub(self._channel)
            except Exception as exc:
                logger.warning("Failed to connect to engine at %s: %s", self.grpc_url, exc)
                return False
        return True

    def _metadata(self) -> list[tuple[str, str]]:
        return [("authorization", f"Bearer {self.auth_token}")] if self.auth_token else []

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
                job_id=_sanitize_job_id(job_id),
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
                job_id=_sanitize_job_id(job_id),
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

    # ── Convenience methods for compute pipelines ────────────────────────

    async def process_authority(
        self,
        *,
        field_name: str,
        values: list[str],
        entity_type: str = "person",
        domain: str = "default",
        context_affiliation: str | None = None,
        context_orcid_hint: str | None = None,
        context_doi: str | None = None,
        context_year: int | None = None,
    ) -> Any | None:
        """Delegate authority resolution to the engine."""
        if not await self._ensure_channel():
            return None
        try:
            from backend.proto.ukip.engine.v1 import engine_pb2

            authority_req = engine_pb2.AuthorityRequest(
                field_name=field_name,
                values=values,
                entity_type=entity_type,
            )
            if context_affiliation:
                authority_req.context_affiliation = context_affiliation
            if context_orcid_hint:
                authority_req.context_orcid_hint = context_orcid_hint
            if context_doi:
                authority_req.context_doi = context_doi
            if context_year is not None:
                authority_req.context_year = context_year

            req = engine_pb2.ProcessRequest(
                pipeline="compute_authority",
                job_id=_sanitize_job_id(f"authority-{field_name}"),
                import_batch_id=0,
                domain=domain,
                authority_request=authority_req,
            )
            resp = await self._stub.ProcessSync(
                req, metadata=self._metadata(), timeout=120
            )
            return resp
        except Exception as exc:
            logger.error("Engine process_authority failed: %s", exc)
            return None

    async def process_analytics(
        self,
        *,
        domain_id: str,
        mode: str,
        limit: int = 30,
        field_filters: list[str] | None = None,
    ) -> Any | None:
        """Delegate analytics computation to the engine."""
        if not await self._ensure_channel():
            return None
        try:
            from backend.proto.ukip.engine.v1 import engine_pb2

            analytics_req = engine_pb2.AnalyticsRequest(
                domain_id=domain_id,
                mode=mode,
                limit=limit,
                field_filters=field_filters or [],
            )
            req = engine_pb2.ProcessRequest(
                pipeline="compute_analytics",
                job_id=_sanitize_job_id(f"analytics-{mode}-{domain_id}"),
                import_batch_id=0,
                domain=domain_id,
                analytics_request=analytics_req,
            )
            resp = await self._stub.ProcessSync(
                req, metadata=self._metadata(), timeout=120
            )
            return resp
        except Exception as exc:
            logger.error("Engine process_analytics failed: %s", exc)
            return None

    async def process_disambiguation(
        self,
        *,
        field_name: str,
        values: list[str],
        similarity_threshold: float = 0.85,
        domain: str = "default",
    ) -> Any | None:
        """Delegate disambiguation to the engine."""
        if not await self._ensure_channel():
            return None
        try:
            from backend.proto.ukip.engine.v1 import engine_pb2

            disambiguation_req = engine_pb2.DisambiguationRequest(
                field_name=field_name,
                values=values,
                similarity_threshold=similarity_threshold,
            )
            req = engine_pb2.ProcessRequest(
                pipeline="compute_disambiguation",
                job_id=_sanitize_job_id(f"disambiguate-{field_name}"),
                import_batch_id=0,
                domain=domain,
                disambiguation_request=disambiguation_req,
            )
            resp = await self._stub.ProcessSync(
                req, metadata=self._metadata(), timeout=120
            )
            return resp
        except Exception as exc:
            logger.error("Engine process_disambiguation failed: %s", exc)
            return None

    async def process_normalization(
        self,
        *,
        values: list[str],
        mode: str = "unicode",
        rules: list[dict] | None = None,
        domain: str = "default",
    ) -> Any | None:
        """Delegate normalization to the engine."""
        if not await self._ensure_channel():
            return None
        try:
            from backend.proto.ukip.engine.v1 import engine_pb2

            proto_rules = []
            if rules:
                for r in rules:
                    proto_rules.append(engine_pb2.NormalizationRule(
                        pattern=r.get("pattern", ""),
                        replacement=r.get("replacement", ""),
                    ))

            normalization_req = engine_pb2.NormalizationRequest(
                values=values,
                mode=mode,
                rules=proto_rules,
            )
            req = engine_pb2.ProcessRequest(
                pipeline="compute_normalization",
                job_id=_sanitize_job_id(f"normalize-{mode}"),
                import_batch_id=0,
                domain=domain,
                normalization_request=normalization_req,
            )
            resp = await self._stub.ProcessSync(
                req, metadata=self._metadata(), timeout=60
            )
            return resp
        except Exception as exc:
            logger.error("Engine process_normalization failed: %s", exc)
            return None

    async def process_connectors(
        self,
        *,
        source: str,
        query_type: str,
        queries: list[str],
        limit: int = 10,
        filters: dict[str, str] | None = None,
        domain: str = "default",
    ) -> Any | None:
        """Delegate scientific connector fetch to the engine."""
        if not await self._ensure_channel():
            return None
        try:
            from backend.proto.ukip.engine.v1 import engine_pb2

            connector_req = engine_pb2.ConnectorRequest(
                source=source,
                query_type=query_type,
                queries=queries,
                limit=limit,
                filters=filters or {},
            )
            req = engine_pb2.ProcessRequest(
                pipeline="compute_connectors",
                job_id=_sanitize_job_id(f"connector-{source}"),
                import_batch_id=0,
                domain=domain,
                connector_request=connector_req,
            )
            resp = await self._stub.ProcessSync(
                req, metadata=self._metadata(), timeout=120
            )
            return resp
        except Exception as exc:
            logger.error("Engine process_connectors failed: %s", exc)
            return None

    async def close(self) -> None:
        """Close the gRPC channel."""
        if self._channel:
            await self._channel.close()
            self._channel = None
            self._stub = None
