from __future__ import annotations

from pathlib import Path


HTML = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")


def test_ui_contains_persistence_and_reset_controls():
    assert "video_queue_ui_state_v1" in HTML
    assert 'id="resetSavedBtn"' in HTML
    assert "localStorage" in HTML
    assert "function resetSavedOptions" in HTML


def test_ui_contains_batch_and_single_tabs():
    assert 'id="tabBatch"' in HTML
    assert 'id="tabSingle"' in HTML
    assert 'id="singleInputSection"' in HTML
    assert 'id="inputImage"' in HTML
    assert "/api/jobs/single" in HTML


def test_ui_contains_cancel_feedback_and_prompt_details():
    assert "cancel_summary" in HTML
    assert "Comfy prompt_id" in HTML
    assert "Prompt JSON" in HTML


def test_ui_uses_default_input_dir_endpoint():
    assert "/api/input-dirs/default" in HTML
    assert "defaultInputDirNotice" in HTML
