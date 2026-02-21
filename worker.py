from __future__ import annotations

import json
import shutil
import threading
import time
from pathlib import Path
from typing import Any

from comfy_client import (
    ComfyError,
    ComfyUnreachableError,
    ComfyValidationError,
    get_outputs,
    health_check,
    poll_until_done,
    queue_prompt,
)
from db import QueueDB, utc_now
from defs import WorkflowDef


class Worker:
    def __init__(
        self,
        db: QueueDB,
        workflows: dict[str, WorkflowDef],
        base_url: str,
        data_dir: str | Path,
    ) -> None:
        self.db = db
        self.workflows = workflows
        self.base_url = base_url
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.logs_dir = self.data_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._state_lock = threading.Lock()
        self._running = False
        self._backoff_idx = 0
        self._backoff_steps = [5, 10, 30, 60]

    @property
    def running(self) -> bool:
        with self._state_lock:
            return self._running

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    def _write_log(self, job_id: int, prompt_row_id: int, lines: list[str]) -> str:
        log_path = self.logs_dir / f"{job_id}_{prompt_row_id}.log"
        with log_path.open("a", encoding="utf-8") as f:
            for line in lines:
                f.write(f"{utc_now()} {line}\n")
        return str(log_path)

    def _move_processed(self, job_id: int) -> None:
        detail = self.db.get_job(job_id)
        if not detail:
            return
        job = detail["job"]
        if not bool(job.get("move_processed", 0)):
            return
        if job.get("status") != "succeeded":
            return

        source_dir = Path(job["input_dir"]).expanduser().resolve()
        processed_dir = source_dir / "_processed"
        processed_dir.mkdir(parents=True, exist_ok=True)

        seen: set[str] = set()
        for prompt in detail["prompts"]:
            src = prompt["input_file"]
            if src in seen:
                continue
            seen.add(src)
            src_path = Path(src)
            if not src_path.exists():
                continue
            dst = processed_dir / src_path.name
            if dst.exists():
                dst = processed_dir / f"{src_path.stem}_{int(time.time())}{src_path.suffix}"
            try:
                shutil.move(str(src_path), str(dst))
            except Exception:
                continue

    def _run_loop(self) -> None:
        with self._state_lock:
            self._running = True

        self.db.recover_interrupted()
        try:
            while not self._stop_event.is_set():
                if self.db.is_paused():
                    time.sleep(1.0)
                    continue

                if not health_check(self.base_url):
                    wait_s = self._backoff_steps[min(self._backoff_idx, len(self._backoff_steps) - 1)]
                    self._backoff_idx = min(self._backoff_idx + 1, len(self._backoff_steps) - 1)
                    time.sleep(wait_s)
                    continue

                self._backoff_idx = 0
                row = self.db.next_pending_prompt()
                if not row:
                    time.sleep(1.0)
                    continue

                prompt_row_id = int(row["id"])
                job_id = int(row["job_id"])
                job_detail = self.db.get_job(job_id)
                if not job_detail:
                    self.db.update_prompt_status(prompt_row_id, "failed", error_detail="missing parent job")
                    continue

                prompt_json = json.loads(row["prompt_json"])

                # Cancel-after-current semantics: if cancel was requested before execution
                # of this pending row, mark it canceled and skip queueing to ComfyUI.
                if self.db.is_cancel_requested(job_id):
                    self.db.update_prompt_status(
                        prompt_row_id,
                        "canceled",
                        finished_at=utc_now(),
                        error_detail="canceled before execution",
                    )
                    self.db.update_job_status(job_id)
                    continue

                self.db.update_prompt_status(prompt_row_id, "running", started_at=utc_now())
                self.db.update_job_status(job_id)

                log_lines = [f"prompt_row={prompt_row_id} status=running"]
                try:
                    comfy_prompt_id = queue_prompt(self.base_url, prompt_json)
                    log_lines.append(f"queued prompt_id={comfy_prompt_id}")
                    self.db.update_prompt_status(prompt_row_id, "running", prompt_id=comfy_prompt_id)

                    ok, status = poll_until_done(self.base_url, comfy_prompt_id)
                    if ok:
                        output_paths = get_outputs(self.base_url, comfy_prompt_id)
                        self.db.update_prompt_status(
                            prompt_row_id,
                            "succeeded",
                            finished_at=utc_now(),
                            exit_status=status,
                            output_paths=json.dumps(output_paths),
                        )
                        log_lines.append(f"status=succeeded prompt_id={comfy_prompt_id}")
                    else:
                        self.db.update_prompt_status(
                            prompt_row_id,
                            "failed",
                            finished_at=utc_now(),
                            exit_status=status,
                            error_detail=f"Comfy returned status={status}",
                        )
                        log_lines.append(f"status=failed prompt_id={comfy_prompt_id} detail={status}")

                except ComfyValidationError as exc:
                    self.db.update_prompt_status(
                        prompt_row_id,
                        "failed",
                        finished_at=utc_now(),
                        exit_status="validation_error",
                        error_detail=str(exc),
                    )
                    log_lines.append(f"status=failed validation_error={exc}")
                except ComfyUnreachableError as exc:
                    self.db.update_prompt_status(
                        prompt_row_id,
                        "failed",
                        finished_at=utc_now(),
                        exit_status="unreachable",
                        error_detail=str(exc),
                    )
                    log_lines.append(f"status=failed unreachable={exc}")
                except ComfyError as exc:
                    self.db.update_prompt_status(
                        prompt_row_id,
                        "failed",
                        finished_at=utc_now(),
                        exit_status="error",
                        error_detail=str(exc),
                    )
                    log_lines.append(f"status=failed error={exc}")
                except Exception as exc:
                    self.db.update_prompt_status(
                        prompt_row_id,
                        "failed",
                        finished_at=utc_now(),
                        exit_status="exception",
                        error_detail=str(exc),
                    )
                    log_lines.append(f"status=failed exception={exc}")

                log_path = self._write_log(job_id, prompt_row_id, log_lines)
                self.db.conn.execute("UPDATE jobs SET log_path=? WHERE id=?", (log_path, job_id))
                self.db.conn.commit()

                if self.db.is_cancel_requested(job_id):
                    self.db.cancel_pending_prompts(job_id)

                job_status = self.db.update_job_status(job_id)
                if job_status == "succeeded":
                    self._move_processed(job_id)

        finally:
            with self._state_lock:
                self._running = False


__all__ = ["Worker"]
