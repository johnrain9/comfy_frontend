from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _src(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


PAGE = _src("ui/src/routes/+page.svelte")
STATUS_BAR = _src("ui/src/lib/components/StatusBar.svelte")
SUBMIT_PANEL = _src("ui/src/lib/components/SubmitPanel/SubmitPanel.svelte")
DROP_ZONE = _src("ui/src/lib/components/SubmitPanel/DropZone.svelte")
QUEUE_PANEL = _src("ui/src/lib/components/Queue/QueuePanel.svelte")
BULK_ACTIONS = _src("ui/src/lib/components/Queue/BulkActions.svelte")
API_TS = _src("ui/src/lib/api.ts")


def test_v2_has_status_bar_and_quick_actions():
    assert 'id="health"' in STATUS_BAR
    assert 'id="pauseBtn"' in STATUS_BAR
    assert 'id="resumeBtn"' in STATUS_BAR
    assert 'id="reloadWfBtn"' in STATUS_BAR
    assert 'id="reloadLoraBtn"' in STATUS_BAR


def test_v2_has_submit_panel_controls():
    assert 'id="modeBatch"' in SUBMIT_PANEL
    assert 'id="modeImageGen"' in SUBMIT_PANEL
    assert 'id="modeUpscale"' in SUBMIT_PANEL
    assert 'id="modeUpscaleImg"' in SUBMIT_PANEL
    assert 'id="workflowSelect"' in SUBMIT_PANEL
    assert 'id="paramFields"' in SUBMIT_PANEL
    assert 'id="submitBtn"' in SUBMIT_PANEL


def test_v2_has_drop_upload_and_thumbnails():
    assert 'id="dropZone"' in SUBMIT_PANEL
    assert 'inputId="fileInput"' in SUBMIT_PANEL
    assert 'thumbsId="thumbs"' in SUBMIT_PANEL
    assert '/api/upload/input-image' in API_TS
    assert 'id = \'dropZone\'' in DROP_ZONE


def test_v2_has_queue_visibility_and_safe_actions():
    assert 'id="statusFilter"' in QUEUE_PANEL
    assert 'id="queueSearch"' in QUEUE_PANEL
    assert 'id="queueSort"' in QUEUE_PANEL
    assert 'id="selectVisible"' in QUEUE_PANEL
    assert 'id="cancelSelBtn"' in BULK_ACTIONS
    assert 'id="clearQueueBtn"' in BULK_ACTIONS
    assert '/api/jobs/' in API_TS


def test_v2_has_workspace_and_preset_controls():
    assert 'id="workspaceTabs"' in PAGE
    assert 'id="newWsBtn"' in PAGE
    assert 'id="renameWsBtn"' in PAGE
    assert 'id="closeWsBtn"' in PAGE
    assert 'id="promptPresetSelect"' in SUBMIT_PANEL
    assert 'id="settingsPresetSelect"' in SUBMIT_PANEL
