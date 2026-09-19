from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_ENV = {
    "UKIP_BACKUP_MONITOR_ENABLED",
    "UKIP_BACKUP_ENVIRONMENT",
    "UKIP_BACKUP_PROVIDER_REACHABLE",
    "UKIP_BACKUP_PROVIDER_REACHABLE_AT",
    "UKIP_BACKUP_PROVIDER_REACHABILITY_FILE",
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


def test_reachability_file_defaults_empty_and_is_mounted_read_only():
    # B4 (#320). Unset, the backend keeps the previous environment-variable
    # behaviour and stays fail-closed; the mount must be read-only so the
    # application can never forge its own reachability signal.
    compose = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")

    assert (
        "UKIP_BACKUP_PROVIDER_REACHABILITY_FILE: "
        "${UKIP_BACKUP_PROVIDER_REACHABILITY_FILE:-}"
    ) in compose
    assert (
        "${UKIP_BACKUP_SIGNAL_DIR:-/var/lib/ukip/signals}:/run/ukip-signals:ro"
    ) in compose


def test_the_reachability_probe_carries_no_credential():
    # The probe runs on the host with the read-only provider credential, which
    # must come from the systemd EnvironmentFile, never from the repository.
    probe = (ROOT / "scripts" / "ukip-backup-reachability-probe.sh").read_text(encoding="utf-8")

    # Naming the variables it expects is fine and useful; assigning a value to
    # one of them, or embedding a key id, is not.
    assert "AKIA" not in probe
    assert re.search(r"AWS_(ACCESS_KEY_ID|SECRET_ACCESS_KEY)\s*=\s*\S", probe) is None
    assert "EnvironmentFile" in probe
    # It writes the document atomically: a half-written file must never be read.
    assert "mv -f" in probe
