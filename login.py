"""One-time OAuth for local use. Gets an access token; the server never imports this.

Usage:
    python login.py                 # interactive consent, prints the token
    python login.py --print-token   # token only, for $(...) capture

Needs a *Desktop* OAuth client JSON outside the repo, at GOOGLE_CREDENTIALS_PATH.
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
TOKEN_PATH = Path.home() / ".config/calendar-agent/token.json"


def load_creds() -> Credentials:
    creds = None
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        except ValueError:
            creds = None
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json())
            return creds
        except RefreshError:
            # revoked, expired, or issued by a deleted OAuth client; fall through to consent
            TOKEN_PATH.unlink(missing_ok=True)
            creds = None
    client_file = os.environ.get("GOOGLE_CREDENTIALS_PATH", "")
    if not client_file or not Path(client_file).exists():
        sys.exit("GOOGLE_CREDENTIALS_PATH must point at a Desktop OAuth client JSON")
    creds = InstalledAppFlow.from_client_secrets_file(client_file, SCOPES).run_local_server(port=0)
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json())
    return creds


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-token", action="store_true", help="print only the access token")
    args = parser.parse_args()
    token = load_creds().token
    if not token:
        sys.exit("no access token")
    if args.print_token:
        print(token)
    else:
        print(f"access token (valid ~1h): {token}")
        print(f"refresh token cached at {TOKEN_PATH}")


if __name__ == "__main__":
    main()
