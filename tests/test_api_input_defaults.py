from __future__ import annotations


def test_default_input_dir_endpoint(queue_server):
    data = queue_server.request("GET", "/api/input-dirs/default")
    assert data["default_path"] == str(queue_server.comfy_root / "input")
    assert data["exists"] is True


def test_normalize_and_touch_with_default_path(queue_server):
    default_path = str(queue_server.comfy_root / "input")

    normalized = queue_server.request(
        "POST",
        "/api/input-dirs/normalize",
        {"path": default_path},
    )
    assert normalized["normalized_path"] == default_path

    touched = queue_server.request(
        "POST",
        "/api/input-dirs/recent",
        {"path": default_path},
    )
    assert touched["path"] == default_path

    recent = queue_server.request("GET", "/api/input-dirs/recent?limit=20")
    assert default_path in recent["paths"]
