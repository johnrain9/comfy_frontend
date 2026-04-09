from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

import pytest

os.environ.setdefault("VIDEO_QUEUE_ROOT", "/tmp/video_queue_test_import_root")
os.environ.setdefault("COMFY_ROOT", "/tmp/video_queue_test_import_comfy")

from app import QUEUE_STAGING_DIRNAME, _dedupe_stage_dest, _sanitize_stage_filename, _stage_input_files, state


def _upload_input_image(queue_server, *, filename: str, subdir: str, data: bytes | None = None) -> dict[str, str]:
    req = urllib.request.Request(
        f"{queue_server.base_url}/api/upload/input-image",
        data=data if data is not None else b"\x89PNG\r\n\x1a\n",
        headers={"x-filename": filename, "x-subdir": subdir},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


@pytest.mark.parametrize(
    ("raw_name", "expected"),
    [
        ("My Cool Photo!.PNG", "My_Cool_Photo.png"),
        ("../../odd name!!.jpeg", "odd_name.jpeg"),
        ("", "input"),
        (".....gif", "input.gif"),
    ],
)
def test_sanitize_stage_filename(raw_name: str, expected: str):
    assert _sanitize_stage_filename(raw_name) == expected


def test_dedupe_stage_dest_appends_incrementing_suffixes(tmp_path: Path):
    stage_dir = tmp_path / "stage"
    stage_dir.mkdir(parents=True, exist_ok=True)

    (stage_dir / "image.png").write_bytes(b"1")
    (stage_dir / "image__2.png").write_bytes(b"2")

    assert _dedupe_stage_dest(stage_dir, "image.png") == stage_dir / "image__3.png"


def test_stage_input_files_copies_sources_into_queue_staging_and_dedupes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    comfy_input_dir = tmp_path / "comfy" / "input"
    comfy_input_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(state, "comfy_input_dir", comfy_input_dir)

    src_a = tmp_path / "src_a" / "same name!.png"
    src_b = tmp_path / "src_b" / "same name!.png"
    src_a.parent.mkdir(parents=True, exist_ok=True)
    src_b.parent.mkdir(parents=True, exist_ok=True)
    src_a.write_bytes(b"AAA")
    src_b.write_bytes(b"BBB")

    staged_paths, source_by_staged = _stage_input_files([src_a, src_b])

    assert len(staged_paths) == 2
    assert staged_paths[0].parent == staged_paths[1].parent
    assert staged_paths[0].parent.parent == comfy_input_dir / QUEUE_STAGING_DIRNAME
    assert staged_paths[0].name == "same_name.png"
    assert staged_paths[1].name == "same_name__2.png"
    assert staged_paths[0].read_bytes() == b"AAA"
    assert staged_paths[1].read_bytes() == b"BBB"
    assert source_by_staged[str(staged_paths[0])] == str(src_a.resolve())
    assert source_by_staged[str(staged_paths[1])] == str(src_b.resolve())


def test_upload_unique_name_preserves_sanitized_original_filename(queue_server):
    response = _upload_input_image(queue_server, filename="My Cool Photo!.PNG", subdir="uploads/test-unique")

    uploaded_path = Path(response["path"])
    assert uploaded_path.name == "My_Cool_Photo.png"
    assert uploaded_path.exists()
    assert response["dir"].endswith("uploads/test-unique")
    assert response["original_filename"] == "My Cool Photo!.PNG"


def test_upload_same_name_in_same_dir_uses_deterministic_suffixes(queue_server):
    first = _upload_input_image(queue_server, filename="duplicate.png", subdir="uploads/test-collision")
    second = _upload_input_image(queue_server, filename="duplicate.png", subdir="uploads/test-collision")
    third = _upload_input_image(queue_server, filename="duplicate.png", subdir="uploads/test-collision")

    assert Path(first["path"]).name == "duplicate.png"
    assert Path(second["path"]).name == "duplicate__2.png"
    assert Path(third["path"]).name == "duplicate__3.png"


def test_upload_same_name_in_different_subdirs_does_not_force_suffix(queue_server):
    first = _upload_input_image(queue_server, filename="shared.png", subdir="uploads/test-a")
    second = _upload_input_image(queue_server, filename="shared.png", subdir="uploads/test-b")

    assert Path(first["path"]).name == "shared.png"
    assert Path(second["path"]).name == "shared.png"
    assert Path(first["dir"]) != Path(second["dir"])
