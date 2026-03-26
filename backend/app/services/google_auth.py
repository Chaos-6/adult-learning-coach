"""
Google OAuth2 authentication for CLI Google Docs export.

Handles the OAuth2 user consent flow and token caching:
1. First run: opens browser for Google sign-in, saves token
2. Subsequent runs: loads cached token, refreshes if expired

Token stored at ~/.alca/google_token.json (outside the project,
so it's never accidentally committed to git).
"""

import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]
TOKEN_DIR = Path.home() / ".alca"
TOKEN_PATH = TOKEN_DIR / "google_token.json"


def get_google_services(client_id: str, client_secret: str):
    """Authenticate with Google and return (docs_service, drive_service).

    On first run, opens a browser for OAuth consent. On subsequent
    runs, uses the cached token (refreshing automatically if expired).

    Args:
        client_id: Google OAuth2 client ID from config.
        client_secret: Google OAuth2 client secret from config.

    Returns:
        Tuple of (docs_service, drive_service) — authorized API clients.

    Raises:
        ValueError: If client_id or client_secret not configured.
    """
    if not client_id or not client_secret:
        raise ValueError(
            "Google OAuth2 credentials not configured.\n"
            "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your .env file.\n"
            "Create credentials at: https://console.cloud.google.com/apis/credentials"
        )

    creds = None

    # Load cached token if it exists
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # Refresh or re-authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Build client config from our env vars (no downloaded JSON file needed)
            client_config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            }
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)

        # Cache the token for next time
        TOKEN_DIR.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())

    docs_service = build("docs", "v1", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)
    return docs_service, drive_service
