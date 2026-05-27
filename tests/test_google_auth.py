from __future__ import annotations

from pathlib import Path

import pytest
from google.auth.exceptions import RefreshError

from curated_events.google_auth import ensure_google_credentials, load_google_credentials


class FakeCredentials:
    def __init__(self, *, valid: bool, expired: bool, refresh_token: str | None = "refresh-token"):
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token
        self.refresh_calls = 0

    def refresh(self, request) -> None:
        self.refresh_calls += 1
        raise RefreshError("invalid_grant")

    def to_json(self) -> str:
        return '{"token":"new-token"}'


class FakeFlow:
    def __init__(self, credentials):
        self.credentials = credentials
        self.run_calls = 0

    def run_local_server(self, port: int = 0):
        self.run_calls += 1
        return self.credentials


def test_load_google_credentials_raises_reauth_message_on_invalid_grant(monkeypatch, tmp_path: Path):
    token_path = tmp_path / "token.json"
    token_path.write_text("{}", encoding="utf-8")
    creds = FakeCredentials(valid=False, expired=True)

    monkeypatch.setattr(
        "curated_events.google_auth.Credentials.from_authorized_user_file",
        lambda *args, **kwargs: creds,
    )

    with pytest.raises(RuntimeError, match="Run `curated-events google-auth` to re-authorize"):
        load_google_credentials(token_path)


def test_ensure_google_credentials_falls_back_to_oauth_on_invalid_grant(monkeypatch, tmp_path: Path):
    credentials_path = tmp_path / "google-credentials.json"
    token_path = tmp_path / "token.json"
    credentials_path.write_text("{}", encoding="utf-8")
    token_path.write_text("{}", encoding="utf-8")

    stale_creds = FakeCredentials(valid=False, expired=True)
    fresh_creds = FakeCredentials(valid=True, expired=False, refresh_token=None)
    flow = FakeFlow(fresh_creds)

    monkeypatch.setattr(
        "curated_events.google_auth.Credentials.from_authorized_user_file",
        lambda *args, **kwargs: stale_creds,
    )
    monkeypatch.setattr(
        "curated_events.google_auth.InstalledAppFlow.from_client_secrets_file",
        lambda *args, **kwargs: flow,
    )

    credentials = ensure_google_credentials(credentials_path=credentials_path, token_path=token_path)

    assert credentials is fresh_creds
    assert stale_creds.refresh_calls == 1
    assert flow.run_calls == 1
    assert token_path.read_text(encoding="utf-8") == fresh_creds.to_json()
