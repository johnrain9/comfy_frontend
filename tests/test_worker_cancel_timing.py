from __future__ import annotations

import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import worker as worker_mod
from db import QueueDB
from worker import Worker


def _spec(path: str, seed: int = 1):
    return SimpleNamespace(input_file=path, prompt_json={"name": path}, seed_used=seed)


def _wait_until(predicate, timeout: float = 5.0, step: float = 0.05):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        last = predicate()
        if last:
            return last
        time.sleep(step)
    raise AssertionError("timed out waiting for predicate")


def _job_with_two_prompts(db: QueueDB) -> int:
    return db.create_job("wf", None, "/tmp", {}, [_spec("a.png"), _spec("b.png")])


def test_cancel_before_pickup_never_queues_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = QueueDB(tmp_path / "queue.db")
    calls: list[object] = []
    try:
        job_id = _job_with_two_prompts(db)
        detail = db.cancel_job(job_id)
        assert detail is not None

        monkeypatch.setattr(worker_mod, "health_check", lambda _base_url: True)
        monkeypatch.setattr(worker_mod, "queue_prompt", lambda *_args, **_kwargs: calls.append("queued"))

        worker = Worker(db, workflows={}, base_url="http://127.0.0.1:8188", data_dir=tmp_path)
        worker.start()
        try:
            _wait_until(lambda: db.get_job(job_id)["job"]["status"] == "canceled")
            time.sleep(0.2)
            assert calls == []
        finally:
            worker.stop()
    finally:
        db.close()


def test_cancel_after_pickup_before_queue_submission_cancels_remaining_pending(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = QueueDB(tmp_path / "queue.db")
    queue_entered = threading.Event()
    release_queue = threading.Event()
    try:
        job_id = _job_with_two_prompts(db)

        monkeypatch.setattr(worker_mod, "health_check", lambda _base_url: True)

        def fake_queue_prompt(_base_url: str, _prompt_json: dict) -> str:
            queue_entered.set()
            assert release_queue.wait(timeout=5)
            return "pid-before-submit"

        monkeypatch.setattr(worker_mod, "queue_prompt", fake_queue_prompt)
        monkeypatch.setattr(worker_mod, "poll_until_done", lambda *_args, **_kwargs: (True, "success"))
        monkeypatch.setattr(worker_mod, "get_outputs", lambda *_args, **_kwargs: ["video/test/pid-before-submit.mp4"])

        worker = Worker(db, workflows={}, base_url="http://127.0.0.1:8188", data_dir=tmp_path)
        worker.start()
        try:
            _wait_until(
                lambda: (
                    queue_entered.is_set()
                    and (detail := db.get_job(job_id))
                    and detail["prompts"][0]["status"] == "running"
                    and not detail["prompts"][0]["prompt_id"]
                    and detail["prompts"][1]["status"] == "pending"
                    and detail
                )
            )

            canceled = db.cancel_job(job_id)
            assert canceled is not None
            assert canceled["cancel_summary"]["mode"] == "cancel_after_current"
            release_queue.set()

            terminal = _wait_until(
                lambda: (
                    (detail := db.get_job(job_id))
                    and detail["job"]["status"] in {"canceled", "failed", "succeeded"}
                    and detail
                )
            )
            assert terminal["job"]["status"] == "canceled"
            assert [p["status"] for p in terminal["prompts"]] == ["succeeded", "canceled"]
            assert terminal["prompts"][0]["prompt_id"] == "pid-before-submit"
        finally:
            release_queue.set()
            worker.stop()
    finally:
        db.close()


def test_cancel_while_polling_in_progress_allows_current_prompt_and_cancels_rest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = QueueDB(tmp_path / "queue.db")
    poll_entered = threading.Event()
    release_poll = threading.Event()
    try:
        job_id = _job_with_two_prompts(db)

        monkeypatch.setattr(worker_mod, "health_check", lambda _base_url: True)
        monkeypatch.setattr(worker_mod, "queue_prompt", lambda *_args, **_kwargs: "pid-polling")

        def fake_poll_until_done(*_args, **_kwargs):
            poll_entered.set()
            assert release_poll.wait(timeout=5)
            return True, "success"

        monkeypatch.setattr(worker_mod, "poll_until_done", fake_poll_until_done)
        monkeypatch.setattr(worker_mod, "get_outputs", lambda *_args, **_kwargs: ["video/test/pid-polling.mp4"])

        worker = Worker(db, workflows={}, base_url="http://127.0.0.1:8188", data_dir=tmp_path)
        worker.start()
        try:
            _wait_until(
                lambda: (
                    poll_entered.is_set()
                    and (detail := db.get_job(job_id))
                    and detail["prompts"][0]["status"] == "running"
                    and detail["prompts"][0]["prompt_id"] == "pid-polling"
                    and detail["prompts"][1]["status"] == "pending"
                    and detail
                )
            )

            canceled = db.cancel_job(job_id)
            assert canceled is not None
            assert canceled["cancel_summary"]["mode"] == "cancel_after_current"
            release_poll.set()

            terminal = _wait_until(
                lambda: (
                    (detail := db.get_job(job_id))
                    and detail["job"]["status"] in {"canceled", "failed", "succeeded"}
                    and detail
                )
            )
            assert terminal["job"]["status"] == "canceled"
            assert [p["status"] for p in terminal["prompts"]] == ["succeeded", "canceled"]
        finally:
            release_poll.set()
            worker.stop()
    finally:
        db.close()


def test_cancel_after_first_prompt_completion_cancels_next_pending_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = QueueDB(tmp_path / "queue.db")
    call_count = 0
    try:
        job_id = _job_with_two_prompts(db)

        monkeypatch.setattr(worker_mod, "health_check", lambda _base_url: True)

        def fake_queue_prompt(*_args, **_kwargs) -> str:
            nonlocal call_count
            call_count += 1
            return f"pid-{call_count}"

        def fake_poll_until_done(_base_url: str, prompt_id: str, **_kwargs):
            if prompt_id == "pid-1":
                db.pause()
                return True, "success"
            raise AssertionError("second prompt should not start before cancel is applied")

        monkeypatch.setattr(worker_mod, "queue_prompt", fake_queue_prompt)
        monkeypatch.setattr(worker_mod, "poll_until_done", fake_poll_until_done)
        monkeypatch.setattr(worker_mod, "get_outputs", lambda *_args, **_kwargs: ["video/test/pid-1.mp4"])

        worker = Worker(db, workflows={}, base_url="http://127.0.0.1:8188", data_dir=tmp_path)
        worker.start()
        try:
            detail = _wait_until(
                lambda: (
                    (current := db.get_job(job_id))
                    and current["prompts"][0]["status"] == "succeeded"
                    and current["prompts"][1]["status"] == "pending"
                    and current
                )
            )
            assert detail["job"]["status"] == "pending"

            canceled = db.cancel_job(job_id)
            assert canceled is not None
            assert canceled["cancel_summary"]["mode"] == "immediate"

            final_detail = db.get_job(job_id)
            assert final_detail is not None
            assert final_detail["job"]["status"] == "canceled"
            assert [p["status"] for p in final_detail["prompts"]] == ["succeeded", "canceled"]
            assert call_count == 1
        finally:
            worker.stop()
    finally:
        db.close()
