from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


class QueueDB:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path).expanduser() if db_path else Path.home() / "video_queue" / "data" / "queue.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              workflow_name TEXT NOT NULL,
              job_name TEXT,
              status TEXT NOT NULL,
              cancel_requested INTEGER NOT NULL DEFAULT 0,
              priority INTEGER NOT NULL DEFAULT 0,
              input_dir TEXT NOT NULL,
              params_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              started_at TEXT,
              finished_at TEXT,
              last_error TEXT,
              log_path TEXT,
              move_processed INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS prompts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
              input_file TEXT NOT NULL,
              prompt_json TEXT NOT NULL,
              status TEXT NOT NULL,
              prompt_id TEXT,
              started_at TEXT,
              finished_at TEXT,
              exit_status TEXT,
              error_detail TEXT,
              output_paths TEXT,
              seed_used INTEGER
            );

            CREATE TABLE IF NOT EXISTS queue_state (
              id INTEGER PRIMARY KEY CHECK (id = 1),
              paused INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS input_dir_history (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              path TEXT NOT NULL UNIQUE,
              last_used_at TEXT NOT NULL,
              use_count INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS prompt_presets (
              name TEXT PRIMARY KEY,
              positive_prompt TEXT NOT NULL DEFAULT '',
              negative_prompt TEXT NOT NULL DEFAULT '',
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings_presets (
              name TEXT PRIMARY KEY,
              payload_json TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_input_dir_history_last_used
              ON input_dir_history(last_used_at DESC);
            CREATE INDEX IF NOT EXISTS idx_prompt_presets_updated_at
              ON prompt_presets(updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_settings_presets_updated_at
              ON settings_presets(updated_at DESC);

            INSERT OR IGNORE INTO queue_state (id, paused) VALUES (1, 0);
            """
        )
        job_cols = {str(row["name"]) for row in self.conn.execute("PRAGMA table_info(jobs)").fetchall()}
        if "cancel_requested" not in job_cols:
            self.conn.execute("ALTER TABLE jobs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0")
        if "job_name" not in job_cols:
            self.conn.execute("ALTER TABLE jobs ADD COLUMN job_name TEXT")
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def is_paused(self) -> bool:
        row = self.conn.execute("SELECT paused FROM queue_state WHERE id=1").fetchone()
        return bool(row["paused"]) if row else False

    def pause(self) -> None:
        self.conn.execute("UPDATE queue_state SET paused=1 WHERE id=1")
        self.conn.commit()

    def resume(self) -> None:
        self.conn.execute("UPDATE queue_state SET paused=0 WHERE id=1")
        self.conn.commit()

    def create_job(
        self,
        workflow_name: str,
        job_name: str | None,
        input_dir: str,
        params_json: dict[str, Any],
        prompt_specs: list[Any],
        priority: int = 0,
        move_processed: bool = False,
    ) -> int:
        created = utc_now()
        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO jobs (
                    workflow_name, job_name, status, cancel_requested, priority, input_dir, params_json, created_at, move_processed
                ) VALUES (?, ?, 'pending', 0, ?, ?, ?, ?, ?)
                """,
                (workflow_name, job_name, priority, input_dir, json.dumps(params_json), created, int(move_processed)),
            )
            job_id = int(cur.lastrowid)
            for spec in prompt_specs:
                self.conn.execute(
                    """
                    INSERT INTO prompts (
                        job_id, input_file, prompt_json, status, output_paths, seed_used
                    ) VALUES (?, ?, ?, 'pending', '[]', ?)
                    """,
                    (
                        job_id,
                        str(spec.input_file),
                        json.dumps(spec.prompt_json),
                        spec.seed_used,
                    ),
                )
        return job_id

    def next_pending_prompt(self, job_id: int | None = None) -> dict[str, Any] | None:
        if self.is_paused():
            return None

        where = "WHERE p.status='pending' AND j.status IN ('pending','running') AND COALESCE(j.cancel_requested, 0)=0"
        params: list[Any] = []
        if job_id is not None:
            where += " AND j.id=?"
            params.append(job_id)

        row = self.conn.execute(
            f"""
            SELECT p.*, j.priority AS job_priority, j.created_at AS job_created_at, j.workflow_name
            FROM prompts p
            JOIN jobs j ON j.id = p.job_id
            {where}
            ORDER BY j.priority DESC, j.created_at ASC, p.id ASC
            LIMIT 1
            """,
            params,
        ).fetchone()
        return dict(row) if row else None

    def update_prompt_status(self, prompt_row_id: int, status: str, **fields: Any) -> None:
        allowed = {
            "prompt_id",
            "started_at",
            "finished_at",
            "exit_status",
            "error_detail",
            "output_paths",
            "seed_used",
        }
        sets = ["status=?"]
        values: list[Any] = [status]

        for key, value in fields.items():
            if key in allowed:
                sets.append(f"{key}=?")
                values.append(value)

        values.append(prompt_row_id)
        self.conn.execute(f"UPDATE prompts SET {', '.join(sets)} WHERE id=?", values)
        self.conn.commit()

    def _job_prompt_counts(self, job_id: int) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) AS c FROM prompts WHERE job_id=? GROUP BY status", (job_id,)
        ).fetchall()
        counts = {row["status"]: int(row["c"]) for row in rows}
        counts.setdefault("pending", 0)
        counts.setdefault("running", 0)
        counts.setdefault("succeeded", 0)
        counts.setdefault("failed", 0)
        counts.setdefault("canceled", 0)
        return counts

    def update_job_status(self, job_id: int) -> str:
        counts = self._job_prompt_counts(job_id)
        total = sum(counts.values())
        now = utc_now()
        job_row = self.conn.execute(
            "SELECT started_at, COALESCE(cancel_requested, 0) AS cancel_requested FROM jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        if not job_row:
            return "pending"
        cancel_requested = bool(job_row["cancel_requested"])

        if total == 0:
            status = "pending"
        elif counts["running"] > 0:
            status = "running"
        elif counts["pending"] > 0:
            status = "pending"
        elif counts["failed"] > 0:
            status = "failed"
        elif counts["succeeded"] == total:
            status = "succeeded"
        elif counts["canceled"] == total:
            status = "canceled"
        elif counts["succeeded"] > 0 and counts["canceled"] > 0 and cancel_requested:
            status = "canceled"
        else:
            status = "succeeded"

        started_at = job_row["started_at"]
        started_val = started_at if started_at else (now if status in {"running", "succeeded", "failed", "canceled"} else None)
        finished_val = now if status in {"succeeded", "failed", "canceled"} else None

        self.conn.execute(
            "UPDATE jobs SET status=?, started_at=COALESCE(started_at, ?), finished_at=? WHERE id=?",
            (status, started_val, finished_val, job_id),
        )
        self.conn.commit()
        return status

    def recover_interrupted(self) -> None:
        now = utc_now()
        with self.conn:
            self.conn.execute(
                """
                UPDATE prompts
                SET status='failed', finished_at=?, exit_status='interrupted',
                    error_detail=COALESCE(error_detail, 'interrupted')
                WHERE status='running'
                """,
                (now,),
            )
            jobs = self.conn.execute("SELECT DISTINCT job_id FROM prompts WHERE exit_status='interrupted'").fetchall()
            for row in jobs:
                self.update_job_status(int(row["job_id"]))

    def list_running_prompts(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT p.*, j.workflow_name, j.status AS job_status
            FROM prompts p
            JOIN jobs j ON j.id = p.job_id
            WHERE p.status='running'
            ORDER BY p.id ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]

    def list_jobs(self, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if status:
            where = "WHERE j.status=?"
            params.append(status)

        rows = self.conn.execute(
            f"""
            SELECT j.*,
                   SUM(CASE WHEN p.status='pending' THEN 1 ELSE 0 END) AS pending_count,
                   SUM(CASE WHEN p.status='running' THEN 1 ELSE 0 END) AS running_count,
                   SUM(CASE WHEN p.status='succeeded' THEN 1 ELSE 0 END) AS succeeded_count,
                   SUM(CASE WHEN p.status='failed' THEN 1 ELSE 0 END) AS failed_count,
                   SUM(CASE WHEN p.status='canceled' THEN 1 ELSE 0 END) AS canceled_count,
                   COUNT(p.id) AS prompt_count
            FROM jobs j
            LEFT JOIN prompts p ON p.job_id=j.id
            {where}
            GROUP BY j.id
            ORDER BY j.created_at DESC
            LIMIT ?
            """,
            [*params, limit],
        ).fetchall()
        return [dict(r) for r in rows]

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        job = self.conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not job:
            return None
        prompts = self.conn.execute(
            "SELECT * FROM prompts WHERE job_id=? ORDER BY id ASC", (job_id,)
        ).fetchall()
        return {
            "job": dict(job),
            "prompts": [dict(p) for p in prompts],
        }

    def cancel_job(self, job_id: int) -> dict[str, Any] | None:
        exists = self.conn.execute("SELECT id FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not exists:
            return None

        canceled_pending = 0
        with self.conn:
            cur = self.conn.execute(
                "UPDATE prompts SET status='canceled', finished_at=? WHERE job_id=? AND status='pending'",
                (utc_now(), job_id),
            )
            canceled_pending = int(cur.rowcount or 0)
            self.conn.execute("UPDATE jobs SET cancel_requested=1 WHERE id=?", (job_id,))

        running_now = int(
            self.conn.execute(
                "SELECT COUNT(*) AS c FROM prompts WHERE job_id=? AND status='running'",
                (job_id,),
            ).fetchone()["c"]
            or 0
        )
        self.update_job_status(job_id)
        detail = self.get_job(job_id)
        if not detail:
            return None
        mode = "cancel_after_current" if running_now > 0 else "immediate"
        detail["cancel_summary"] = {
            "mode": mode,
            "canceled_pending": canceled_pending,
            "running_prompts": running_now,
        }
        return detail

    def retry_job(self, job_id: int) -> dict[str, Any] | None:
        with self.conn:
            self.conn.execute(
                """
                UPDATE prompts
                SET status='pending', prompt_id=NULL, started_at=NULL, finished_at=NULL,
                    exit_status=NULL, error_detail=NULL, output_paths='[]'
                WHERE job_id=? AND status='failed'
                """,
                (job_id,),
            )
            self.conn.execute(
                "UPDATE jobs SET status='pending', cancel_requested=0, started_at=NULL, finished_at=NULL, last_error=NULL WHERE id=?",
                (job_id,),
            )
        self.update_job_status(job_id)
        return self.get_job(job_id)

    def is_cancel_requested(self, job_id: int) -> bool:
        row = self.conn.execute(
            "SELECT COALESCE(cancel_requested, 0) AS cancel_requested FROM jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        return bool(row["cancel_requested"]) if row else False

    def cancel_pending_prompts(self, job_id: int) -> int:
        with self.conn:
            cur = self.conn.execute(
                "UPDATE prompts SET status='canceled', finished_at=? WHERE job_id=? AND status='pending'",
                (utc_now(), job_id),
            )
        return int(cur.rowcount or 0)

    def queue_counts(self) -> dict[str, int]:
        row = self.conn.execute(
            """
            SELECT
              SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending,
              SUM(CASE WHEN status='running' THEN 1 ELSE 0 END) AS running
            FROM prompts
            """
        ).fetchone()
        return {
            "pending": int(row["pending"] or 0),
            "running": int(row["running"] or 0),
        }

    def touch_input_dir_history(self, path: str) -> None:
        now = utc_now()
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO input_dir_history (path, last_used_at, use_count)
                VALUES (?, ?, 1)
                ON CONFLICT(path) DO UPDATE SET
                    last_used_at=excluded.last_used_at,
                    use_count=input_dir_history.use_count + 1
                """,
                (path, now),
            )

    def list_input_dir_history(self, limit: int = 20) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT path
            FROM input_dir_history
            ORDER BY last_used_at DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
        paths = [str(row["path"]) for row in rows if row["path"]]
        if paths:
            return paths

        legacy = self.conn.execute(
            """
            SELECT input_dir
            FROM jobs
            WHERE input_dir IS NOT NULL AND input_dir != ''
            GROUP BY input_dir
            ORDER BY MAX(created_at) DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
        return [str(row["input_dir"]) for row in legacy if row["input_dir"]]

    def get_prompts_for_job(self, job_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM prompts WHERE job_id=? ORDER BY id ASC", (job_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def has_active_prompts_for_input(self, input_file: str, exclude_job_id: int | None = None) -> bool:
        sql = """
            SELECT 1
            FROM prompts p
            JOIN jobs j ON j.id = p.job_id
            WHERE p.input_file=?
              AND p.status IN ('pending','running')
              AND j.status IN ('pending','running')
        """
        params: list[Any] = [str(input_file)]
        if exclude_job_id is not None:
            sql += " AND p.job_id!=?"
            params.append(int(exclude_job_id))
        sql += " LIMIT 1"
        row = self.conn.execute(sql, params).fetchone()
        return row is not None

    def list_prompt_presets(self, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT name, positive_prompt, negative_prompt, updated_at
            FROM prompt_presets
            ORDER BY updated_at DESC, name ASC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
        return [dict(r) for r in rows]

    def save_prompt_preset(self, name: str, positive_prompt: str, negative_prompt: str) -> dict[str, Any]:
        clean_name = str(name or "").strip()
        if not clean_name:
            raise ValueError("preset name is required")
        now = utc_now()
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO prompt_presets (name, positive_prompt, negative_prompt, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    positive_prompt=excluded.positive_prompt,
                    negative_prompt=excluded.negative_prompt,
                    updated_at=excluded.updated_at
                """,
                (clean_name, str(positive_prompt or ""), str(negative_prompt or ""), now),
            )
        return {
            "name": clean_name,
            "positive_prompt": str(positive_prompt or ""),
            "negative_prompt": str(negative_prompt or ""),
            "updated_at": now,
        }

    def list_settings_presets(self, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT name, payload_json, updated_at
            FROM settings_presets
            ORDER BY updated_at DESC, name ASC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            payload_text = str(row["payload_json"] or "{}")
            try:
                payload = json.loads(payload_text)
            except json.JSONDecodeError:
                payload = {}
            out.append(
                {
                    "name": str(row["name"]),
                    "payload": payload if isinstance(payload, dict) else {},
                    "updated_at": str(row["updated_at"]),
                }
            )
        return out

    def save_settings_preset(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        clean_name = str(name or "").strip()
        if not clean_name:
            raise ValueError("preset name is required")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")

        now = utc_now()
        payload_json = json.dumps(payload)
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO settings_presets (name, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (clean_name, payload_json, now),
            )
        return {
            "name": clean_name,
            "payload": payload,
            "updated_at": now,
        }
