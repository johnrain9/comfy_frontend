from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = PROJECT_ROOT / "venv" / "bin" / "python"


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class _FakeComfyHandler(BaseHTTPRequestHandler):
    server_version = "FakeComfy/0.1"

    def log_message(self, fmt: str, *args: object) -> None:  # pragma: no cover
        return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @property
    def state(self) -> dict[str, Any]:
        return self.server.state  # type: ignore[attr-defined]

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/system_stats":
            self._send_json({"ok": True})
            return

        if self.path.startswith("/history/"):
            prompt_id = urllib.parse.unquote(self.path.split("/history/", 1)[1])
            hist = self.state["history"].get(prompt_id)
            if not hist:
                self._send_json({})
                return

            hist["polls"] += 1
            complete_after = int(hist.get("complete_after", self.state["complete_after"]))
            completed = hist["polls"] >= complete_after
            status_str = "success" if completed else "running"
            payload: dict[str, Any] = {
                prompt_id: {
                    "status": {"completed": completed, "status_str": status_str},
                }
            }
            if completed:
                payload[prompt_id]["outputs"] = {
                    "108": {
                        "videos": [
                            {
                                "filename": f"{prompt_id}.mp4",
                                "subfolder": "video/test",
                            }
                        ]
                    }
                }
            self._send_json(payload)
            return

        self._send_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/prompt":
            _ = self._read_json()
            self.state["counter"] += 1
            prompt_id = f"fake-{self.state['counter']}"
            self.state["history"][prompt_id] = {
                "polls": 0,
                "complete_after": int(self.state["complete_after"]),
            }
            self._send_json({"prompt_id": prompt_id})
            return

        self._send_json({"error": "not found"}, status=404)


@dataclass
class FakeComfyServer:
    base_url: str
    server: ThreadingHTTPServer
    thread: threading.Thread

    def set_complete_after(self, polls: int) -> None:
        self.server.state["complete_after"] = int(polls)  # type: ignore[attr-defined]

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


@dataclass
class QueueServer:
    base_url: str
    root: Path
    comfy_root: Path
    sample_image: Path
    proc: subprocess.Popen[bytes]
    fake_comfy: FakeComfyServer

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None, expected: int = 200) -> Any:
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                txt = resp.read().decode("utf-8")
                if resp.status != expected:
                    raise AssertionError(f"expected HTTP {expected}, got {resp.status}: {txt}")
                return json.loads(txt) if txt else {}
        except urllib.error.HTTPError as exc:
            txt = exc.read().decode("utf-8", errors="replace")
            if exc.code != expected:
                raise AssertionError(f"expected HTTP {expected}, got {exc.code}: {txt}") from exc
            try:
                return json.loads(txt)
            except json.JSONDecodeError:
                return {"detail": txt}

    def wait_until(self, predicate, timeout: float = 15.0, step: float = 0.1) -> Any:
        end = time.time() + timeout
        last = None
        while time.time() < end:
            last = predicate()
            if last:
                return last
            time.sleep(step)
        raise AssertionError("timed out waiting for predicate")

    def stop(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.fake_comfy.stop()


@pytest.fixture(scope="session")
def queue_server() -> QueueServer:
    fake_port = _find_free_port()
    fake_http = ThreadingHTTPServer(("127.0.0.1", fake_port), _FakeComfyHandler)
    fake_http.state = {
        "counter": 0,
        "history": {},
        "complete_after": 50,
    }
    fake_thread = threading.Thread(target=fake_http.serve_forever, daemon=True)
    fake_thread.start()
    fake = FakeComfyServer(base_url=f"http://127.0.0.1:{fake_port}", server=fake_http, thread=fake_thread)

    temp_dir = Path(tempfile.mkdtemp(prefix="video_queue_tests_"))
    queue_root = temp_dir / "queue_root"
    comfy_root = temp_dir / "comfy_root"
    (queue_root / "data").mkdir(parents=True, exist_ok=True)
    shutil.copytree(PROJECT_ROOT / "static", queue_root / "static")
    (comfy_root / "input").mkdir(parents=True, exist_ok=True)
    (comfy_root / "models" / "loras").mkdir(parents=True, exist_ok=True)

    sample_image = comfy_root / "input" / "sample.png"
    sample_image.write_bytes(b"\x89PNG\r\n\x1a\n")

    port = _find_free_port()
    env = os.environ.copy()
    env.update(
        {
            "VIDEO_QUEUE_ROOT": str(queue_root),
            "WORKFLOW_DEFS_DIR": str(PROJECT_ROOT / "workflow_defs_v2"),
            "COMFY_ROOT": str(comfy_root),
            "COMFY_BASE_URL": fake.base_url,
            "PORT": str(port),
        }
    )

    proc = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    server = QueueServer(
        base_url=f"http://127.0.0.1:{port}",
        root=queue_root,
        comfy_root=comfy_root,
        sample_image=sample_image,
        proc=proc,
        fake_comfy=fake,
    )

    try:
        def _up() -> bool:
            try:
                health = server.request("GET", "/api/health")
                return bool(health)
            except Exception:
                return False

        server.wait_until(_up, timeout=25, step=0.25)
        yield server
    finally:
        server.stop()
        shutil.rmtree(temp_dir, ignore_errors=True)
