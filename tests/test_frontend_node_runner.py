from __future__ import annotations

import subprocess
from pathlib import Path


def test_frontend_state_node_suite_passes():
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        ["node", "--test", str(root / "tests" / "frontend_state.test.mjs")],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(f"node frontend suite failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
