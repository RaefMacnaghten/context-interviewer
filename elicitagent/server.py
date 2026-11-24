"""A small local web server: plain HTML, CSS and JavaScript, no build step.

It listens on 127.0.0.1 only. Sessions live in memory; each run's brief and gap
trace are written to the runs/ folder.
"""

from __future__ import annotations

import json
import mimetypes
import os
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .asktable import AskTable
from .models import ModelError, make_model
from .session import REPO_ROOT, Session

WEB_DIR = Path(__file__).resolve().parent / "web"
TASKS_DIR = REPO_ROOT / "tasks"

SESSIONS: dict[str, Session] = {}
LOCK = threading.Lock()


def list_tasks() -> list[dict]:
    out = []
    if TASKS_DIR.is_dir():
        for task in sorted(TASKS_DIR.iterdir()):
            materials = task / "materials"
            if materials.is_dir():
                request_file = task / "request.txt"
                out.append(
                    {
                        "name": task.name,
                        "folder": str(materials.relative_to(REPO_ROOT)),
                        "request": request_file.read_text(encoding="utf-8").strip() if request_file.is_file() else "",
                        "simulated_available": (task / "simulated-model.json").is_file(),
                    }
                )
    return out


def resolve_folder(folder: str) -> Path:
    p = Path(folder)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return p.resolve()


class Handler(BaseHTTPRequestHandler):
    server_version = "ElicitAgent/0.1"
    default_model = "auto"

    def log_message(self, fmt, *args):  # keep the terminal quiet
        pass

    # ------------------------------------------------------------ helpers

    def _send_json(self, data, status=HTTPStatus.OK):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, message, status=HTTPStatus.BAD_REQUEST):
        self._send_json({"error": message}, status)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _session(self, sid: str) -> Session | None:
        with LOCK:
            return SESSIONS.get(sid)

    # ------------------------------------------------------------ GET

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/config":
            table = AskTable.load()
            return self._send_json(
                {
                    "tasks": list_tasks(),
                    "rules": [
                        {"name": r, "label": table.rule_label(r), "threshold": table.default_threshold(r),
                         "threshold_name": table.rules[r].get("threshold_name"), "settings": table.rules[r].get("settings", [])}
                        for r in table.rule_names()
                    ],
                    "key_present": bool(os.environ.get("ANTHROPIC_API_KEY")),
                    "default_model": self.default_model,
                    "limit_start": table.limit_start,
                }
            )
        if path.startswith("/api/session/"):
            parts = path.strip("/").split("/")
            s = self._session(parts[2]) if len(parts) >= 3 else None
            if not s:
                return self._error("no such session", HTTPStatus.NOT_FOUND)
            if len(parts) == 5 and parts[3] == "why":
                try:
                    return self._send_json(s.why(parts[4]))
                except KeyError:
                    return self._error("no such item", HTTPStatus.NOT_FOUND)
            if len(parts) == 4 and parts[3] in ("brief.md", "gap-trace.jsonl"):
                target = s.brief_path if parts[3] == "brief.md" else s.trace.path
                if not target or not target.is_file():
                    return self._error("not written yet", HTTPStatus.NOT_FOUND)
                body = target.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/markdown; charset=utf-8" if parts[3] == "brief.md" else "application/x-ndjson; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="{s.task}-run-{s.run}-{parts[3]}"')
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return None
            return self._send_json(s.view())
        return self._static(path)

    def _static(self, path: str):
        if path in ("", "/"):
            path = "/index.html"
        target = (WEB_DIR / path.lstrip("/")).resolve()
        if not target.is_relative_to(WEB_DIR) or not target.is_file():
            return self._error("not found", HTTPStatus.NOT_FOUND)
        body = target.read_bytes()
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") or ctype.endswith("javascript") else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------ POST

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = self._body()
        except json.JSONDecodeError:
            return self._error("body is not JSON")
        if path == "/api/session":
            return self._start(body)
        parts = path.strip("/").split("/")
        if len(parts) < 4 or parts[0] != "api" or parts[1] != "session":
            return self._error("not found", HTTPStatus.NOT_FOUND)
        s = self._session(parts[2])
        if not s:
            return self._error("no such session", HTTPStatus.NOT_FOUND)
        action = parts[3]
        try:
            with LOCK:
                if action == "reply":
                    s.reply(body["item"], body["action"], body.get("value"), body.get("who"))
                elif action == "limit":
                    s.limit_choice(body["action"])
                elif action == "item":
                    s.control(body["item"], body["action"], body.get("value"))
                elif action == "finish":
                    s.finish()
                else:
                    return self._error(f"unknown action {action}", HTTPStatus.NOT_FOUND)
        except (KeyError, ValueError) as exc:
            return self._error(str(exc))
        return self._send_json(s.view())

    def _start(self, body: dict):
        folder = body.get("folder") or ""
        request = body.get("request") or ""
        if not folder or not request.strip():
            return self._error("Choose a folder and say what you want the agent to do.")
        folder_path = resolve_folder(folder)
        if not folder_path.is_dir():
            return self._error(f"Not a folder: {folder}")
        try:
            model = make_model(body.get("model") or self.default_model, folder_path)
            threshold = body.get("threshold")
            limit = body.get("limit", "default")
            if limit in ("", "none", "off"):
                limit = None
            s = Session(folder_path, request, model, rule=body.get("rule") or "cost-weighted",
                        threshold=float(threshold) if threshold not in (None, "") else None,
                        limit=limit if limit in (None, "default") else float(limit)).start()
        except ModelError as exc:
            return self._error(str(exc))
        except ValueError as exc:
            return self._error(str(exc))
        with LOCK:
            SESSIONS[s.id] = s
        return self._send_json(s.view())


def serve(host: str = "127.0.0.1", port: int = 8765, model: str = "auto") -> None:
    Handler.default_model = model
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"ElicitAgent is running at http://{host}:{port}/  (Ctrl+C to stop)")
    which = model
    if model == "auto":
        which = "anthropic (key found)" if os.environ.get("ANTHROPIC_API_KEY") else "simulated (no ANTHROPIC_API_KEY set)"
    print(f"Model: {which}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
