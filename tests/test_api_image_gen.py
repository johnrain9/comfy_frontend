from __future__ import annotations

import json
from pathlib import Path


def test_image_gen_t2i_submit_without_input_dir_succeeds_and_completed_detail_has_outputs(queue_server_factory):
    server = queue_server_factory(
        {
            "image-gen-test-t2i.yaml": """
name: image-gen-test-t2i
display_name: "Image Gen Test T2I"
group: "Image Gen"
category: "image_gen"
description: "Inputless test workflow for API coverage"
input_type: none
input_extensions: [.png]
template_inline:
  "1":
    class_type: CLIPTextEncode
    inputs:
      text: "default prompt"
  "2":
    class_type: SaveImage
    inputs:
      filename_prefix: "image/test"
parameters:
  positive_prompt:
    label: "Positive prompt"
    type: text
    nodes: ["1"]
    field: text
    default: ""
  output_prefix:
    label: "Output prefix"
    type: text
    nodes: ["2"]
    field: filename_prefix
    default: "image/test"
  randomize_seed:
    label: "Randomize seed"
    type: bool
    default: false
  tries:
    label: "Tries"
    type: int
    default: 1
    min: 1
    max: 10
""".strip()
        }
    )
    server.request("POST", "/api/queue/clear")
    server.fake_comfy.set_complete_after(1)

    job = server.request(
        "POST",
        "/api/jobs",
        {
            "workflow_name": "image-gen-test-t2i",
            "input_dir": "",
            "params": {
                "positive_prompt": "studio portrait, cinematic lighting",
                "output_prefix": "image/t2i_test",
            },
            "split_by_input": False,
        },
        expected=201,
    )
    assert int(job["prompt_count"]) == 1

    terminal = server.wait_until(
        lambda: (
            (detail := server.request("GET", f"/api/jobs/{job['job_id']}"))
            and detail["job"]["status"] in {"succeeded", "failed", "canceled"}
            and detail
        ),
        timeout=10,
        step=0.2,
    )
    assert terminal["job"]["status"] == "succeeded"
    assert len(terminal["prompts"]) == 1
    prompt = terminal["prompts"][0]
    assert prompt["input_file"] == ""
    assert prompt["output_paths"] != "[]"
    prompt_json = json.loads(prompt["prompt_json"])
    assert prompt_json["1"]["inputs"]["text"] == "studio portrait, cinematic lighting"


def test_image_gen_i2i_submit_succeeds_and_completed_detail_has_outputs(queue_server, tmp_path: Path):
    queue_server.request("POST", "/api/queue/clear")
    queue_server.fake_comfy.set_complete_after(1)

    image_dir = tmp_path / "image_gen_i2i"
    image_dir.mkdir(parents=True, exist_ok=True)
    source = image_dir / "source.png"
    source.write_bytes(queue_server.sample_image.read_bytes())

    job = queue_server.request(
        "POST",
        "/api/jobs",
        {
            "workflow_name": "image-gen-flux-img2img",
            "input_dir": str(image_dir),
            "params": {
                "positive_prompt": "soft rim light portrait",
                "style_prompt": "high detail skin, film grain",
                "denoise": 0.45,
                "tries": 1,
                "randomize_seed": False,
            },
            "split_by_input": False,
        },
        expected=201,
    )
    assert int(job["prompt_count"]) == 1

    terminal = queue_server.wait_until(
        lambda: (
            (detail := queue_server.request("GET", f"/api/jobs/{job['job_id']}"))
            and detail["job"]["status"] in {"succeeded", "failed", "canceled"}
            and detail
        ),
        timeout=10,
        step=0.2,
    )
    assert terminal["job"]["status"] == "succeeded"
    assert len(terminal["prompts"]) == 1
    prompt = terminal["prompts"][0]
    assert prompt["input_file"] == str(source)
    assert prompt["output_paths"] != "[]"

    prompt_json = json.loads(prompt["prompt_json"])
    assert prompt_json["36"]["inputs"]["clip_l"] == "soft rim light portrait"
    assert prompt_json["36"]["inputs"]["t5xxl"] == "high detail skin, film grain"
