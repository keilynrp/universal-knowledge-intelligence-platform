"""Compatibility entry point for the enterprise control report."""

from backend.enterprise_controls import build_enterprise_readiness_report


def get_enterprise_readiness_report() -> dict:
    return build_enterprise_readiness_report()
