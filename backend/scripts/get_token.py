"""Print an access token for the test account, for trying protected endpoints.

Run from backend/:

    python scripts/get_token.py

Needs in backend/.env (or the environment):
    SUPABASE_URL, SUPABASE_ANON_KEY  - the usual backend settings
    TEST_EMAIL, TEST_PASSWORD        - a test account created in the Supabase dashboard
                                       (Authentication → Users → Add user, "Auto Confirm User" on)

Prints ONLY the access token (valid for 1 hour), so it can be captured:

    TOKEN=$(python scripts/get_token.py)
    curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/me

Or paste it into http://127.0.0.1:8000/docs → Authorize.
Never prints the password or refresh token. Never commit TEST_PASSWORD.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import dotenv_values

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _setting(name: str, dotenv: dict) -> str:
    value = (os.environ.get(name) or dotenv.get(name) or "").strip()
    if not value:
        sys.exit(f"get_token.py: {name} is not set (add it to backend/.env or the environment).")
    return value


def main() -> None:
    dotenv = dotenv_values(BACKEND_DIR / ".env")
    supabase_url = _setting("SUPABASE_URL", dotenv).rstrip("/")
    anon_key = _setting("SUPABASE_ANON_KEY", dotenv)
    email = _setting("TEST_EMAIL", dotenv)
    password = _setting("TEST_PASSWORD", dotenv)

    request = urllib.request.Request(
        f"{supabase_url}/auth/v1/token?grant_type=password",
        data=json.dumps({"email": email, "password": password}).encode(),
        headers={"apikey": anon_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = json.load(response)
    except urllib.error.HTTPError as e:
        try:
            code = json.load(e).get("error_code") or e.reason
        except ValueError:
            code = e.reason
        sys.exit(f"get_token.py: sign-in failed (HTTP {e.code}: {code}). Check TEST_EMAIL/TEST_PASSWORD.")
    except urllib.error.URLError as e:
        sys.exit(f"get_token.py: could not reach Supabase ({e.reason}).")

    print(body["access_token"])


if __name__ == "__main__":
    main()
