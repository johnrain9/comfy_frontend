from __future__ import annotations


def test_cancel_immediate_and_idempotent_for_pending(queue_server):
    queue_server.fake_comfy.set_complete_after(50)
    queue_server.request("POST", "/api/queue/pause")

    job = queue_server.request(
        "POST",
        "/api/jobs/single",
        {
            "workflow_name": "wan-context-lite-2stage",
            "input_image": str(queue_server.sample_image),
            "params": {"tries": 2},
        },
        expected=201,
    )
    job_id = int(job["job_id"])

    c1 = queue_server.request("POST", f"/api/jobs/{job_id}/cancel")
    summary1 = c1.get("cancel_summary", {})
    assert summary1.get("mode") == "immediate"
    assert int(summary1.get("canceled_pending", -1)) == 2
    assert int(summary1.get("running_prompts", -1)) == 0
    assert c1["job"]["status"] == "canceled"

    c2 = queue_server.request("POST", f"/api/jobs/{job_id}/cancel")
    summary2 = c2.get("cancel_summary", {})
    assert summary2.get("mode") == "immediate"
    assert int(summary2.get("canceled_pending", -1)) == 0
    assert int(summary2.get("running_prompts", -1)) == 0
    assert c2["job"]["status"] == "canceled"

    queue_server.request("POST", "/api/queue/resume")


def test_cancel_after_current_when_running_prompt_exists(queue_server):
    queue_server.fake_comfy.set_complete_after(6)
    queue_server.request("POST", "/api/queue/resume")

    job = queue_server.request(
        "POST",
        "/api/jobs/single",
        {
            "workflow_name": "wan-context-lite-2stage",
            "input_image": str(queue_server.sample_image),
            "params": {"tries": 2},
        },
        expected=201,
    )
    job_id = int(job["job_id"])

    def _has_running_and_pending() -> bool:
        detail = queue_server.request("GET", f"/api/jobs/{job_id}")
        statuses = [p.get("status") for p in detail.get("prompts", [])]
        return ("running" in statuses) and ("pending" in statuses)

    queue_server.wait_until(_has_running_and_pending, timeout=10, step=0.1)

    canceled = queue_server.request("POST", f"/api/jobs/{job_id}/cancel")
    summary = canceled.get("cancel_summary", {})
    assert summary.get("mode") == "cancel_after_current"
    assert int(summary.get("running_prompts", 0)) >= 1
    assert int(summary.get("canceled_pending", 0)) >= 1

    def _terminal() -> bool:
        detail = queue_server.request("GET", f"/api/jobs/{job_id}")
        return detail["job"]["status"] in {"canceled", "failed", "succeeded"}

    queue_server.wait_until(_terminal, timeout=25, step=0.5)
