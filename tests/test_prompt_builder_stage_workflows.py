from __future__ import annotations

from pathlib import Path

from defs import load_all
from prompt_builder import build_prompts


ROOT = Path(__file__).resolve().parents[1]


def _workflow(name: str):
    workflows = {wf.name: wf for wf in load_all(ROOT / "workflow_defs_v2")}
    assert name in workflows, f"workflow not found: {name}"
    return workflows[name]


def test_upscale_images_workflow_definition_loads_with_expected_defaults():
    wf = _workflow("upscale-images-i2v")

    assert wf.input_type == "image"
    assert "upscale_model_name" in wf.parameters
    assert "final_scale_factor" in wf.parameters
    assert wf.parameters["upscale_model_name"].default == "RealESRGAN_x2plus.pth"
    assert float(wf.parameters["final_scale_factor"].default) == 0.75


def test_2stage_split_prompt_values_map_to_stage_nodes(tmp_path: Path):
    wf = _workflow("wan-context-2stage-split-prompts")
    image = tmp_path / "sample.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")

    params = {
        "positive_prompt_stage1": "stage one action",
        "positive_prompt_stage2": "stage two continuation",
        "negative_prompt": "bad anatomy, artifacts",
        "randomize_seed": False,
        "tries": 1,
    }
    specs = build_prompts(wf, [image], params, comfy_input_dir=tmp_path)
    assert len(specs) == 1

    prompt = specs[0].prompt_json
    assert prompt["93"]["inputs"]["text"] == "stage one action"
    assert prompt["193"]["inputs"]["text"] == "stage two continuation"
    assert prompt["89"]["inputs"]["text"] == "bad anatomy, artifacts"


def test_3stage_split_prompt_mapping_and_seed_bindings_cover_all_samplers(tmp_path: Path):
    wf = _workflow("wan-context-3stage-split-prompts")
    image = tmp_path / "sample.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")

    params = {
        "positive_prompt_stage1": "stage one",
        "positive_prompt_stage2": "stage two",
        "positive_prompt_stage3": "stage three",
        "negative_prompt": "bad quality",
        "randomize_seed": True,
        "tries": 1,
    }
    specs = build_prompts(wf, [image], params, comfy_input_dir=tmp_path)
    assert len(specs) == 1

    spec = specs[0]
    prompt = spec.prompt_json
    assert spec.seed_used is not None

    assert prompt["93"]["inputs"]["text"] == "stage one"
    assert prompt["193"]["inputs"]["text"] == "stage two"
    assert prompt["293"]["inputs"]["text"] == "stage three"

    seed = int(spec.seed_used)
    for node_id in ["86", "85", "120", "121", "130", "131"]:
        inputs = prompt[node_id]["inputs"]
        if "noise_seed" in inputs:
            assert int(inputs["noise_seed"]) == seed
        if "seed" in inputs:
            assert int(inputs["seed"]) == seed
