from __future__ import annotations

from pathlib import Path


HTML = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")


def test_ui_contains_persistence_and_reset_controls():
    assert "video_queue_ui_state_v1" in HTML
    assert 'id="resetSavedBtn"' in HTML
    assert "localStorage" in HTML
    assert "function resetSavedOptions" in HTML


def test_ui_contains_mode_tabs():
    assert 'id="tabBatch"' in HTML
    assert 'id="tabImageGen"' in HTML
    assert 'id="tabUpscale"' in HTML
    assert 'id="tabUpscaleImages"' in HTML


def test_ui_contains_image_gen_source_controls():
    assert 'id="imageGenSourceMode"' in HTML
    assert 'id="imageGenDropZone"' in HTML
    assert 'id="clearImageGenDropBtn"' in HTML


def test_ui_contains_cancel_feedback_and_prompt_details():
    assert "cancel_summary" in HTML
    assert "Comfy prompt_id" in HTML
    assert "Prompt JSON" in HTML


def test_ui_contains_default_input_dir_notice_anchor():
    assert "defaultInputDirNotice" in HTML


def test_ui_contains_queue_visibility_controls():
    assert 'id="queueSummaryCards"' in HTML
    assert 'id="queueStatusBar"' in HTML
    assert 'id="queueSearch"' in HTML
    assert 'id="queueSort"' in HTML


def test_ui_contains_batch_dropzone_controls():
    assert 'id="batchDropZone"' in HTML
    assert 'id="batchThumbs"' in HTML
    assert 'id="clearBatchDropBtn"' in HTML


def test_ui_contains_workspace_tab_controls():
    assert 'id="workspaceTabs"' in HTML
    assert 'id="newWorkspaceBtn"' in HTML
    assert 'id="renameWorkspaceBtn"' in HTML
    assert 'id="closeWorkspaceBtn"' in HTML


def test_ui_contains_favicon_link():
    assert 'rel="icon"' in HTML
    assert "/static/favicon.svg" in HTML
