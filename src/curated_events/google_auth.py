"""Google OAuth helpers for local installed-app auth."""

from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def load_google_credentials(token_path: Path) -> Credentials:
    credentials = Credentials.from_authorized_user_file(str(token_path), GOOGLE_CALENDAR_SCOPES)
    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            token_path.write_text(credentials.to_json(), encoding="utf-8")
        except RefreshError as exc:
            raise RuntimeError(
                f"Google token refresh failed for {token_path}. Run `curated-events google-auth` to re-authorize."
            ) from exc
    return credentials


def ensure_google_credentials(credentials_path: Path, token_path: Path) -> Credentials:
    credentials = None
    if token_path.exists():
        credentials = Credentials.from_authorized_user_file(str(token_path), GOOGLE_CALENDAR_SCOPES)

    if credentials and credentials.valid:
        return credentials

    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
        except RefreshError:
            credentials = None

    if credentials is None or not credentials.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), GOOGLE_CALENDAR_SCOPES)
        credentials = flow.run_local_server(port=0)

    token_path.write_text(credentials.to_json(), encoding="utf-8")
    return credentials
