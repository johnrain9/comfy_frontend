from __future__ import annotations

from db import QueueDB


def test_prompt_presets_can_be_filtered_by_mode(tmp_path):
    db = QueueDB(tmp_path / "queue.db")
    try:
        db.save_prompt_preset("walk", "a", "b", mode="video_gen")
        db.save_prompt_preset("interp", "c", "d", mode="video_upscale")

        only_video_gen = db.list_prompt_presets(limit=50, mode="video_gen")
        only_video_upscale = db.list_prompt_presets(limit=50, mode="video_upscale")

        assert [item["name"] for item in only_video_gen] == ["walk"]
        assert [item["name"] for item in only_video_upscale] == ["interp"]
        assert only_video_gen[0]["mode"] == "video_gen"
        assert only_video_upscale[0]["mode"] == "video_upscale"
    finally:
        db.close()
