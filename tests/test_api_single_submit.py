from __future__ import annotations

import json


def test_single_submit_success_and_fanout(queue_server):
    queue_server.request("POST", "/api/queue/pause")
    job = queue_server.request(
        "POST",
        "/api/jobs/single",
        {
            "workflow_name": "wan-context-lite-2stage",
            "input_image": str(queue_server.sample_image),
            "params": {"tries": 2, "positive_prompt": "(at 0 second: x)(at 3 second: y)(at 7 second: z)"},
            "resolution_preset": "640x1136",
            "flip_orientation": False,
        },
        expected=201,
    )
    assert job["prompt_count"] == 2

    detail = queue_server.request("GET", f"/api/jobs/{job['job_id']}")
    assert len(detail["prompts"]) == 2
    for prompt in detail["prompts"]:
        assert prompt["input_file"] == str(queue_server.sample_image)

    queue_server.request("POST", "/api/queue/resume")


def test_single_submit_missing_image_is_rejected(queue_server):
    err = queue_server.request(
        "POST",
        "/api/jobs/single",
        {
            "workflow_name": "wan-context-lite-2stage",
            "input_image": "",
            "params": {},
        },
        expected=400,
    )
    assert "required" in str(err.get("detail", "")).lower()


def test_single_submit_invalid_extension_is_rejected(queue_server, tmp_path):
    bad = tmp_path / "bad.txt"
    bad.write_text("x", encoding="utf-8")
    err = queue_server.request(
        "POST",
        "/api/jobs/single",
        {
            "workflow_name": "wan-context-lite-2stage",
            "input_image": str(bad),
            "params": {},
        },
        expected=400,
    )
    assert "unsupported input image extension" in str(err.get("detail", "")).lower()


def test_batch_and_single_shared_options_produce_equivalent_prompt_payload(queue_server, tmp_path):
    queue_server.request("POST", "/api/queue/pause")

    batch_dir = tmp_path / "batch"
    batch_dir.mkdir(parents=True, exist_ok=True)
    sample_copy = batch_dir / "sample.png"
    sample_copy.write_bytes(queue_server.sample_image.read_bytes())

    common_params = {
        "positive_prompt": "(at 0 second: one)(at 3 second: two)(at 7 second: three)",
        "tries": 1,
        "randomize_seed": False,
    }

    batch_job = queue_server.request(
        "POST",
        "/api/jobs",
        {
            "workflow_name": "wan-context-lite-2stage",
            "input_dir": str(batch_dir),
            "params": common_params,
            "resolution_preset": "640x1136",
            "flip_orientation": False,
        },
        expected=201,
    )
    single_job = queue_server.request(
        "POST",
        "/api/jobs/single",
        {
            "workflow_name": "wan-context-lite-2stage",
            "input_image": str(sample_copy),
            "params": common_params,
            "resolution_preset": "640x1136",
            "flip_orientation": False,
        },
        expected=201,
    )

    batch_detail = queue_server.request("GET", f"/api/jobs/{batch_job['job_id']}")
    single_detail = queue_server.request("GET", f"/api/jobs/{single_job['job_id']}")

    assert len(batch_detail["prompts"]) == 1
    assert len(single_detail["prompts"]) == 1
    assert batch_detail["prompts"][0]["prompt_json"] == single_detail["prompts"][0]["prompt_json"]

    queue_server.request("POST", "/api/queue/resume")


def test_api_submit_persists_distinct_stage_prompts_for_2stage_split_workflow(queue_server):
    queue_server.request("POST", "/api/queue/pause")
    try:
        job = queue_server.request(
            "POST",
            "/api/jobs/single",
            {
                "workflow_name": "wan-context-2stage-split-prompts",
                "input_image": str(queue_server.sample_image),
                "params": {
                    "positive_prompt_stage1": "standing still, subtle motion",
                    "positive_prompt_stage2": "continues turn, settles into pose",
                    "negative_prompt": "jitter, artifacts",
                },
            },
            expected=201,
        )
        detail = queue_server.request("GET", f"/api/jobs/{job['job_id']}")
        assert len(detail["prompts"]) == 1

        prompt_json = detail["prompts"][0]["prompt_json"]
        prompt = json.loads(prompt_json) if isinstance(prompt_json, str) else prompt_json
        assert prompt["93"]["inputs"]["text"] == "standing still, subtle motion"
        assert prompt["193"]["inputs"]["text"] == "continues turn, settles into pose"
        assert prompt["89"]["inputs"]["text"] == "jitter, artifacts"
    finally:
        queue_server.request("POST", "/api/queue/resume")


def test_api_submit_maps_all_three_stage_prompts_for_3stage_workflow(queue_server):
    queue_server.request("POST", "/api/queue/pause")
    try:
        job = queue_server.request(
            "POST",
            "/api/jobs/single",
            {
                "workflow_name": "wan-context-3stage-split-prompts",
                "input_image": str(queue_server.sample_image),
                "params": {
                    "positive_prompt_stage1": "start motion",
                    "positive_prompt_stage2": "continue motion",
                    "positive_prompt_stage3": "finish and hold",
                    "negative_prompt": "stutter",
                },
            },
            expected=201,
        )
        detail = queue_server.request("GET", f"/api/jobs/{job['job_id']}")
        assert len(detail["prompts"]) == 1

        prompt_json = detail["prompts"][0]["prompt_json"]
        prompt = json.loads(prompt_json) if isinstance(prompt_json, str) else prompt_json
        assert prompt["93"]["inputs"]["text"] == "start motion"
        assert prompt["193"]["inputs"]["text"] == "continue motion"
        assert prompt["293"]["inputs"]["text"] == "finish and hold"
    finally:
        queue_server.request("POST", "/api/queue/resume")


def test_upscale_images_mode_queues_one_prompt_per_image(queue_server, tmp_path):
    queue_server.request("POST", "/api/queue/pause")
    try:
        image_dir = tmp_path / "upscale_batch"
        image_dir.mkdir(parents=True, exist_ok=True)
        for idx in range(3):
            (image_dir / f"img_{idx}.png").write_bytes(b"\x89PNG\r\n\x1a\n")

        job = queue_server.request(
            "POST",
            "/api/jobs",
            {
                "workflow_name": "upscale-images-i2v",
                "input_dir": str(image_dir),
                "params": {
                    "upscale_model_name": "RealESRGAN_x2plus.pth",
                    "final_scale_factor": 0.75,
                    "output_prefix": "image/upscaled_i2v",
                },
                "split_by_input": False,
            },
            expected=201,
        )
        assert int(job["prompt_count"]) == 3

        detail = queue_server.request("GET", f"/api/jobs/{job['job_id']}")
        assert len(detail["prompts"]) == 3
    finally:
        queue_server.request("POST", "/api/queue/resume")
