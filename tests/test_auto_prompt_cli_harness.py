from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / "venv" / "bin" / "python"


def run_cmd(args: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(
        [str(PY), str(ROOT / "auto_prompt_cli.py"), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return p.returncode, p.stdout, p.stderr


def test_cli_mock_both_stage_outputs_json(tmp_path: Path):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")

    code, out, err = run_cmd([
        "--mock",
        "--stage",
        "both",
        "--workflow-name",
        "wan-context-2stage",
        "--image",
        str(img),
    ])
    assert code == 0, err
    payload = json.loads(out)
    assert payload["stage"] == "both"
    assert payload["workflow_name"] == "wan-context-2stage"
    assert len(payload["items"]) == 1
    assert "caption" in payload["items"][0]
    assert "motion_prompt" in payload["items"][0]


def test_cli_motion_stage_accepts_captions_file(tmp_path: Path):
    img = tmp_path / "y.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    cap = tmp_path / "caps.json"
    cap.write_text(json.dumps({str(img.resolve()): "provided caption"}), encoding="utf-8")

    code, out, err = run_cmd([
        "--mock",
        "--stage",
        "motion",
        "--workflow-name",
        "wan-context-2stage",
        "--captions-file",
        str(cap),
    ])
    assert code == 0, err
    payload = json.loads(out)
    assert payload["items"][0]["caption"] == "provided caption"


def test_cli_requires_captions_for_motion_when_no_images(tmp_path: Path):
    code, _out, err = run_cmd([
        "--mock",
        "--stage",
        "motion",
        "--workflow-name",
        "wan-context-2stage",
    ])
    assert code == 1
    assert "captions required for motion stage" in err
