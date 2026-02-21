from __future__ import annotations


def test_job_detail_contains_prompt_id_fields_and_payload(queue_server):
    queue_server.request("POST", "/api/queue/pause")

    job = queue_server.request(
        "POST",
        "/api/jobs/single",
        {
            "workflow_name": "wan-context-lite-2stage",
            "input_image": str(queue_server.sample_image),
            "params": {"tries": 1},
        },
        expected=201,
    )

    detail = queue_server.request("GET", f"/api/jobs/{job['job_id']}")
    assert isinstance(detail.get("prompts"), list)
    assert len(detail["prompts"]) == 1

    prompt = detail["prompts"][0]
    assert isinstance(prompt.get("id"), int)
    assert "prompt_id" in prompt
    assert prompt.get("prompt_id") is None
    assert isinstance(prompt.get("prompt_json"), str)
    assert prompt.get("status") in {"pending", "running", "canceled", "failed", "succeeded"}

    queue_server.request("POST", "/api/queue/resume")
