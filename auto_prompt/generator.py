from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from defs import WorkflowDef

from .cache import CaptionCache
from .prompts import (
    STAGE1_MODEL_DEFAULT,
    STAGE1_SYSTEM_PROMPT,
    STAGE2_MODEL_DEFAULT,
    render_stage2_system_prompt,
)


class LMStudioUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkflowContext:
    workflow_name: str
    split_prompt_workflow: bool
    stage_count: int
    stage_prompt_keys: list[str]
    fps: int
    total_frames: int
    frames_per_stage: int
    duration_seconds: float
    marker_0: float
    marker_1: float
    marker_2: float


class LMStudioClient:
    def __init__(self, base_url: str, timeout_s: float = 20.0) -> None:
        self.base_url = str(base_url).rstrip("/")
        self.timeout_s = float(timeout_s)

    def check_available(self) -> None:
        try:
            self.list_models()
        except LMStudioUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            raise LMStudioUnavailable(
                "LM Studio unavailable. Start LM Studio, enable OpenAI-compatible API, and load the required model."
            ) from exc

    def list_models(self) -> list[str]:
        try:
            import requests

            resp = requests.get(f"{self.base_url}/v1/models", timeout=self.timeout_s)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", []) if isinstance(data, dict) else []
            out: list[str] = []
            for item in items:
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    out.append(str(item["id"]))
            return out
        except Exception as exc:  # noqa: BLE001
            raise LMStudioUnavailable(
                "LM Studio unavailable. Start LM Studio, enable OpenAI-compatible API, and load the required model."
            ) from exc

    def load_model(self, model: str) -> dict[str, Any]:
        import requests

        payload = {"model": str(model)}
        resp = requests.post(
            f"{self.base_url}/api/v1/models/load",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=max(self.timeout_s, 120.0),
        )
        resp.raise_for_status()
        return resp.json() if resp.text else {}

    def ensure_model_loaded(self, model: str, auto_load: bool = True) -> None:
        try:
            loaded = self.list_models()
            if model in loaded:
                return
        except Exception:
            # If list fails, fall through to explicit load path (auto-load) or surface unavailable.
            if not auto_load:
                raise

        if not auto_load:
            raise LMStudioUnavailable(
                f"LM Studio model '{model}' is not loaded. Load it in LM Studio or enable auto-load."
            )
        try:
            self.load_model(model)
        except Exception as exc:  # noqa: BLE001
            raise LMStudioUnavailable(
                f"Failed to auto-load LM Studio model '{model}'. "
                "Ensure the model is downloaded in LM Studio and API server is enabled."
            ) from exc

    def chat(self, *, model: str, system_prompt: str, user_prompt: str) -> str:
        import requests

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.4,
        }
        try:
            resp = requests.post(
                f"{self.base_url}/v1/chat/completions",
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=self.timeout_s,
            )
            resp.raise_for_status()
            data = resp.json()
            return str(data["choices"][0]["message"]["content"])
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"LM Studio chat failed: {exc}") from exc


class AutoPromptGenerator:
    """Two-stage auto prompt generator.

    Contract:
    - caption_image(image_path)
    - caption_to_motion(caption, workflow_context)
    - generate_batch(image_paths, callback=None)
    Callback shape: callback(stage, path, i, total)
      - stage in {"caption", "motion"}
    """

    def __init__(
        self,
        lmstudio_url: str = "http://127.0.0.1:1234",
        stage1_model: str = STAGE1_MODEL_DEFAULT,
        stage2_model: str = STAGE2_MODEL_DEFAULT,
        client: LMStudioClient | None = None,
        cache: CaptionCache | None = None,
        auto_load_models: bool = True,
    ) -> None:
        self.lmstudio_url = str(lmstudio_url)
        self.stage1_model = str(stage1_model)
        self.stage2_model = str(stage2_model)
        self.client = client or LMStudioClient(self.lmstudio_url)
        self.cache = cache or CaptionCache()
        self.auto_load_models = bool(auto_load_models)

    @staticmethod
    def extract_workflow_context(workflow: WorkflowDef) -> WorkflowContext:
        keys = sorted(
            [k for k in workflow.parameters.keys() if re.fullmatch(r"positive_prompt_stage\d+", k)],
            key=lambda x: int(re.findall(r"\d+", x)[0]),
        )
        split = len(keys) > 0
        stage_count = len(keys) if split else 1

        fps = 24
        total_frames = 81
        for node in workflow.template_prompt.values():
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            if isinstance(inputs.get("fps"), (int, float)) and int(inputs["fps"]) > 0:
                fps = int(inputs["fps"])
            if isinstance(inputs.get("length"), (int, float)) and int(inputs["length"]) > 0:
                total_frames = max(total_frames, int(inputs["length"]))

        frames_per_stage = max(1, int(total_frames / stage_count))
        duration = float(total_frames) / float(fps)

        # Keep default-friendly temporal anchors expected by current 81f/24fps flows.
        marker_0 = 0.0
        marker_1 = min(1.5, duration)
        marker_2 = min(3.0, duration)

        return WorkflowContext(
            workflow_name=workflow.name,
            split_prompt_workflow=split,
            stage_count=stage_count,
            stage_prompt_keys=keys,
            fps=fps,
            total_frames=total_frames,
            frames_per_stage=frames_per_stage,
            duration_seconds=duration,
            marker_0=marker_0,
            marker_1=marker_1,
            marker_2=marker_2,
        )

    def check_available(self) -> None:
        self.client.check_available()

    def ensure_required_models_loaded(self, stage: str = "both") -> None:
        normalized = str(stage or "both").strip().lower()
        if normalized not in {"caption", "motion", "both"}:
            raise ValueError("stage must be one of: caption, motion, both")
        if normalized in {"caption", "both"}:
            self.client.ensure_model_loaded(self.stage1_model, auto_load=self.auto_load_models)
        if normalized in {"motion", "both"}:
            self.client.ensure_model_loaded(self.stage2_model, auto_load=self.auto_load_models)

    def caption_image(self, image_path: str | Path, *, ensure_model: bool = True) -> str:
        path = str(Path(image_path).expanduser().resolve())
        cached = self.cache.get(path)
        if cached:
            return cached
        if ensure_model:
            self.client.ensure_model_loaded(self.stage1_model, auto_load=self.auto_load_models)
        user = (
            "Describe this source image for video generation continuity. "
            "Image path: "
            f"{path}"
        )
        caption = self.client.chat(model=self.stage1_model, system_prompt=STAGE1_SYSTEM_PROMPT, user_prompt=user).strip()
        self.cache.set(path, caption)
        return caption

    def caption_to_motion(
        self,
        caption: str,
        workflow_context: WorkflowContext,
        system_prompt_override: str | None = None,
        *,
        ensure_model: bool = True,
    ) -> str | dict[str, str]:
        sys_prompt = system_prompt_override or render_stage2_system_prompt(
            fps=workflow_context.fps,
            total_frames=workflow_context.total_frames,
            duration_seconds=workflow_context.duration_seconds,
            marker_0=workflow_context.marker_0,
            marker_1=workflow_context.marker_1,
            marker_2=workflow_context.marker_2,
            split_prompt_workflow=workflow_context.split_prompt_workflow,
            stage_count=workflow_context.stage_count,
        )
        if ensure_model:
            self.client.ensure_model_loaded(self.stage2_model, auto_load=self.auto_load_models)
        user = f"Caption: {caption}\nGenerate motion prompt now."
        raw = self.client.chat(model=self.stage2_model, system_prompt=sys_prompt, user_prompt=user).strip()
        if workflow_context.split_prompt_workflow:
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    out: dict[str, str] = {}
                    for i in range(1, workflow_context.stage_count + 1):
                        key = f"clip_{i}"
                        out[key] = str(data.get(key, "")).strip()
                    return out
            except Exception:  # noqa: BLE001
                pass
            # fallback: duplicate text across clips
            return {f"clip_{i}": raw for i in range(1, workflow_context.stage_count + 1)}
        return raw

    def generate_batch(
        self,
        image_paths: list[str | Path],
        workflow_context: WorkflowContext,
        *,
        callback: Callable[[str, str, int, int], None] | None = None,
        stage: str = "both",
        captions: dict[str, str] | None = None,
        system_prompt_override: str | None = None,
    ) -> dict[str, Any]:
        total = len(image_paths)
        if total == 0:
            return {
                "items": [],
                "stage1_model": self.stage1_model,
                "stage2_model": self.stage2_model,
                "elapsed_seconds": 0.0,
            }

        started = time.time()
        items: list[dict[str, Any]] = []
        captions_in = {str(k): str(v) for k, v in (captions or {}).items()}
        self.ensure_required_models_loaded(stage=stage)

        for idx, img in enumerate(image_paths, 1):
            path = str(Path(img).expanduser().resolve())
            item: dict[str, Any] = {"path": path}

            cap = captions_in.get(path)
            if stage in {"caption", "both"}:
                cap = self.caption_image(path, ensure_model=False)
                if callback:
                    callback("caption", path, idx, total)
            if cap is not None:
                item["caption"] = cap

            if stage in {"motion", "both"}:
                if not cap:
                    raise ValueError(f"caption required for motion stage: {path}")
                motion = self.caption_to_motion(
                    cap,
                    workflow_context,
                    system_prompt_override=system_prompt_override,
                    ensure_model=False,
                )
                if callback:
                    callback("motion", path, idx, total)
                if isinstance(motion, dict):
                    item["motion_prompts"] = motion
                else:
                    item["motion_prompt"] = motion

            items.append(item)

        return {
            "items": items,
            "stage1_model": self.stage1_model,
            "stage2_model": self.stage2_model,
            "elapsed_seconds": round(time.time() - started, 3),
            "workflow_context": {
                "workflow_name": workflow_context.workflow_name,
                "split_prompt_workflow": workflow_context.split_prompt_workflow,
                "stage_count": workflow_context.stage_count,
                "fps": workflow_context.fps,
                "total_frames": workflow_context.total_frames,
                "duration_seconds": round(workflow_context.duration_seconds, 3),
                "markers": [workflow_context.marker_0, workflow_context.marker_1, workflow_context.marker_2],
            },
        }
