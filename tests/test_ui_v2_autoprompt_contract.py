from __future__ import annotations

from pathlib import Path


SRC = (Path(__file__).resolve().parents[1] / "ui" / "src" / "lib" / "components" / "SubmitPanel" / "SubmitPanel.svelte").read_text(
    encoding="utf-8"
)


def test_submit_panel_has_prompt_mode_and_auto_prompt_controls():
    assert 'id="promptMode"' in SRC
    assert 'id="apCaptionBtn"' in SRC
    assert 'id="apMotionBtn"' in SRC
    assert 'id="apBothBtn"' in SRC
    assert 'id="apApplyBtn"' in SRC
    assert 'id="apClearBtn"' in SRC
    assert 'id="autoPromptRows"' in SRC


def test_submit_payload_includes_prompt_mode_and_per_file_params():
    assert "prompt_mode:" in SRC
    assert "activeWs.prompt_mode" in SRC
    assert "per_file_params:" in SRC
    assert "activeWs.per_file_params" in SRC
