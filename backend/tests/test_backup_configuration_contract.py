from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_ENV = {
    "UKIP_BACKUP_MONITOR_ENABLED",
    "UKIP_BACKUP_ENVIRONMENT",
    "UKIP_BACKUP_PROVIDER_REACHABLE",
    "UKIP_BACKUP_PROVIDER_REACHABLE_AT",
    "UKIP_BACKUP_RPO_HOURS",
    "UKIP_BACKUP_CRITICAL_AFTER_HOURS",
}
FORBIDDEN_APPLICATION_ENV = {
    "S3_SECRET_ACCESS_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "BACKUP_DATABASE_PASSWORD",
    "BACKUP_BUCKET_ACCESS_TOKEN",
}


def test_production_compose_and_dokploy_example_define_monitoring_metadata():
    compose = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    dokploy = (ROOT / ".env.dokploy.example").read_text(encoding="utf-8")

    for variable in REQUIRED_ENV:
        assert variable in compose
        assert variable in dokploy


def test_local_example_disables_backup_monitoring():
    local_env = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "UKIP_BACKUP_MONITOR_ENABLED=0" in local_env
    assert "UKIP_BACKUP_PROVIDER_REACHABLE=0" in local_env
    assert "UKIP_BACKUP_PROVIDER_REACHABLE_AT=" in local_env


def test_provider_reachability_defaults_fail_closed():
    compose = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    dokploy = (ROOT / ".env.dokploy.example").read_text(encoding="utf-8")

    assert (
        "UKIP_BACKUP_PROVIDER_REACHABLE: "
        "${UKIP_BACKUP_PROVIDER_REACHABLE:-0}"
    ) in compose
    assert (
        "UKIP_BACKUP_PROVIDER_REACHABLE_AT: "
        "${UKIP_BACKUP_PROVIDER_REACHABLE_AT:-}"
    ) in compose
    assert "UKIP_BACKUP_PROVIDER_REACHABLE=0" in dokploy
    assert "UKIP_BACKUP_PROVIDER_REACHABLE_AT=" in dokploy


def test_application_configuration_contains_no_backup_storage_secrets():
    contents = "\n".join(
        [
            (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"),
            (ROOT / ".env.dokploy.example").read_text(encoding="utf-8"),
            (ROOT / ".env.example").read_text(encoding="utf-8"),
        ]
    )

    for variable in FORBIDDEN_APPLICATION_ENV:
        assert variable not in contents
