"""Run operator account commands on EC2 over the existing authenticated HTTPS receiver."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from dotenv import dotenv_values

BACKEND = Path(__file__).resolve().parents[1]
CONTROL_PATH = "/internal/koji-deploy/modal"


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # An administrator bearer token must never be forwarded to another URL.
        return None


def configuration(path: Path) -> tuple[str, str]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or value.get("version") != 1 or set(value) - {"version", "origin", "token_file"}:
        raise ValueError("Invalid remote control configuration")
    origin = os.getenv("KOJI_MODAL_CONTROL_URL") or value.get("origin", "")
    parsed = urlsplit(origin)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise ValueError("Remote origin must be HTTPS without credentials, path or query")
    token = os.getenv("KOJI_MODAL_CONTROL_TOKEN", "")
    if not token:
        token_path = value.get("token_file")
        if not isinstance(token_path, str) or not token_path:
            raise ValueError("Configure a private token_file or KOJI_MODAL_CONTROL_TOKEN")
        token_file = Path(token_path).expanduser()
        if not token_file.is_absolute():
            token_file = path.parent / token_file
        token = dotenv_values(token_file).get("KOJI_DEPLOY_TOKEN") or ""
    if len(token) < 40 or "\r" in token or "\n" in token:
        raise ValueError("Remote control token is missing or invalid")
    return origin.rstrip("/"), token


def execute(action: str, account: str | None, config: Path) -> dict:
    if action not in {"list", "status", "check", "switch", "rollback"}:
        raise ValueError("Unknown remote action")
    if action in {"switch", "check"} and (not account or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", account)):
        raise ValueError("Provide a valid account name")
    origin, token = configuration(config)
    endpoint = origin + CONTROL_PATH
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    if action in {"list", "status"}:
        request = Request(endpoint + "/" + action, headers=headers)
    else:
        headers["Content-Type"] = "application/json"
        body = {"action": action}
        if account is not None:
            body["account"] = account
        request = Request(endpoint, data=json.dumps(body).encode(), headers=headers, method="POST")
    print(f"EC2 remote control: {origin}", flush=True)
    # Default context uses the OS trust store, including Windows-managed roots.
    opener = build_opener(NoRedirects(), HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(request, timeout=900) as response:
            payload = response.read(32769)
    except HTTPError as error:
        payload = error.read(32769)
        try:
            details = json.loads(payload).get("details", [])
            for line in details:
                print(line)
        except (ValueError, AttributeError):
            pass
        if error.code == 401:
            raise ValueError("EC2 rejected the operator token") from None
        if error.code == 404:
            raise ValueError("EC2 remote account control is not installed") from None
        raise ValueError(f"EC2 account operation failed (HTTP {error.code}); routing was not confirmed. Run status before retrying.") from None
    except (URLError, TimeoutError, OSError):
        raise ValueError("EC2 connection failed; routing was not confirmed. Run status before retrying.") from None
    if len(payload) > 32768:
        raise ValueError("EC2 response is too large")
    result = json.loads(payload)
    if not isinstance(result, dict) or "active_account" not in result:
        raise ValueError("EC2 returned an invalid account response")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=BACKEND / "modal-remote.json")
    parser.add_argument("action", choices=("list", "status", "check", "switch", "rollback"))
    parser.add_argument("account", nargs="?")
    args = parser.parse_args(argv)
    try:
        result = execute(args.action, args.account, args.config.resolve())
        for line in result.get("details", []):
            print(line)
        if args.action == "list":
            for account in result.get("accounts", []):
                print(f"{'*' if account['name'] == result['active_account'] else ' '} {account['name']}")
        print("EC2 active account:", result["active_account"] or "environment")
        return 0
    except (OSError, ValueError) as error:
        print(f"Remote operation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
