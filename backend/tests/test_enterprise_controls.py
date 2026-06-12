from backend.enterprise_controls import (
    CONTROL_MATURITY_ORDER,
    ENTERPRISE_CONTROLS,
    build_enterprise_readiness_report,
)


EXPECTED_IDS = {
    "ER-CTRL-001",
    "ER-OPS-001",
    "ER-BCP-001",
    "ER-SDLC-001",
    "ER-AUD-001",
    "ER-PRIV-001",
    "ER-IAM-001",
    "ER-DEP-001",
    "ER-IR-001",
    "ER-PERF-001",
    "ER-ASSURE-001",
}


def test_manifest_has_unique_expected_control_ids():
    ids = [control.control_id for control in ENTERPRISE_CONTROLS]
    assert set(ids) == EXPECTED_IDS
    assert len(ids) == len(set(ids))


def test_every_control_has_delivery_and_next_gate():
    for control in ENTERPRISE_CONTROLS:
        assert control.owner
        assert control.related_work or control.control_id == "ER-CTRL-001"
        assert control.next_gate
        assert control.current_maturity in CONTROL_MATURITY_ORDER
        assert control.target_maturity in CONTROL_MATURITY_ORDER


def test_report_aggregates_by_priority_and_maturity():
    report = build_enterprise_readiness_report()
    assert report["status"] == "enterprise_readiness_program"
    assert report["target_claim"] == "regulated_institutional_enterprise_ready"
    assert report["summary"]["total_controls"] == len(ENTERPRISE_CONTROLS)
    assert sum(report["summary"]["priority_counts"].values()) == len(ENTERPRISE_CONTROLS)
    assert sum(report["summary"]["maturity_counts"].values()) == len(ENTERPRISE_CONTROLS)
