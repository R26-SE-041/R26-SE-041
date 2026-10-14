"""Operator-controlled Modal routing. Existing jobs retain their endpoint snapshot."""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlsplit

import requests
from dotenv import load_dotenv

SERVICES = {
    "prompt": "PROMPT_AGENT_URL", "image": "IMAGE_AGENT_URL",
    "sketch": "SKETCH_AGENT_URL", "interactive": "INTERACTIVE_AGENT_URL",
    "evaluation": "EVAL_AGENT_URL", "threed": "THREED_AGENT_URL",
}
ENDPOINT_KEYS = {*SERVICES, "orchestrator"}
BACKEND = Path(__file__).resolve().parents[1]


def registry_path() -> Path:
    return Path(os.getenv("KOJI_MODAL_ACCOUNTS_FILE") or BACKEND / "modal-accounts.json").resolve()


def state_path() -> Path:
    return Path(os.getenv("KOJI_MODAL_STATE_FILE") or registry_path().with_name("modal-active.json")).resolve()


def validate_endpoints(value: object, *, complete: bool = True) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) - ENDPOINT_KEYS:
        raise ValueError("Endpoints must contain only known Koji services")
    if complete and set(value) != ENDPOINT_KEYS:
        raise ValueError("Account needs all six agent URLs and the orchestrator URL")
    result = {}
    for service, url in value.items():
        if not isinstance(url, str):
            raise ValueError(f"Invalid {service} URL")
        url = url.strip().rstrip("/")
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path or parsed.port not in {None, 443}
                or any(character.isspace() for character in url)):
            raise ValueError(f"{service} must be an HTTPS origin without credentials, path or query")
        result[service] = url
    return result


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError(f"Invalid version in {path.name}; expected version 1")
    return value


def accounts() -> dict:
    value = read_json(registry_path()).get("accounts")
    if not isinstance(value, dict) or not value:
        raise ValueError("Configure at least one account in modal-accounts.json")
    result = {}
    for name, account in value.items():
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name) or not isinstance(account, dict):
            raise ValueError("Invalid account name or configuration")
        if set(account) - {"profile", "environment", "endpoints"}:
            raise ValueError(f"Unknown fields in account {name}")
        for key in ("profile", "environment"):
            if not isinstance(account.get(key), str) or not account[key].strip():
                raise ValueError(f"Account {name} needs a {key}")
        result[name] = {**account, "endpoints": validate_endpoints(account.get("endpoints"))}
    return result


def legacy_endpoints() -> dict[str, str]:
    # Preserve local HTTP development and partial environment configuration.
    return {service: os.environ[key].strip().rstrip("/")
            for service, key in {**SERVICES, "orchestrator": "ORCHESTRATOR_URL"}.items()
            if os.getenv(key, "").strip()}


def validate_snapshot(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != {"account", "endpoints"}:
        raise ValueError("Invalid active account snapshot")
    name = value["account"]
    if name is not None and (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name)):
        raise ValueError("Invalid active account name")
    if name is None:
        # A rollback to environment routing must use the process's own .env.
        if value["endpoints"] != {}:
            raise ValueError("Environment snapshot must not contain endpoints")
        return value
    return {"account": name, "endpoints": validate_endpoints(value["endpoints"])}


def current_state() -> dict:
    try:
        value = read_json(state_path())
    except FileNotFoundError:
        return {"version": 1, "active": {"account": None, "endpoints": {}}, "previous": None}
    # A bad state must fail closed, never silently route to another workspace.
    value["active"] = validate_snapshot(value.get("active"))
    if value.get("previous") is not None:
        value["previous"] = validate_snapshot(value["previous"])
    return value


def routing_endpoints() -> dict[str, str]:
    active = current_state()["active"]
    return dict(active["endpoints"]) if active["account"] is not None else legacy_endpoints()


def atomic_write(path: Path, value: dict) -> None:
    # Readers see either complete snapshot. No process-local cache or restart.
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        # Routing contains public origins only; API/worker must be able to read it.
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def switch_lock():
    path = state_path().with_suffix(".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt
            if path.stat().st_size == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise ValueError("Another account switch is in progress") from None
        else:
            import fcntl
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError("Another account switch is in progress") from None
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def check_endpoints(endpoints: dict[str, str], timeout: float) -> None:
    if not endpoints:
        raise ValueError("No endpoints configured to check")
    failures = []
    for service, origin in endpoints.items():
        try:
            response = requests.get(origin + "/health", timeout=(10, timeout))
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict) or body.get("status") != "ok":
                raise ValueError("health response is not ok")
            print(f"  {service}: ok", flush=True)
        except (requests.RequestException, ValueError):
            # Avoid dumping response bodies or potentially sensitive URLs.
            failures.append(service)
            print(f"  {service}: unavailable", flush=True)
    if failures:
        raise ValueError("Health checks failed: " + ", ".join(failures))


def activate(account: str | None, timeout: float, *, rollback: bool = False) -> None:
    with switch_lock():
        state = current_state()
        if rollback:
            target = state.get("previous")
            if target is None:
                raise ValueError("No previous routing configuration to restore")
        else:
            registry = accounts()
            if account not in registry:
                raise ValueError(f"Unknown account: {account}")
            target = {"account": account, "endpoints": registry[account]["endpoints"]}
        if target == state["active"]:
            print("This routing configuration is already active")
            return
        print(f"Checking {target['account'] or 'environment'} before switching", flush=True)
        check_endpoints(target["endpoints"] if target["account"] is not None else legacy_endpoints(), timeout)
        atomic_write(state_path(), {"version": 1, "active": target, "previous": state["active"]})
        print(f"Active: {target['account'] or 'environment'}. New requests use this routing; existing jobs keep their URLs.")


def main(argv: list[str] | None = None) -> int:
    load_dotenv(BACKEND / ".env")
    parser = argparse.ArgumentParser(description="Manage Koji's live Modal endpoint routing")
    parser.add_argument("--config", type=Path, help="Account registry path")
    parser.add_argument("--state", type=Path, help="Shared routing state path used by the API")
    parser.add_argument("--timeout", type=float, default=120, help="Read timeout per endpoint, seconds")
    parser.add_argument("--json", action="store_true", help="Machine-readable result for remote control")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    commands.add_parser("status")
    commands.add_parser("rollback")
    for command in ("check", "switch"):
        commands.add_parser(command).add_argument("account")
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    if args.config:
        os.environ["KOJI_MODAL_ACCOUNTS_FILE"] = str(args.config.resolve())
    if args.state:
        os.environ["KOJI_MODAL_STATE_FILE"] = str(args.state.resolve())
    try:
        if args.json:
            # Reuse the checked local operation; keep progress out of JSON responses.
            arguments = ["--timeout", str(args.timeout), args.command]
            if args.command in {"check", "switch"}:
                arguments.append(args.account)
            progress = io.StringIO()
            with redirect_stdout(progress):
                result = main(arguments)
            if result:
                print(json.dumps({"error": "Account operation failed", "details": progress.getvalue().splitlines()}))
                return result
            state = current_state()
            payload = {"active_account": state["active"]["account"],
                       "previous_account": (state.get("previous") or {}).get("account"),
                       "endpoints": routing_endpoints(), "details": progress.getvalue().splitlines()}
            if args.command == "list":
                payload["accounts"] = [{"name": name, "profile": account["profile"],
                                        "environment": account["environment"]} for name, account in accounts().items()]
            print(json.dumps(payload))
            return 0
        if args.command == "status":
            state = current_state()
            print("Active:", state["active"]["account"] or "environment")
            previous = state.get("previous")
            print("Previous:", (previous["account"] or "environment") if previous is not None else "none")
            print("Routing file:", state_path())
            for service, url in routing_endpoints().items():
                print(f"  {service}: {url}")
        elif args.command == "list":
            active = current_state()["active"]["account"]
            for name, account in accounts().items():
                print(f"{'*' if name == active else ' '} {name} (profile={account['profile']}, environment={account['environment']})")
        elif args.command == "check":
            registry = accounts()
            if args.account not in registry:
                raise ValueError(f"Unknown account: {args.account}")
            check_endpoints(registry[args.account]["endpoints"], args.timeout)
        else:
            activate(getattr(args, "account", None), args.timeout, rollback=args.command == "rollback")
        return 0
    except (OSError, ValueError) as exc:
        print(f"Account operation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
