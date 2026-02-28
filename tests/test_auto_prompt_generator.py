from __future__ import annotations

from pathlib import Path

from auto_prompt.generator import AutoPromptGenerator, LMStudioUnavailable
from defs import load_all


ROOT = Path(__file__).resolve().parents[1]


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.ensure_calls: list[tuple[str, bool]] = []

    def check_available(self) -> None:
        return

    def ensure_model_loaded(self, model: str, auto_load: bool = True) -> None:
        self.ensure_calls.append((model, bool(auto_load)))

    def chat(self, *, model: str, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((model, user_prompt))
        if "Caption:" in user_prompt:
            if "split_prompt_workflow=true" in system_prompt:
                return '{"clip_1":"clip1 move", "clip_2":"clip2 move"}'
            return "single motion prompt"
        return "caption for image"


class _DownClient:
    def check_available(self) -> None:
        raise LMStudioUnavailable("down")

    def ensure_model_loaded(self, model: str, auto_load: bool = True) -> None:
        raise LMStudioUnavailable("down")

    def chat(self, *, model: str, system_prompt: str, user_prompt: str) -> str:
        raise AssertionError("should not chat when unavailable")


def _workflow(name: str):
    workflows = {wf.name: wf for wf in load_all(ROOT / "workflow_defs_v2")}
    return workflows[name]


def test_generator_defaults_and_context_extraction_for_split_workflow():
    wf = _workflow("wan-context-2stage-split-prompts")
    gen = AutoPromptGenerator(client=_FakeClient())
    ctx = gen.extract_workflow_context(wf)

    assert gen.stage1_model == "Qwen3-VL-8B-NSFW-Caption-V4.5"
    assert gen.stage2_model == "Dolphin-Mistral-24B-Venice-Edition"
    assert ctx.split_prompt_workflow is True
    assert ctx.stage_count == 2
    assert ctx.marker_0 == 0.0
    assert ctx.marker_1 == 1.5
    assert ctx.marker_2 == 3.0


def test_generate_batch_callback_contract_caption_and_motion(tmp_path: Path):
    wf = _workflow("wan-context-2stage")
    client = _FakeClient()
    gen = AutoPromptGenerator(client=client)
    ctx = gen.extract_workflow_context(wf)

    img = tmp_path / "a.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")

    seen: list[tuple[str, str, int, int]] = []

    out = gen.generate_batch([img], ctx, callback=lambda stage, path, i, total: seen.append((stage, path, i, total)))
    assert len(out["items"]) == 1
    assert out["items"][0]["caption"] == "caption for image"
    assert out["items"][0]["motion_prompt"] == "single motion prompt"
    assert client.ensure_calls == [
        ("Qwen3-VL-8B-NSFW-Caption-V4.5", True),
        ("Dolphin-Mistral-24B-Venice-Edition", True),
    ]
    assert seen == [
        ("caption", str(img.resolve()), 1, 1),
        ("motion", str(img.resolve()), 1, 1),
    ]


def test_generator_unavailable_raises():
    gen = AutoPromptGenerator(client=_DownClient())
    try:
        gen.check_available()
        raised = False
    except LMStudioUnavailable:
        raised = True
    assert raised is True


def test_generate_motion_from_supplied_captions_without_stage1(tmp_path: Path):
    wf = _workflow("wan-context-2stage")
    client = _FakeClient()
    gen = AutoPromptGenerator(client=client)
    ctx = gen.extract_workflow_context(wf)
    img = tmp_path / "c.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")

    out = gen.generate_batch(
        [img],
        ctx,
        stage="motion",
        captions={str(img.resolve()): "provided caption"},
    )
    assert out["items"][0]["caption"] == "provided caption"
    assert out["items"][0]["motion_prompt"] == "single motion prompt"
    assert client.ensure_calls == [("Dolphin-Mistral-24B-Venice-Edition", True)]


def test_ensure_required_models_loaded_by_stage():
    client = _FakeClient()
    gen = AutoPromptGenerator(client=client)
    gen.ensure_required_models_loaded(stage="caption")
    assert client.ensure_calls == [("Qwen3-VL-8B-NSFW-Caption-V4.5", True)]

    client.ensure_calls.clear()
    gen.ensure_required_models_loaded(stage="motion")
    assert client.ensure_calls == [("Dolphin-Mistral-24B-Venice-Edition", True)]
