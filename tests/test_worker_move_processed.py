from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from db import QueueDB
from worker import Worker


def _spec(path: str, seed: int = 1):
    return SimpleNamespace(input_file=path, prompt_json={"name": path}, seed_used=seed)


def test_move_processed_skips_files_still_referenced_by_active_prompts(tmp_path: Path):
    src_dir = tmp_path / "inputs"
    src_dir.mkdir(parents=True, exist_ok=True)
    src_file = src_dir / "a.png"
    src_file.write_bytes(b"png")

    db = QueueDB(tmp_path / "queue.db")
    try:
        # Job 1 (succeeded, move_processed enabled)
        job1 = db.create_job("wf", None, str(src_dir), {}, [_spec(str(src_file))], move_processed=True)
        p1 = db.get_prompts_for_job(job1)[0]
        db.update_prompt_status(int(p1["id"]), "succeeded")
        db.update_job_status(job1)

        # Job 2 (still pending) references the same input file.
        job2 = db.create_job("wf", None, str(src_dir), {}, [_spec(str(src_file))], move_processed=True)
        db.update_job_status(job2)

        worker = Worker(db, workflows={}, base_url="http://127.0.0.1:8188", data_dir=tmp_path)
        worker._move_processed(job1)
        assert src_file.exists(), "source file should not be moved while another active prompt references it"

        # Once the other job is no longer active, move should proceed.
        p2 = db.get_prompts_for_job(job2)[0]
        db.update_prompt_status(int(p2["id"]), "canceled")
        db.update_job_status(job2)

        worker._move_processed(job1)
        moved = src_dir / "_processed" / src_file.name
        assert moved.exists(), "source file should be moved after no active references remain"
        assert not src_file.exists()
    finally:
        db.close()

