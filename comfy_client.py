from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class ComfyError(Exception):
    pass


class ComfyUnreachableError(ComfyError):
    pass


class ComfyValidationError(ComfyError):
    pass


class ComfyServerError(ComfyError):
    pass


class ComfyTimeoutError(ComfyError):
    pass



def _url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"



def _extract_error_detail(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        parts: list[str] = []
        for key in ("error", "message", "details", "node_errors", "exception_message"):
            if key in payload:
                val = payload[key]
                if isinstance(val, (dict, list)):
                    parts.append(json.dumps(val, ensure_ascii=True))
                else:
                    parts.append(str(val))
        if parts:
            return " | ".join(parts)
        return json.dumps(payload, ensure_ascii=True)
    if isinstance(payload, list):
        return json.dumps(payload, ensure_ascii=True)
    return str(payload)



def _request_json(method: str, base_url: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    req_data = None
    headers = {}
    if payload is not None:
        req_data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(_url(base_url, path), data=req_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
            if not body:
                return {}
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        payload_obj: Any
        try:
            payload_obj = json.loads(body)
        except json.JSONDecodeError:
            payload_obj = body

        detail = _extract_error_detail(payload_obj)
        if exc.code == 400:
            raise ComfyValidationError(detail) from exc
        if 500 <= exc.code < 600:
            raise ComfyServerError(f"HTTP {exc.code}: {detail}") from exc
        raise ComfyError(f"HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionRefusedError) as exc:
        raise ComfyUnreachableError(str(exc)) from exc



def health_check(base_url: str) -> bool:
    try:
        _request_json("GET", base_url, "/system_stats")
        return True
    except ComfyError:
        return False



def queue_prompt(base_url: str, prompt_json: dict[str, Any]) -> str:
    data = _request_json("POST", base_url, "/prompt", {"prompt": prompt_json})
    prompt_id = data.get("prompt_id") if isinstance(data, dict) else None
    if not prompt_id:
        raise ComfyError(f"Comfy response did not include prompt_id: {data}")
    return str(prompt_id)


def get_history_entry(base_url: str, prompt_id: str) -> dict[str, Any] | None:
    history = _request_json("GET", base_url, f"/history/{urllib.parse.quote(prompt_id)}")
    if not isinstance(history, dict):
        return None
    entry = history.get(prompt_id)
    return entry if isinstance(entry, dict) else None


def get_queue_prompt_ids(base_url: str) -> set[str]:
    data = _request_json("GET", base_url, "/queue")
    if not isinstance(data, dict):
        return set()

    out: set[str] = set()
    for key in ("queue_running", "queue_pending"):
        rows = data.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, list) or len(row) < 2:
                continue
            pid = row[1]
            if pid is None:
                continue
            out.add(str(pid))
    return out



def poll_until_done(
    base_url: str,
    prompt_id: str,
    poll_interval: float = 2.0,
    timeout: float = 7200.0,
) -> tuple[bool, str]:
    start = time.time()
    encoded = urllib.parse.quote(prompt_id)

    while True:
        history = _request_json("GET", base_url, f"/history/{encoded}")
        if isinstance(history, dict) and prompt_id in history:
            entry = history.get(prompt_id) or {}
            status = entry.get("status") or {}
            completed = bool(status.get("completed", False))
            status_str = str(status.get("status_str", "unknown"))
            if completed:
                return True, status_str
            if status_str in {"error", "failed", "canceled"}:
                return False, status_str

        if (time.time() - start) > timeout:
            return False, "timeout"
        time.sleep(poll_interval)



def get_outputs(base_url: str, prompt_id: str) -> list[str]:
    history = _request_json("GET", base_url, f"/history/{urllib.parse.quote(prompt_id)}")
    if not isinstance(history, dict) or prompt_id not in history:
        return []

    entry = history[prompt_id] or {}
    outputs = entry.get("outputs") or {}
    if not isinstance(outputs, dict):
        return []

    paths: list[str] = []
    for node_out in outputs.values():
        if not isinstance(node_out, dict):
            continue
        for media_key in ("images", "videos", "gifs"):
            items = node_out.get(media_key) or []
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                filename = item.get("filename")
                if not filename:
                    continue
                subfolder = item.get("subfolder") or ""
                rel = f"{subfolder.strip('/')}/{filename}" if subfolder else str(filename)
                paths.append(rel)

    return paths
