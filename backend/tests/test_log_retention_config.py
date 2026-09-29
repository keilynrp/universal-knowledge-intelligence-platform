"""The reviewed host configuration for central-log-retention keeps its promises.

These files are applied by hand (Traefik in Dokploy, the policies in AWS), so a
test on the reviewed copy is the only place a careless edit can be caught before
it reaches production. What they must never do (openspec change
``central-log-retention``, design decisions 3 and 4):

- the proxy log keeps no query string and no header that carries a credential;
- the shipper can append, and cannot read, delete, or shorten the retention of
  what it shipped;
- the reader can read, and cannot change the record.
"""
from __future__ import annotations

import fnmatch
import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
TRAEFIK = ROOT / "deploy/traefik/access-log.yml"
IAM = ROOT / "deploy/log-shipper/iam"

LOG_GROUPS = ("/ukip/prod/backend", "/ukip/prod/traefik")
REGION = "us-east-2"

# Actions that read, remove, or re-time retained logs, or lift Object Lock.
_TAMPERING = (
    "logs:Delete*",
    "logs:PutRetentionPolicy",
    "s3:Delete*",
    "s3:PutObjectRetention",
    "s3:PutObjectLegalHold",
    "s3:BypassGovernanceRetention",
    "s3:PutBucketObjectLockConfiguration",
    "s3:PutLifecycleConfiguration",
    "s3:PutBucketPolicy",
)
_READING = ("logs:Get*", "logs:FilterLogEvents", "logs:StartQuery", "s3:Get*", "s3:List*")
_WRITING = ("logs:CreateLogStream", "logs:PutLogEvents", "s3:PutObject")


def _policy(name: str) -> dict:
    return json.loads((IAM / name).read_text(encoding="utf-8"))


def _statements(policy: dict, effect: str) -> list[dict]:
    return [s for s in policy["Statement"] if s["Effect"] == effect]


def _actions(statements: list[dict]) -> set[str]:
    found: set[str] = set()
    for statement in statements:
        action = statement["Action"]
        found.update([action] if isinstance(action, str) else action)
    return found


def _matches(action: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(action, pattern) for pattern in patterns)


def _resources(statement: dict) -> list[str]:
    resource = statement["Resource"]
    return [resource] if isinstance(resource, str) else resource


class TestTraefikAccessLog:
    @pytest.fixture()
    def access_log(self) -> dict:
        return yaml.safe_load(TRAEFIK.read_text(encoding="utf-8"))["accessLog"]

    def test_it_is_json(self, access_log):
        assert access_log["format"] == "json"

    def test_it_stays_in_the_file_dokploy_reads(self, access_log):
        # Dokploy's "Requests" view reads this file; moving the log to stdout
        # would break it, and the shipper follows the same file.
        assert access_log["filePath"] == "/etc/dokploy/traefik/dynamic/access.log"

    def test_every_request_is_logged(self, access_log):
        # Dokploy's default keeps only requests over 10 ms or retried; a fast
        # request is still an access.
        assert not access_log.get("filters")

    def test_no_query_parameter_is_kept(self, access_log):
        query = access_log["fields"]["queryParameters"]
        assert query["defaultMode"] == "drop"
        assert not query.get("names"), "no query parameter may be kept by name"

    def test_headers_are_dropped_except_the_two_it_needs(self, access_log):
        headers = access_log["fields"]["headers"]
        assert headers["defaultMode"] == "drop"
        kept = {name.lower() for name, mode in headers.get("names", {}).items() if mode != "drop"}
        assert kept <= {"user-agent", "cf-connecting-ip"}
        assert not kept & {"authorization", "cookie", "x-api-key"}

    def test_basic_auth_user_names_are_dropped(self, access_log):
        assert access_log["fields"]["names"]["ClientUsername"] == "drop"


class TestShipperPolicy:
    @pytest.fixture()
    def policy(self) -> dict:
        return _policy("ukip-log-shipper-policy.json")

    def test_it_is_allowed_to_write_and_nothing_else(self, policy):
        allowed = _actions(_statements(policy, "Allow"))
        assert allowed == {
            "logs:CreateLogStream",
            "logs:DescribeLogStreams",
            "logs:PutLogEvents",
            "s3:PutObject",
        }

    def test_nothing_it_is_allowed_reads_or_tampers(self, policy):
        for action in _actions(_statements(policy, "Allow")):
            assert not _matches(action, _TAMPERING + _READING), action

    def test_tampering_and_reading_are_denied_explicitly(self, policy):
        # A broader policy attached later must not quietly restore these.
        denied = _actions(_statements(policy, "Deny"))
        for required in (
            "logs:DeleteLogGroup", "logs:PutRetentionPolicy", "logs:GetLogEvents",
            "s3:GetObject", "s3:DeleteObject", "s3:PutObjectRetention",
            "s3:BypassGovernanceRetention",
        ):
            assert required in denied, required

    def test_it_writes_only_to_the_two_groups_and_the_archive_prefix(self, policy):
        for statement in _statements(policy, "Allow"):
            for resource in _resources(statement):
                assert resource != "*"
                if resource.startswith("arn:aws:logs:"):
                    assert f":{REGION}:" in resource
                    assert any(f":log-group:{group}:" in resource for group in LOG_GROUPS)
                else:
                    assert resource.endswith("/logs/*"), resource


class TestReaderPolicy:
    @pytest.fixture()
    def policy(self) -> dict:
        return _policy("ukip-log-reader-policy.json")

    def test_nothing_it_is_allowed_writes_or_tampers(self, policy):
        for action in _actions(_statements(policy, "Allow")):
            assert not _matches(action, _TAMPERING + _WRITING), action

    def test_writing_and_tampering_are_denied_explicitly(self, policy):
        denied = _actions(_statements(policy, "Deny"))
        for required in (
            "logs:PutLogEvents", "logs:DeleteLogGroup", "logs:PutRetentionPolicy",
            "s3:PutObject", "s3:DeleteObject", "s3:BypassGovernanceRetention",
        ):
            assert required in denied, required

    def test_it_reads_only_the_two_groups_and_the_archive_prefix(self, policy):
        for statement in _statements(policy, "Allow"):
            actions = _actions([statement])
            for resource in _resources(statement):
                if resource == "*":
                    # Query results are addressed by query id, not by log group.
                    assert actions <= {"logs:GetQueryResults", "logs:StopQuery"}, actions
                elif resource.startswith("arn:aws:logs:"):
                    assert f":{REGION}:" in resource
                    assert any(f":log-group:{group}:" in resource for group in LOG_GROUPS)
                elif resource == "arn:aws:s3:::${LOG_ARCHIVE_BUCKET}":
                    assert actions == {"s3:ListBucket"}
                    prefixes = statement["Condition"]["StringLike"]["s3:prefix"]
                    assert prefixes == ["logs/*"]
                else:
                    assert resource.endswith("/logs/*"), resource
