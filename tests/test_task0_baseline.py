from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from defs import load_all
from prompt_builder import build_prompts, resolve_params


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "baseline"
VENV_PYTHON = PROJECT_ROOT / "venv" / "bin" / "python"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonicalize_seed_fields(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"seed", "noise_seed"} and isinstance(item, int):
                out[key] = "__SEED__"
            else:
                out[key] = _canonicalize_seed_fields(item)
        return out
    if isinstance(value, list):
        return [_canonicalize_seed_fields(item) for item in value]
    return value


def _serialize_specs(specs: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for spec in specs:
        out.append(
            {
                "input_file": spec.input_file,
                "output_prefix": spec.output_prefix,
                "seed_used": "__SEED__" if spec.seed_used is not None else None,
                "prompt_json": _canonicalize_seed_fields(spec.prompt_json),
            }
        )
    return out


def _run_cli(args: list[str], env: dict[str, str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        [str(VENV_PYTHON), str(PROJECT_ROOT / "cli.py"), *args],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _prepare_cli_env(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    queue_root = tmp_path / "queue_root"
    comfy_root = tmp_path / "comfy_root"
    input_dir = comfy_root / "input"
    (queue_root / "data").mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)

    sample_image = input_dir / "sample.png"
    sample_image.write_bytes(b"\x89PNG\r\n\x1a\n")

    env = os.environ.copy()
    env.update(
        {
            # Intentionally unreachable so CLI fallback code paths are exercised.
            "VIDEO_QUEUE_API": "http://127.0.0.1:9",
            "VIDEO_QUEUE_ROOT": str(queue_root),
            "WORKFLOW_DEFS_DIR": str(PROJECT_ROOT / "workflow_defs_v2"),
            "COMFY_ROOT": str(comfy_root),
        }
    )
    return env, input_dir, sample_image


def _normalize_cli_dry_run_output(output: str, input_dir: Path, sample_image: Path) -> str:
    text = output.replace(str(sample_image), "<INPUT_IMAGE_PATH>")
    text = text.replace(str(input_dir), "<INPUT_DIR>")
    text = re.sub(r"/tmp/task0_cli_[^/\s]*/[^\s]*", "<TMP_PATH>", text)
    return text


def test_api_workflows_payload_schema_snapshot(queue_server):
    actual = queue_server.request("GET", "/api/workflows")

    assert isinstance(actual, list)
    assert actual

    for workflow in actual:
        assert isinstance(workflow.get("name"), str)
        assert isinstance(workflow.get("display_name"), str)
        assert isinstance(workflow.get("group"), str)
        assert isinstance(workflow.get("description"), str)
        assert workflow.get("input_type") in {"image", "video"}
        assert isinstance(workflow.get("input_extensions"), list)
        assert isinstance(workflow.get("supports_resolution"), bool)
        parameters = workflow.get("parameters")
        assert isinstance(parameters, dict)
        for param in parameters.values():
            assert isinstance(param.get("label"), str)
            assert isinstance(param.get("type"), str)
            assert set(param.keys()) == {"label", "type", "default", "min", "max"}

    expected = _read_json(FIXTURES_ROOT / "api" / "workflows_payload.json")
    assert actual == expected


def test_prompt_generation_golden_fixtures_cover_two_workflows_and_multi_try():
    workflow_map = {wf.name: wf for wf in load_all(PROJECT_ROOT / "workflow_defs_v2")}

    scenarios = [
        {
            "fixture": "wan-context-lite-2stage.single.json",
            "workflow": "wan-context-lite-2stage",
            "input_files": [Path("/tmp/task0_comfy/input/sample.png")],
            "params": {
                "positive_prompt": "(at 0 second: alpha)(at 3 second: beta)(at 7 second: gamma)",
                "negative_prompt": "bad anatomy",
                "randomize_seed": False,
                "tries": 1,
                "output_prefix": "video/task0-lite",
                "lora_high_name": "lite_high.safetensors",
                "lora_low_name": "lite_low.safetensors",
                "lora_strength": 0.85,
            },
        },
        {
            "fixture": "wan-context-2stage.single.json",
            "workflow": "wan-context-2stage",
            "input_files": [Path("/tmp/task0_comfy/input/sample.png")],
            "params": {
                "positive_prompt": "(at 0 second: cat)(at 3 second: walk)(at 7 second: city)",
                "negative_prompt": "low quality",
                "randomize_seed": False,
                "tries": 1,
                "output_prefix": "video/task0-main",
                "lora_high_name": "main_high.safetensors",
                "lora_low_name": "main_low.safetensors",
                "lora_strength": 1.0,
            },
        },
        {
            "fixture": "wan-context-lite-2stage.multi_try.json",
            "workflow": "wan-context-lite-2stage",
            "input_files": [Path("/tmp/task0_comfy/input/sample.png")],
            "params": {
                "positive_prompt": "(at 0 second: alpha)(at 3 second: beta)(at 7 second: gamma)",
                "negative_prompt": "bad anatomy",
                "randomize_seed": False,
                "tries": 3,
                "output_prefix": "video/task0-lite",
                "lora_high_name": "lite_high.safetensors",
                "lora_low_name": "lite_low.safetensors",
                "lora_strength": 0.85,
            },
        },
    ]

    for scenario in scenarios:
        workflow = workflow_map[scenario["workflow"]]
        resolved = resolve_params(workflow, scenario["params"])
        specs = build_prompts(
            workflow,
            scenario["input_files"],
            resolved,
            comfy_input_dir=Path("/tmp/task0_comfy/input"),
            resolution=(640, 1136),
            flip_orientation=False,
        )
        actual = _serialize_specs(specs)
        expected = _read_json(FIXTURES_ROOT / "prompts" / scenario["fixture"])
        assert actual == expected


def test_cli_list_output_snapshot(tmp_path: Path):
    env, _, _ = _prepare_cli_env(tmp_path)
    code, out, err = _run_cli(["list"], env)
    assert code == 0, err

    expected = (FIXTURES_ROOT / "cli" / "list.txt").read_text(encoding="utf-8")
    assert out == expected


def test_cli_status_output_snapshot(tmp_path: Path):
    env, _, _ = _prepare_cli_env(tmp_path)
    code, out, err = _run_cli(["status"], env)
    assert code == 0, err

    expected = (FIXTURES_ROOT / "cli" / "status_empty.txt").read_text(encoding="utf-8")
    assert out == expected


def test_cli_submit_dry_run_output_snapshot(tmp_path: Path):
    env, input_dir, sample_image = _prepare_cli_env(tmp_path)
    code, out, err = _run_cli(
        [
            "submit",
            "--workflow",
            "wan-context-lite-2stage",
            "--dir",
            str(input_dir),
            "--dry-run",
            "--param",
            "randomize_seed=false",
            "--param",
            "tries=1",
            "--param",
            "positive_prompt=(at 0 second: alpha)(at 3 second: beta)(at 7 second: gamma)",
            "--param",
            "negative_prompt=bad anatomy",
            "--param",
            "output_prefix=video/task0-cli",
            "--param",
            "lora_high_name=cli_high.safetensors",
            "--param",
            "lora_low_name=cli_low.safetensors",
            "--param",
            "lora_strength=0.8",
        ],
        env,
    )
    assert code == 0, err

    normalized = _normalize_cli_dry_run_output(out, input_dir=input_dir, sample_image=sample_image)
    expected = (FIXTURES_ROOT / "cli" / "submit_dry_run.txt").read_text(encoding="utf-8")
    assert normalized == expected
