"""JWTs are signed and verified with PyJWT, not python-jose (#422).

python-jose was the only reason ecdsa, rsa and pyasn1 were in the image, and
ecdsa carried an advisory with no fix in any version (PYSEC-2026-1325). UKIP
signs with HS256 only, which PyJWT covers with no dependencies.

The switch must not sign anyone out: tokens minted by python-jose before the
deploy have to keep working. The two below were minted by python-jose 3.5.0 on
2026-09-30 with the keys in this file, the claims create_access_token and
create_refresh_token produce, and an expiry in 2099.
"""
from __future__ import annotations

import base64
import json
import pathlib
from datetime import timedelta

import jwt
import pytest

from backend import auth

PRIMARY = "compat-primary-key-for-tests-only-0123456789abcdef"
RETIRING = "compat-retiring-key-for-tests-only-0123456789abcdef"

JOSE_ACCESS = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiJjb21wYXRfdXNlciIsInJvbGUiOiJlZGl0b3IiLCJzaWQiOiJjb21wYXQtc2lkLTAwMDEiLCJleHAiOjQwNzA5MDg4MDAsInR5cGUiOiJhY2Nlc3MifQ."
    "f0T1N3da8Pa1_RPl7PBFljIG2-fLPZ1Ffg-5TrTdPc8"
)
JOSE_REFRESH_WITH_RETIRING_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiJjb21wYXRfdXNlciIsInJvbGUiOiJlZGl0b3IiLCJzaWQiOiJjb21wYXQtc2lkLTAwMDEiLCJleHAiOjQwNzA5MDg4MDAsInR5cGUiOiJyZWZyZXNoIn0."
    "_oSvbLWM_GL-e8YQrXxRhrshbJegZnzCRwWvmsGIQVs"
)


@pytest.fixture()
def keys(monkeypatch):
    monkeypatch.setattr(auth, "SECRET_KEY", PRIMARY)
    monkeypatch.setattr(auth, "RETIRING_SECRET_KEYS", [RETIRING])


def _b64(part: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(part).encode()).rstrip(b"=").decode()


class TestTokensMintedBeforeTheSwitch:
    def test_an_access_token_from_python_jose_still_decodes(self, keys):
        claims = auth._decode_token(JOSE_ACCESS)
        assert claims["sub"] == "compat_user"
        assert claims["role"] == "editor"
        assert claims["sid"] == "compat-sid-0001"
        assert claims["type"] == "access"

    def test_a_refresh_token_signed_with_a_retiring_key_still_decodes(self, keys):
        claims = auth._decode_token(JOSE_REFRESH_WITH_RETIRING_KEY)
        assert claims["type"] == "refresh"
        assert claims["sid"] == "compat-sid-0001"


class TestNewTokens:
    def test_access_and_refresh_tokens_round_trip(self, keys):
        access = auth.create_access_token("alice", "viewer", "sid-1")
        refresh = auth.create_refresh_token("alice", "viewer", "sid-1")
        assert auth._decode_token(access)["type"] == "access"
        assert auth._decode_token(refresh)["type"] == "refresh"
        assert jwt.get_unverified_header(access)["alg"] == "HS256"


class TestRefusals:
    """Every refusal raises jwt.PyJWTError, the type every call site catches."""

    def test_an_expired_token(self, keys):
        token = auth.create_access_token("alice", "viewer", "sid-1", timedelta(seconds=-5))
        with pytest.raises(jwt.PyJWTError):
            auth._decode_token(token)

    def test_a_token_signed_with_an_unknown_key(self, keys):
        token = jwt.encode({"sub": "mallory", "exp": 4070908800}, "some-other-key-0123456789abcdef-long", algorithm="HS256")
        with pytest.raises(jwt.PyJWTError):
            auth._decode_token(token)

    def test_a_tampered_payload(self, keys):
        header, _, signature = JOSE_ACCESS.split(".")
        forged = _b64({"sub": "compat_user", "role": "super_admin", "sid": "compat-sid-0001", "exp": 4070908800, "type": "access"})
        with pytest.raises(jwt.PyJWTError):
            auth._decode_token(f"{header}.{forged}.{signature}")

    def test_an_unsigned_token(self, keys):
        # alg "none": no signature at all.
        token = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64({'sub': 'mallory', 'exp': 4070908800})}."
        with pytest.raises(jwt.PyJWTError):
            auth._decode_token(token)

    def test_another_algorithm_with_the_real_key(self, keys):
        # Only HS256 is accepted, even when the signature is otherwise valid.
        token = jwt.encode({"sub": "alice", "exp": 4070908800}, PRIMARY, algorithm="HS512")
        with pytest.raises(jwt.PyJWTError):
            auth._decode_token(token)

    def test_garbage(self, keys):
        with pytest.raises(jwt.PyJWTError):
            auth._decode_token("not.a.jwt")


def test_nothing_in_the_backend_imports_python_jose():
    backend = pathlib.Path(__file__).resolve().parents[1]
    offenders = [
        str(path.relative_to(backend))
        for path in backend.rglob("*.py")
        if any(
            line.strip().startswith(("from jose", "import jose"))
            for line in path.read_text(encoding="utf-8").splitlines()
        )
    ]
    assert offenders == []
