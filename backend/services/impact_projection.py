from __future__ import annotations

import hashlib
import math
from typing import Any

import numpy as np


class ImpactProjectionService:
    """Portfolio-level Monte Carlo projection for executive impact readouts."""

    _SIMULATIONS = 10_000

    @classmethod
    def build_from_snapshot(cls, snapshot: dict[str, Any]) -> dict[str, Any]:
        kpis = snapshot.get("kpis") or {}
        quality = snapshot.get("quality") or {}
        top_entities = snapshot.get("top_entities") or []

        total_entities = int(kpis.get("total_entities") or 0)
        enrichment_pct = float(kpis.get("enrichment_pct") or 0.0)
        avg_citations = float(kpis.get("avg_citations") or 0.0)
        avg_quality = quality.get("average")
        quality_pct = float(avg_quality) * 100 if avg_quality is not None else 0.0
        top_citations = [int(entity.get("citation_count") or 0) for entity in top_entities[:10]]

        if total_entities <= 0:
            return cls._empty_projection()

        citation_signal = min(100.0, math.log1p(max(avg_citations, 0.0)) / math.log1p(5000) * 100)
        concentration_signal = min(100.0, math.log1p(sum(top_citations) or 0) / math.log1p(50000) * 100)
        coverage_signal = max(0.0, min(100.0, enrichment_pct))
        quality_signal = max(0.0, min(100.0, quality_pct))

        baseline = (
            coverage_signal * 0.30
            + quality_signal * 0.25
            + citation_signal * 0.25
            + concentration_signal * 0.20
        )

        # Lower coverage and smaller portfolios increase uncertainty.
        sample_penalty = max(0.0, 1.0 - min(total_entities, 500) / 500)
        coverage_penalty = max(0.0, 1.0 - coverage_signal / 100)
        quality_penalty = max(0.0, 1.0 - quality_signal / 100) if avg_quality is not None else 0.35
        sigma = 5.0 + sample_penalty * 12.0 + coverage_penalty * 10.0 + quality_penalty * 6.0

        seed = cls._seed(snapshot)
        rng = np.random.default_rng(seed)
        simulations = rng.normal(loc=baseline, scale=sigma, size=cls._SIMULATIONS)
        simulations += rng.triangular(-8, 0, 12, size=cls._SIMULATIONS) * (coverage_signal / 100)
        simulations = np.clip(simulations, 0, 100)

        p10, p50, p90 = np.percentile(simulations, [10, 50, 90])
        interval_width = float(p90 - p10)
        confidence_score = max(0, min(100, round(100 - interval_width)))
        confidence = "high" if confidence_score >= 70 else "medium" if confidence_score >= 45 else "low"

        expected = round(float(p50))
        conservative = round(float(p10))
        optimistic = round(float(p90))

        if expected >= 70 and confidence != "low":
            recommendation = "El portafolio ya sostiene una narrativa de impacto defendible para stakeholders."
            brief_angle = "Enfatizar evidencia de impacto, outputs destacados y oportunidades de posicionamiento."
        elif expected >= 45:
            recommendation = "Usar la proyección como lectura direccional y reforzar calidad/cobertura antes de escalar."
            brief_angle = "Presentar el impacto como escenario probable, explicando brechas y supuestos."
        else:
            recommendation = "Tratar el impacto como señal temprana; enriquecer y revisar antes del brief externo."
            brief_angle = "Enmarcar el brief como línea base inicial, no como conclusión de impacto."

        return {
            "method": "monte_carlo",
            "simulations": cls._SIMULATIONS,
            "score": expected,
            "expected": expected,
            "conservative": conservative,
            "optimistic": optimistic,
            "range": {"p10": conservative, "p50": expected, "p90": optimistic},
            "confidence": confidence,
            "confidence_score": confidence_score,
            "interval_width": round(interval_width, 1),
            "drivers": {
                "coverage": round(coverage_signal, 1),
                "quality": round(quality_signal, 1),
                "citation_signal": round(citation_signal, 1),
                "concentration": round(concentration_signal, 1),
            },
            "recommendation": recommendation,
            "brief_angle": brief_angle,
            "explanation": (
                "Proyección probabilística basada en cobertura de enriquecimiento, calidad, "
                "citas promedio y concentración de entidades de alto impacto."
            ),
        }

    @staticmethod
    def _seed(snapshot: dict[str, Any]) -> int:
        kpis = snapshot.get("kpis") or {}
        top_entities = snapshot.get("top_entities") or []
        raw = "|".join([
            str(snapshot.get("domain_id") or ""),
            str(kpis.get("total_entities") or 0),
            str(kpis.get("enrichment_pct") or 0),
            str(kpis.get("avg_citations") or 0),
            ",".join(str(entity.get("id") or "") for entity in top_entities[:10]),
        ])
        return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8], 16)

    @staticmethod
    def _empty_projection() -> dict[str, Any]:
        return {
            "method": "monte_carlo",
            "simulations": 0,
            "score": 0,
            "expected": 0,
            "conservative": 0,
            "optimistic": 0,
            "range": {"p10": 0, "p50": 0, "p90": 0},
            "confidence": "low",
            "confidence_score": 0,
            "interval_width": 0,
            "drivers": {"coverage": 0, "quality": 0, "citation_signal": 0, "concentration": 0},
            "recommendation": "Importa y enriquece registros para generar una proyección de impacto.",
            "brief_angle": "El brief debe presentarse como preparación del portafolio, todavía sin lectura de impacto.",
            "explanation": "No hay suficientes registros para correr una proyección probabilística.",
        }
