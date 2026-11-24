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
from urllib.parse import parse_qs, urlparse

from .asktable import AskTable
from .documents import SURVEY_LIMIT, TooBig, survey
from .models import ModelError, make_model, scrub
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
                intent_file = task / "intent.txt"
                out.append(
                    {
                        "name": task.name,
                        "folder": str(materials.relative_to(REPO_ROOT)),
                        "intent": intent_file.read_text(encoding="utf-8").strip() if intent_file.is_file() else "",
                        "simulated_available": (task / "simulated-model.json").is_file(),
                    }
                )
    return out


def resolve_folder(folder: str) -> Path:
    p = Path(folder)
    if not p.is_absolute():
        p = REPO_ROOT / p
    p = p.resolve()
    # A task folder (materials/ beside intent.txt and the answer sheet) means its materials: the tool must never
    # read the answer sheet.
    try:
        if (p / "materials").is_dir() and (p / "intent.txt").is_file():
            p = p / "materials"
    except OSError:  # a folder that cannot be opened is not a task folder; reading it gives a plain message
        pass
    return p


def folder_tree(folder: str) -> dict:
    """The chosen folder as a tree, before reading starts. A missing or empty folder gets a plain message."""
    if not folder.strip():
        return {"ok": False, "message": "Choose a folder."}
    p = resolve_folder(folder.strip())
    shown = str(p.relative_to(REPO_ROOT)) if p.is_relative_to(REPO_ROOT) else str(p)
    try:
        exists, is_dir = p.exists(), p.is_dir()
        if is_dir:
            next(p.iterdir(), None)
    except OSError:
        return {"ok": False, "folder": shown, "message": "This folder cannot be opened."}
    if not exists:
        return {"ok": False, "folder": shown, "message": f"There is no folder at {folder.strip()}."}
    if not is_dir:
        return {"ok": False, "folder": shown, "message": f"{folder.strip()} is a file, not a folder."}
    try:
        data = survey(p)
    except TooBig:
        return {"ok": False, "folder": shown,
                "message": f"This folder holds more than {SURVEY_LIMIT} files and folders. Choose a smaller folder."}
    except OSError:
        return {"ok": False, "folder": shown, "message": "This folder cannot be opened."}
    data.update(ok=True, folder=shown)
    if data["files"] == 0:
        data.update(ok=False, message="This folder is empty. There is nothing to read.")
    elif data["to_read"] == 0:
        data.update(ok=False, message="Nothing in this folder can be read yet. The files are listed below with the reason.")
    return data


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
        if path == "/api/tree":
            return self._send_json(folder_tree((parse_qs(urlparse(self.path).query).get("folder") or [""])[0]))
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
        if s.status != "ready":
            return self._error("Reading the folder has not finished yet." if s.status == "reading"
                               else "Reading the folder failed, so there is nothing to answer.", HTTPStatus.CONFLICT)
        try:
            with LOCK:
                if action == "reply":
                    s.reply(body["item"], body["action"], body.get("value"), body.get("who"))
                elif action == "limit":
                    s.limit_choice(body["action"])
                elif action == "item":
                    s.control(body["item"], body["action"], body.get("value"))
                elif action == "review":
                    s.answer_on_review(body["item"], body.get("value"))
                elif action == "finish":
                    s.finish()
                else:
                    return self._error(f"unknown action {action}", HTTPStatus.NOT_FOUND)
        except (KeyError, ValueError) as exc:
            return self._error(str(exc))
        return self._send_json(s.view())

    def _start(self, body: dict):
        folder = body.get("folder") or ""
        intent = body.get("intent") or ""  # may be empty: the tool then works out the goal from the folder
        if not folder:
            return self._error("Choose a folder.")
        folder_path = resolve_folder(folder)
        if not folder_path.is_dir():
            return self._error(f"Not a folder: {folder}")
        try:
            model = make_model(body.get("model") or self.default_model, folder_path)
            threshold = body.get("threshold")
            limit = body.get("limit", "default")
            if limit in ("", "none", "off"):
                limit = None
            s = Session(folder_path, intent, model, rule=body.get("rule") or "cost-weighted",
                        threshold=float(threshold) if threshold not in (None, "") else None,
                        limit=limit)
        except ModelError as exc:
            return self._error(scrub(str(exc)))
        except ValueError as exc:
            return self._error(str(exc))
        # Reading runs in the background; the page polls the session and shows each step as it really happens.
        s._progress_init()
        with LOCK:
            SESSIONS[s.id] = s
        threading.Thread(target=s.start_safely, daemon=True).start()
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
