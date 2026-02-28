from __future__ import annotations

from pathlib import Path

from defs import load_all, load_one
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


def test_extra_lora_enable_flag_controls_strength_application(tmp_path: Path):
    wf = _workflow("wan-context-2stage")
    image = tmp_path / "sample.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")

    # Disabled extra LoRA should always force strength to 0, even if strength is provided.
    specs_disabled = build_prompts(
        wf,
        [image],
        {
            "randomize_seed": False,
            "tries": 1,
            "extra_lora_enabled": False,
            "extra_lora_strength_high": 1.25,
            "extra_lora_strength_low": 1.1,
        },
        comfy_input_dir=tmp_path,
    )
    p0 = specs_disabled[0].prompt_json
    assert float(p0["201"]["inputs"]["strength_model"]) == 0.0
    assert float(p0["202"]["inputs"]["strength_model"]) == 0.0

    # Enabled extra LoRA should use configured strength.
    specs_enabled = build_prompts(
        wf,
        [image],
        {
            "randomize_seed": False,
            "tries": 1,
            "extra_lora_enabled": True,
            "extra_lora_high_name": "demo_high.safetensors",
            "extra_lora_low_name": "demo_low.safetensors",
            "extra_lora_strength_high": 1.25,
            "extra_lora_strength_low": 1.1,
        },
        comfy_input_dir=tmp_path,
    )
    p1 = specs_enabled[0].prompt_json
    assert float(p1["201"]["inputs"]["strength_model"]) == 1.25
    assert float(p1["202"]["inputs"]["strength_model"]) == 1.1


def test_single_pass_workflow_keeps_core_4step_lora_and_exposes_two_extra_slots(tmp_path: Path):
    wf = _workflow("wan-context-lite-2stage")
    image = tmp_path / "sample.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")

    assert "lora_high_name" not in wf.parameters
    assert "lora_low_name" not in wf.parameters
    assert "extra_lora_enabled" in wf.parameters
    assert "extra_lora2_enabled" in wf.parameters

    specs = build_prompts(wf, [image], {"randomize_seed": False, "tries": 1}, comfy_input_dir=tmp_path)
    prompt = specs[0].prompt_json
    assert prompt["101"]["inputs"]["lora_name"] == "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors"
    assert prompt["102"]["inputs"]["lora_name"] == "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors"
    assert float(prompt["201"]["inputs"]["strength_model"]) == 0.0
    assert float(prompt["202"]["inputs"]["strength_model"]) == 0.0
    assert float(prompt["211"]["inputs"]["strength_model"]) == 0.0
    assert float(prompt["212"]["inputs"]["strength_model"]) == 0.0
    # Disabled extras should fully bypass extra chain to preserve original path quality.
    assert prompt["104"]["inputs"]["model"][0] == "101"
    assert prompt["103"]["inputs"]["model"][0] == "102"


def test_single_pass_enabled_extra_slot_requires_non_empty_names(tmp_path: Path):
    wf = _workflow("wan-context-lite-2stage")
    image = tmp_path / "sample.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")

    specs = build_prompts(
        wf,
        [image],
        {
            "randomize_seed": False,
            "tries": 1,
            "extra_lora_enabled": True,
            "extra_lora_high_name": "",
            "extra_lora_low_name": "",
            "extra_lora_strength_high": 1.0,
            "extra_lora_strength_low": 1.0,
        },
        comfy_input_dir=tmp_path,
    )
    prompt = specs[0].prompt_json
    # Missing names should deactivate slot and preserve baseline path.
    assert float(prompt["201"]["inputs"]["strength_model"]) == 0.0
    assert float(prompt["202"]["inputs"]["strength_model"]) == 0.0
    assert prompt["104"]["inputs"]["model"][0] == "101"
    assert prompt["103"]["inputs"]["model"][0] == "102"


def test_inputless_workflow_can_generate_t2i_prompts_without_files(tmp_path: Path):
    wf_yaml = tmp_path / "image-gen-test.yaml"
    wf_yaml.write_text(
        """
name: image-gen-test
description: "inputless image generation"
category: "image_gen"
input_type: none
input_extensions: [.png]
template_inline:
  "1":
    class_type: CLIPTextEncode
    inputs:
      text: "default"
parameters:
  positive_prompt:
    label: Positive
    type: text
    nodes: ["1"]
    field: text
    default: ""
  tries:
    label: Tries
    type: int
    default: 2
    min: 1
    max: 10
  randomize_seed:
    label: Randomize
    type: bool
    default: false
""".strip(),
        encoding="utf-8",
    )
    wf = load_one(wf_yaml)
    specs = build_prompts(wf, [], {"positive_prompt": "hello world"}, comfy_input_dir=tmp_path)
    assert len(specs) == 2
    assert specs[0].input_file == ""
    assert specs[0].prompt_json["1"]["inputs"]["text"] == "hello world"
    assert specs[0].output_prefix.endswith("prompt_try01")
    assert specs[1].output_prefix.endswith("prompt_try02")


def test_per_file_params_override_single_prompt_per_image(tmp_path: Path):
    wf = _workflow("wan-context-2stage")
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    a.write_bytes(b"\x89PNG\r\n\x1a\n")
    b.write_bytes(b"\x89PNG\r\n\x1a\n")

    specs = build_prompts(
        wf,
        [a, b],
        {"positive_prompt": "global", "randomize_seed": False, "tries": 1},
        per_file_params={
            str(a.resolve()): {"positive_prompt": "prompt A"},
            b.name: {"positive_prompt": "prompt B"},
        },
        comfy_input_dir=tmp_path,
    )
    assert len(specs) == 2
    assert specs[0].prompt_json["93"]["inputs"]["text"] == "prompt A"
    assert specs[1].prompt_json["93"]["inputs"]["text"] == "prompt B"


def test_per_file_params_override_split_prompt_fields(tmp_path: Path):
    wf = _workflow("wan-context-2stage-split-prompts")
    img = tmp_path / "sample.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")

    specs = build_prompts(
        wf,
        [img],
        {
            "positive_prompt_stage1": "global one",
            "positive_prompt_stage2": "global two",
            "negative_prompt": "bad",
            "randomize_seed": False,
            "tries": 1,
        },
        per_file_params={
            str(img.resolve()): {
                "positive_prompt_stage1": "override one",
                "positive_prompt_stage2": "override two",
            }
        },
        comfy_input_dir=tmp_path,
    )
    prompt = specs[0].prompt_json
    assert prompt["93"]["inputs"]["text"] == "override one"
    assert prompt["193"]["inputs"]["text"] == "override two"
