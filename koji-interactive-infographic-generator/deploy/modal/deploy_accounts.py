"""Deploy the same checkout to selected registered Modal profiles; never switch traffic."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import subprocess
import sys

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))
from studio.modal_accounts import SERVICES, accounts

TARGETS = [f"agents/{name}/modal_app.py" for name in (
    "prompt-agent", "image-agent", "sketch-agent", "interactive-agent", "eval-agent", "threed-agent",
)]


def deploy(name: str, account: dict, *, include_orchestrator: bool = False) -> None:
    environment = dict(os.environ)
    # Tokens/OAuth from a shell or CI would override the requested profile.
    for key in ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "MODAL_OAUTH_REFRESH_TOKEN",
                "MODAL_OAUTH_CLIENT_ID", "MODAL_OAUTH_CLIENT_SECRET"):
        environment.pop(key, None)
    environment["MODAL_PROFILE"] = account["profile"]
    environment["MODAL_ENVIRONMENT"] = account["environment"]
    command = [sys.executable, "-m", "modal"]

    def run(*arguments):
        subprocess.run([*command, *arguments], cwd=BACKEND, env=environment, check=True)

    print(f"Deploying {name} using profile {account['profile']}", flush=True)
    run("token", "info")
    for target in TARGETS:
        run("deploy", "--env", account["environment"], target)
    if include_orchestrator:
        # Bind the account's orchestrator to that account's explicitly configured URLs.
        values = [f"{key}={account['endpoints'][service]}" for service, key in SERVICES.items()]
        run("secret", "create", "--env", account["environment"], "--force", "agent-urls-secret", *values)
        run("deploy", "--env", account["environment"], "orchestrator/modal_app.py")
    print(f"Deployed {name}. Verify URLs and model volumes, then run the routing health check.", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--account")
    selection.add_argument("--all", action="store_true")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--include-orchestrator", action="store_true")
    args = parser.parse_args()
    if args.config:
        os.environ["KOJI_MODAL_ACCOUNTS_FILE"] = str(args.config.resolve())
    try:
        registry = accounts()
        names = list(registry) if args.all else [args.account]
        if any(name not in registry for name in names):
            raise ValueError("Requested account is not registered")
        for name in names:
            deploy(name, registry[name], include_orchestrator=args.include_orchestrator)
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Deployment stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
