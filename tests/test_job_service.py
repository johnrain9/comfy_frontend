from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest

from defs import load_all
from services.job_service import (
    get_workflow_or_error,
    normalize_legacy_submit_params,
    prepare_prompt_specs,
    validate_batch_input_dir,
)


@pytest.fixture(scope="module")
def workflows():
    return {w.name: w for w in load_all(Path(__file__).resolve().parents[1] / "workflow_defs_v2")}


def _write_png(path: Path, width: int, height: int) -> None:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag)
        crc = zlib.crc32(data, crc)
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc & 0xFFFFFFFF)

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"\x00" + (b"\x00\x00\x00" * width) * height))
        + chunk(b"IEND", b"")
    )


def test_get_workflow_or_error_rejects_unknown_name(workflows):
    with pytest.raises(ValueError, match="unknown workflow"):
        get_workflow_or_error(workflows, "missing-workflow")


def test_validate_batch_input_dir_rejects_missing_directory(tmp_path, workflows):
    wf = workflows["wan-context-lite-2stage"]
    with pytest.raises(ValueError, match="input directory not found"):
        validate_batch_input_dir(wf, str(tmp_path / "missing"))


def test_validate_batch_input_dir_rejects_empty_matching_set(tmp_path, workflows):
    wf = workflows["wan-context-lite-2stage"]
    input_dir = tmp_path / "inputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / "note.txt").write_text("x", encoding="utf-8")

    with pytest.raises(ValueError, match="no matching input files"):
        validate_batch_input_dir(wf, str(input_dir))


def test_prepare_prompt_specs_rejects_bad_parameter_type(tmp_path, workflows):
    wf = workflows["wan-context-lite-2stage"]
    comfy_input_dir = tmp_path / "comfy" / "input"
    comfy_input_dir.mkdir(parents=True, exist_ok=True)
    image = tmp_path / "source.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")

    with pytest.raises(ValueError, match="parameter 'tries' must be int"):
        prepare_prompt_specs(
            wf,
            [image],
            {"tries": "abc"},
            comfy_input_dir=comfy_input_dir,
            stage_inputs=True,
        )


def test_normalize_legacy_submit_params_maps_old_lora_fields(workflows):
    wf = workflows["wan-context-lite-2stage"]
    normalized = normalize_legacy_submit_params(
        wf,
        {
            "lora_high_name": "legacy_high.safetensors",
            "lora_low_name": "legacy_low.safetensors",
            "lora_strength": 0.75,
        },
    )

    assert normalized["extra_lora_enabled"] is True
    assert normalized["extra_lora_high_name"] == "legacy_high.safetensors"
    assert normalized["extra_lora_low_name"] == "legacy_low.safetensors"
    assert normalized["extra_lora_strength_high"] == 0.75
    assert normalized["extra_lora_strength_low"] == 0.75
    assert "lora_high_name" not in normalized
    assert "lora_low_name" not in normalized
    assert "lora_strength" not in normalized


def test_prepare_prompt_specs_stages_inputs_and_preserves_original_input_file(tmp_path, workflows):
    wf = workflows["wan-context-lite-2stage"]
    comfy_input_dir = tmp_path / "comfy" / "input"
    comfy_input_dir.mkdir(parents=True, exist_ok=True)
    image = tmp_path / "source image!.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")

    resolved, specs = prepare_prompt_specs(
        wf,
        [image],
        {"tries": 1, "randomize_seed": False},
        comfy_input_dir=comfy_input_dir,
        stage_inputs=True,
    )

    assert resolved["tries"] == 1
    assert len(specs) == 1
    assert specs[0].input_file == str(image.resolve())

    encoded = str(specs[0].prompt_json)
    assert "_video_queue_staging/" in encoded
    assert str(image.resolve()) not in encoded


def test_prepare_prompt_specs_qwen_upscale_uses_real_comfy_field_names(tmp_path, workflows):
    wf = workflows["upscale-qwen-image-edit"]
    comfy_input_dir = tmp_path / "comfy" / "input"
    comfy_input_dir.mkdir(parents=True, exist_ok=True)
    image = tmp_path / "source.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")

    _, specs = prepare_prompt_specs(
        wf,
        [image],
        {},
        comfy_input_dir=comfy_input_dir,
        stage_inputs=True,
    )

    prompt = specs[0].prompt_json
    assert prompt["10"]["inputs"]["prompt"]
    assert prompt["11"]["inputs"]["prompt"]
    assert "text" not in prompt["10"]["inputs"]
    assert "text" not in prompt["11"]["inputs"]
    assert prompt["12"]["inputs"]["reference_latents_method"] == "index_timestep_zero"
    assert prompt["13"]["inputs"]["reference_latents_method"] == "index_timestep_zero"
    assert "method" not in prompt["12"]["inputs"]
    assert "method" not in prompt["13"]["inputs"]


def test_prepare_prompt_specs_normalizes_absolute_output_prefix_to_comfy_relative(tmp_path, workflows):
    wf = workflows["upscale-qwen-image-edit"]
    comfy_input_dir = tmp_path / "comfy" / "input"
    comfy_input_dir.mkdir(parents=True, exist_ok=True)
    image = tmp_path / "source.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")

    _, specs = prepare_prompt_specs(
        wf,
        [image],
        {"output_prefix": "/home/cobra/Pictures/upscaled/upscaled"},
        comfy_input_dir=comfy_input_dir,
        stage_inputs=True,
    )

    prompt = specs[0].prompt_json
    assert specs[0].output_prefix == "Pictures/upscaled/upscaled/source"
    assert prompt["17"]["inputs"]["filename_prefix"] == "Pictures/upscaled/upscaled/source"


def test_prepare_prompt_specs_qwen_upscale_derives_dimensions_from_scale_multiple(tmp_path, workflows):
    wf = workflows["upscale-qwen-image-edit"]
    comfy_input_dir = tmp_path / "comfy" / "input"
    comfy_input_dir.mkdir(parents=True, exist_ok=True)
    image = tmp_path / "portrait.png"
    _write_png(image, 577, 1024)

    _, specs = prepare_prompt_specs(
        wf,
        [image],
        {"scale_multiple": 1.5},
        comfy_input_dir=comfy_input_dir,
        stage_inputs=True,
    )

    prompt = specs[0].prompt_json
    assert prompt["14"]["inputs"]["width"] == 864
    assert prompt["14"]["inputs"]["height"] == 1536


def test_prepare_prompt_specs_qwen_upscale_preserves_aspect_when_min_size_applies(tmp_path, workflows):
    wf = workflows["upscale-qwen-image-edit"]
    comfy_input_dir = tmp_path / "comfy" / "input"
    comfy_input_dir.mkdir(parents=True, exist_ok=True)
    image = tmp_path / "small-portrait.png"
    _write_png(image, 447, 500)

    _, specs = prepare_prompt_specs(
        wf,
        [image],
        {"scale_multiple": 1.0},
        comfy_input_dir=comfy_input_dir,
        stage_inputs=True,
    )

    prompt = specs[0].prompt_json
    assert prompt["14"]["inputs"]["width"] == 512
    assert prompt["14"]["inputs"]["height"] == 576
