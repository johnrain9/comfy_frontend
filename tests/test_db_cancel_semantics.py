from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from db import QueueDB


def _spec(name: str, seed: int = 1):
    return SimpleNamespace(input_file=name, prompt_json={"name": name}, seed_used=seed)


def test_mixed_succeeded_and_canceled_resolves_to_canceled(tmp_path: Path):
    db = QueueDB(tmp_path / "queue.db")
    try:
        job_id = db.create_job("wf", "/tmp", {}, [_spec("a.png"), _spec("b.png")])
        prompts = db.get_prompts_for_job(job_id)
        db.update_prompt_status(int(prompts[0]["id"]), "succeeded")

        detail = db.cancel_job(job_id)
        assert detail is not None
        assert detail["job"]["status"] == "canceled"
        assert detail["cancel_summary"]["mode"] == "immediate"
    finally:
        db.close()


def test_cancel_running_job_sets_cancel_after_current(tmp_path: Path):
    db = QueueDB(tmp_path / "queue.db")
    try:
        job_id = db.create_job("wf", "/tmp", {}, [_spec("a.png"), _spec("b.png")])
        prompts = db.get_prompts_for_job(job_id)

        db.update_prompt_status(int(prompts[0]["id"]), "running")
        db.update_job_status(job_id)
        detail = db.cancel_job(job_id)

        assert detail is not None
        assert detail["cancel_summary"]["mode"] == "cancel_after_current"
        assert int(detail["cancel_summary"]["running_prompts"]) == 1
        assert int(detail["cancel_summary"]["canceled_pending"]) == 1
        assert detail["job"]["status"] == "running"
    finally:
        db.close()
