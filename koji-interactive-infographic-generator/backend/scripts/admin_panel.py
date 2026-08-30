"""Local-only admin panel for reviewing/approving SKILL.md and memory candidates.

This is a browser UI over the exact same review flow as manage_skill_versions.py
and manage_memories.py -- same DB functions, same `modal run ...::approve_skill_version`
deploy path, no new business logic. It shares their trust boundary (whoever can
set DATABASE_URL on this machine can already list/transition everything here via
those scripts) and adds nothing beyond a nicer UI, so it is NOT hardened for
exposure beyond localhost: it binds 127.0.0.1 only and must never be deployed
publicly or bound to 0.0.0.0.

Run from backend/:
    export DATABASE_URL=...   # your Supabase connection string
    python scripts/admin_panel.py
    # open http://127.0.0.1:8787

No Supabase/Postgres available? Run with no DATABASE_URL set (or pass --demo)
and it starts in DEMO MODE instead: the dashboard renders from fixed sample
data held in memory, and Approve/Reject/Deploy only mutate that in-memory
copy -- no subprocess, no real DB, nothing gets deployed. Every page in demo
mode says so, so it can never be mistaken for real data.
"""

from __future__ import annotations

import html
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from shared.db import (
    get_agent_memory,
    get_skill_version,
    list_agent_memories,
    list_skill_versions,
    transition_agent_memory,
)

HOST = "127.0.0.1"
PORT = 8787
APPROVE_TIMEOUT_SECONDS = 300

# Flipped on by main() when no DATABASE_URL is available (or --demo is passed).
# Left False here so importing this module for tests always exercises the real
# shared.db-backed code path unless a test explicitly opts into demo mode.
DEMO_MODE = False

_DEMO_SKILLS: list[dict] = [
    {
        "version": 7,
        "status": "candidate",
        "old_score": 7.10,
        "new_score": 8.05,
        "validation_count": 10,
        "created_at": "2026-08-30 02:00 UTC",
        "content": (
            "# SKILL.md (demo candidate)\n\n"
            "Grammar Rules\n- Use clear, concrete visual language.\n\n"
            "Educational Context Rules\n- Match terminology to the stated learner level.\n\n"
            "Visual Composition Rules\n- Prefer unambiguous reading order and clear hierarchy.\n\n"
            "Grade-Level Rules\n- Scale label density to grade level.\n\n"
            "Safety Rules\n- Reject sexual/18+ content and sexual content involving minors.\n"
            "- Reject actionable illegal activity.\n\n"
            "Retry Rules\n- On low pedagogical score, add missing labels before regenerating.\n"
        ),
    },
    {
        "version": 6,
        "status": "deployed",
        "old_score": 6.80,
        "new_score": 7.10,
        "validation_count": 10,
        "created_at": "2026-08-23 02:00 UTC",
        "content": "# SKILL.md (demo, previously deployed)\n\n...\n",
    },
]

_DEMO_MEMORIES: list[dict] = [
    {
        "id": "demo-mem-1",
        "scope": "agent",
        "agent_name": "prompt-agent",
        "memory_type": "memento",
        "content": "Preserve the user's original learning objective and all correct constraints during enhancement.",
        "confidence": 0.81,
        "evidence_count": 14,
        "status": "proposed",
    },
    {
        "id": "demo-mem-2",
        "scope": "global",
        "agent_name": None,
        "memory_type": "memento",
        "content": "Preserve the user's stated correction across regeneration without weakening safety or factual accuracy.",
        "confidence": 0.77,
        "evidence_count": 9,
        "status": "proposed",
    },
]


def _list_skill_candidates() -> list[dict]:
    if DEMO_MODE:
        return [row for row in _DEMO_SKILLS if row["status"] == "candidate"]
    return list_skill_versions(status="candidate", limit=50)


def _find_skill(version: int) -> dict | None:
    if DEMO_MODE:
        return next((row for row in _DEMO_SKILLS if row["version"] == version), None)
    return get_skill_version(version)


def _list_memory_candidates() -> list[dict]:
    if DEMO_MODE:
        return [row for row in _DEMO_MEMORIES if row["status"] == "proposed"]
    return list_agent_memories(status="proposed", limit=50)


def _find_memory(memory_id: str) -> dict | None:
    if DEMO_MODE:
        return next((row for row in _DEMO_MEMORIES if row["id"] == memory_id), None)
    return get_agent_memory(memory_id)


def _approve_skill_action(version: int) -> tuple[bool, str]:
    """Returns (success, message-on-success or error-tail-on-failure)."""
    if DEMO_MODE:
        row = next((row for row in _DEMO_SKILLS if row["version"] == version), None)
        if row is None:
            return False, f"No demo skill version {version}"
        row["status"] = "deployed"
        return True, f"[DEMO] SKILL.md v{version} marked deployed (sample data only, nothing real happened)."
    result = subprocess.run(
        [
            sys.executable, "-m", "modal", "run",
            "agents/skill-generator/modal_app.py::approve_skill_version",
            "--version", str(version),
        ],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=APPROVE_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        return False, (result.stderr or result.stdout)[-2000:]
    return True, f"SKILL.md v{version} deployed."


def _transition_memory_action(memory_id: str, target: str) -> None:
    if DEMO_MODE:
        row = next((row for row in _DEMO_MEMORIES if row["id"] == memory_id), None)
        if row is not None:
            row["status"] = target
        return
    transition_agent_memory(memory_id, target)

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>EduVision Memory Admin (local only)</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.9rem; vertical-align: top; }}
th {{ background: #f0f0f0; }}
pre {{ white-space: pre-wrap; background: #f7f7f7; padding: 0.75rem; border-radius: 4px; }}
form {{ display: inline; }}
button {{ cursor: pointer; padding: 0.25rem 0.6rem; margin-right: 0.25rem; }}
.approve {{ background: #d7f5d7; }}
.reject {{ background: #f5d7d7; }}
.msg {{ background: #fff8dc; padding: 0.6rem; border: 1px solid #e0d090; margin-bottom: 1rem; }}
.badge {{ font-size: 0.75rem; padding: 0.1rem 0.4rem; border-radius: 3px; background: #eee; }}
.demo {{ background: #fde2e2; padding: 0.6rem; border: 1px solid #e0a0a0; margin-bottom: 1rem; font-weight: bold; }}
</style></head>
<body>
<h1>EduVision Memory Admin <span class="badge">local only &mdash; 127.0.0.1</span></h1>
{demo_banner}
{message}
<h2>Pending SKILL.md candidates</h2>
{skill_table}
<h2>Pending memory candidates (memento / skill lessons)</h2>
{memory_table}
</body></html>
"""


def _fmt_score(value) -> str:
    return f"{value:.2f}" if isinstance(value, (int, float)) else "?"


def _skill_table() -> str:
    rows = _list_skill_candidates()
    if not rows:
        return "<p><em>No pending SKILL.md candidates.</em></p>"
    body = "".join(
        f"<tr><td>{r['version']}</td>"
        f"<td>{_fmt_score(r['old_score'])} &rarr; {_fmt_score(r['new_score'])}</td>"
        f"<td>{r['validation_count']}</td><td>{html.escape(str(r['created_at']))}</td>"
        f"<td><a href='/skill/{r['version']}'>review</a></td></tr>"
        for r in rows
    )
    return (
        "<table><tr><th>Version</th><th>Score (old &rarr; new)</th>"
        f"<th>Validated on</th><th>Created</th><th></th></tr>{body}</table>"
    )


def _memory_table() -> str:
    rows = _list_memory_candidates()
    if not rows:
        return "<p><em>No pending memory candidates.</em></p>"
    body = "".join(
        f"<tr><td>{html.escape(r['scope'])}/{html.escape(r['agent_name'] or 'global')}</td>"
        f"<td>{html.escape(r['memory_type'])}</td><td>{_fmt_score(r['confidence'])}</td>"
        f"<td>{r['evidence_count']}</td>"
        f"<td>{html.escape((r['content'] or '')[:80])}</td>"
        f"<td><a href='/memory/{r['id']}'>review</a></td></tr>"
        for r in rows
    )
    return (
        "<table><tr><th>Scope/Agent</th><th>Type</th><th>Confidence</th>"
        f"<th>Evidence</th><th>Lesson</th><th></th></tr>{body}</table>"
    )


def _transition_button(path: str, target: str, label: str, css_class: str) -> str:
    return (
        f"<form method='post' action='{path}'>"
        f"<input type='hidden' name='status' value='{html.escape(target)}'>"
        f"<button class='{css_class}'>{html.escape(label)}</button></form>"
    )


class Handler(BaseHTTPRequestHandler):
    def _send_html(self, body: str, status: int = 200) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parts = urlsplit(self.path)
        segments = [s for s in parts.path.split("/") if s]
        query = parse_qs(parts.query)
        try:
            if not segments:
                message = f'<div class="msg">{html.escape(query["msg"][0])}</div>' if "msg" in query else ""
                demo_banner = (
                    '<div class="demo">DEMO MODE &mdash; no DATABASE_URL configured. '
                    "Showing sample data; Approve/Reject only change this in-memory copy, "
                    "nothing real is deployed.</div>"
                    if DEMO_MODE else ""
                )
                self._send_html(
                    PAGE.format(
                        demo_banner=demo_banner, message=message,
                        skill_table=_skill_table(), memory_table=_memory_table(),
                    )
                )
            elif segments[0] == "skill" and len(segments) == 2:
                self._skill_detail(int(segments[1]))
            elif segments[0] == "memory" and len(segments) == 2:
                self._memory_detail(segments[1])
            else:
                self._send_html("<h1>404</h1>", status=404)
        except Exception as exc:  # keep this single-operator tool alive on a bad request
            self._send_html(f"<h1>Error</h1><pre>{html.escape(str(exc))}</pre>", status=500)

    def do_POST(self) -> None:  # noqa: N802
        parts = urlsplit(self.path)
        segments = [s for s in parts.path.split("/") if s]
        length = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(length).decode("utf-8")) if length else {}
        try:
            if segments[0:1] == ["skill"] and len(segments) == 3 and segments[2] == "approve":
                self._approve_skill(int(segments[1]))
            elif segments[0:1] == ["memory"] and len(segments) == 3 and segments[2] == "transition":
                self._transition_memory(segments[1], form.get("status", [""])[0])
            else:
                self._send_html("<h1>404</h1>", status=404)
        except Exception as exc:
            self._send_html(f"<h1>Error</h1><pre>{html.escape(str(exc))}</pre>", status=500)

    def _skill_detail(self, version: int) -> None:
        row = _find_skill(version)
        if row is None:
            self._send_html("<h1>Not found</h1>", status=404)
            return
        actions = ""
        if row["status"] == "candidate":
            actions = (
                f"<form method='post' action='/skill/{version}/approve' "
                f"onsubmit=\"return confirm('Deploy SKILL.md v{version} to the live prompt-agent?')\">"
                f"<button class='approve'>Approve &amp; Deploy</button></form>"
            )
        body = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>Skill v{version}</title></head><body>"
            "<p><a href='/'>&larr; back</a></p>"
            f"<h1>SKILL.md candidate v{version} "
            f"<span class='badge'>{html.escape(row['status'])}</span></h1>"
            f"<p>Score: {_fmt_score(row['old_score'])} &rarr; {_fmt_score(row['new_score'])}</p>"
            f"{actions}<pre>{html.escape(row['content'])}</pre></body></html>"
        )
        self._send_html(body)

    def _memory_detail(self, memory_id: str) -> None:
        row = _find_memory(memory_id)
        if row is None:
            self._send_html("<h1>Not found</h1>", status=404)
            return
        path = f"/memory/{memory_id}/transition"
        actions = ""
        if row["status"] == "proposed":
            actions = _transition_button(path, "approved", "Approve", "approve") + _transition_button(
                path, "rejected", "Reject", "reject"
            )
        elif row["status"] == "approved":
            actions = _transition_button(path, "deployed", "Deploy", "approve")
        body = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Memory candidate</title></head><body>"
            "<p><a href='/'>&larr; back</a></p>"
            f"<h1>{html.escape(row['scope'])}/{html.escape(row['agent_name'] or 'global')} "
            f"&middot; {html.escape(row['memory_type'])} "
            f"<span class='badge'>{html.escape(row['status'])}</span></h1>"
            f"<p>Confidence: {_fmt_score(row['confidence'])} &middot; Evidence: {row['evidence_count']}</p>"
            f"{actions}<pre>{html.escape(row['content'])}</pre></body></html>"
        )
        self._send_html(body)

    def _approve_skill(self, version: int) -> None:
        success, message = _approve_skill_action(version)
        if not success:
            self._send_html(
                f"<h1>Deploy failed</h1><pre>{html.escape(message)}</pre><p><a href='/'>back</a></p>", status=500
            )
            return
        self._redirect(f"/?msg={quote(message)}")

    def _transition_memory(self, memory_id: str, target: str) -> None:
        _transition_memory_action(memory_id, target)
        self._redirect(f"/?msg={quote(f'Memory candidate moved to {target}.')}")

    def log_message(self, format: str, *args) -> None:  # quiet; single-operator local tool
        pass


def main() -> int:
    global DEMO_MODE
    if "--demo" in sys.argv[1:] or not os.environ.get("DATABASE_URL"):
        DEMO_MODE = True
        print("No DATABASE_URL set (or --demo passed) -- starting in DEMO MODE with sample data.")
        print("Approve/Reject/Deploy only change the in-memory sample data; nothing real is deployed.\n")
    server = HTTPServer((HOST, PORT), Handler)
    print(f"EduVision admin panel: http://{HOST}:{PORT}  (local only, Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
