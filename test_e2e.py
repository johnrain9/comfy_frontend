#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("PORT", "8585"))
BASE = f"http://127.0.0.1:{PORT}"


def req(method: str, path: str, payload: dict | None = None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=10) as resp:
        txt = resp.read().decode("utf-8")
        return json.loads(txt) if txt else {}


def wait_up(timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        try:
            req("GET", "/api/workflows")
            return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("server did not start")


def main() -> int:
    proc = subprocess.Popen([
        sys.executable,
        "-m",
        "uvicorn",
        "app:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(PORT),
    ], cwd=str(ROOT))

    try:
        wait_up()
        workflows = req("GET", "/api/workflows")
        assert workflows, "no workflows"

        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "sample.mp4").write_bytes(b"x")

            job = req(
                "POST",
                "/api/jobs",
                {
                    "workflow_name": "upscale-interpolate",
                    "input_dir": str(d),
                    "params": {"scale_by": 2, "multiplier": 2},
                },
            )
            job_id = job["job_id"]

            jobs = req("GET", "/api/jobs")
            assert any(j["id"] == job_id for j in jobs), "job missing from queue"

            req("POST", f"/api/jobs/{job_id}/cancel")
            detail = req("GET", f"/api/jobs/{job_id}")
            assert detail["job"]["status"] in {"canceled", "running", "pending"}

        print("test_e2e passed")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
