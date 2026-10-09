"""
One-time setup for the Gmail email backend: sign in to the sending Gmail
account in a browser and print the OAuth refresh token to put in
GMAIL_REFRESH_TOKEN.

    cd backend
    python -m app.cli gmail-auth --client-file path/to/client_secret_....json
    python -m app.cli gmail-auth            # or: prompt for the ID and secret

Uses Google's "Desktop app" loopback flow with PKCE: a throwaway web server
on 127.0.0.1 receives the authorization code, so nothing is pasted by hand.
Only the gmail.send scope is requested - the token can send mail as the
account but cannot read it.

The OAuth consent screen must be "In production" (not "Testing"), or Google
expires the refresh token after 7 days.
"""
import argparse
import base64
import getpass
import hashlib
import json
import secrets
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from .core.config import settings
from .services.email_sender import GMAIL_SEND_SCOPE, GOOGLE_TOKEN_URL

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"


def build_auth_url(client_id: str, redirect_uri: str, state: str, code_verifier: str) -> str:
    challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
    return GOOGLE_AUTH_URL + "?" + urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GMAIL_SEND_SCOPE,
        "access_type": "offline",   # ask for a refresh token
        "prompt": "consent",        # ...even if this account consented before
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })


def _wait_for_code(server: HTTPServer, expected_state: str) -> str | None:
    result: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            query = parse_qs(urlparse(self.path).query)
            if query.get("state", [None])[0] != expected_state:
                result["error"] = "state mismatch"
            elif "error" in query:
                result["error"] = query["error"][0]
            else:
                result["code"] = query.get("code", [None])[0]
            ok = "code" in result and result["code"]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                ("Done - you can close this tab and go back to the terminal." if ok
                 else "Sign-in failed - check the terminal.").encode()
            )

        def log_message(self, *args):  # keep the terminal clean
            pass

    server.RequestHandlerClass = Handler
    while not result:
        server.handle_request()
    if "error" in result:
        print(f"Google sign-in failed: {result['error']}", file=sys.stderr)
        return None
    return result["code"]


def read_client_file(path: str) -> tuple[str, str]:
    """Client ID + secret from the JSON Google offers to download for a
    Desktop OAuth client - avoids pasting the secret into a hidden prompt,
    which Ctrl+V doesn't reach in Windows PowerShell."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    client = data.get("installed") or data.get("web") or {}
    return client.get("client_id", ""), client.get("client_secret", "")


def run(argv: list[str] | None = None, prompt=input, secret_prompt=getpass.getpass) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli gmail-auth")
    parser.add_argument(
        "--client-file",
        help="the client_secret_*.json downloaded from Google Cloud > Clients",
    )
    args = parser.parse_args(argv or [])

    if args.client_file:
        try:
            client_id, client_secret = read_client_file(args.client_file)
        except (OSError, ValueError) as e:
            print(f"Could not read {args.client_file}: {e}", file=sys.stderr)
            return 1
    else:
        client_id = settings.GMAIL_CLIENT_ID or prompt("OAuth client ID: ").strip()
        client_secret = settings.GMAIL_CLIENT_SECRET or secret_prompt("OAuth client secret: ").strip()
    if not client_id or not client_secret:
        print("Client ID and secret are required.", file=sys.stderr)
        return 1

    server = HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    redirect_uri = f"http://127.0.0.1:{server.server_port}"
    state = secrets.token_urlsafe(16)
    code_verifier = secrets.token_urlsafe(64)
    url = build_auth_url(client_id, redirect_uri, state, code_verifier)

    print("Sign in with the Gmail account that should SEND the emails.")
    print(f"If no browser opens, visit:\n\n{url}\n")
    webbrowser.open(url)
    try:
        code = _wait_for_code(server, state)
    finally:
        server.server_close()
    if not code:
        return 1

    resp = httpx.post(GOOGLE_TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "code_verifier": code_verifier,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }, timeout=15)
    if resp.status_code != 200:
        print(f"Token exchange failed ({resp.status_code}): {resp.text[:300]}", file=sys.stderr)
        return 1
    refresh_token = resp.json().get("refresh_token")
    if not refresh_token:
        print("Google returned no refresh token - remove the app's access at "
              "https://myaccount.google.com/permissions and try again.", file=sys.stderr)
        return 1

    print("Success. Set these environment variables (Render > backend > Environment):\n")
    print("EMAIL_BACKEND=gmail")
    print(f"GMAIL_CLIENT_ID={client_id}")
    print("GMAIL_CLIENT_SECRET=<the client secret you used>")
    print(f"GMAIL_REFRESH_TOKEN={refresh_token}")
    print("EMAIL_FROM=BSU Registrar <the-sending-address@gmail.com>")
    print("\nTreat the refresh token like a password.")
    return 0
