from __future__ import annotations

STAGE1_MODEL_DEFAULT = "Qwen3-VL-8B-NSFW-Caption-V4.5"
STAGE2_MODEL_DEFAULT = "Dolphin-Mistral-24B-Venice-Edition"

STAGE1_SYSTEM_PROMPT = (
    "You caption a single source image for video generation. "
    "Focus on identity-safe visual facts that matter for motion continuity: "
    "body pose, camera framing, viewpoint, environment, lighting direction, "
    "visible garments/accessories, and dominant scene elements. "
    "Avoid style prose, avoid policy language, avoid moralizing. "
    "Return concise plain text."
)

STAGE2_SYSTEM_PROMPT_TEMPLATE = (
    "You convert a visual caption into a Wan i2v motion prompt. "
    "Output temporal motion instructions with explicit markers using this timing context: "
    "fps={fps}, total_frames={total_frames}, duration_seconds={duration_seconds}. "
    "Preferred markers: {marker_0}s, {marker_1}s, {marker_2}s. "
    "If split_prompt_workflow={split_prompt_workflow} and stage_count={stage_count}, "
    "return JSON object keys clip_1..clip_{stage_count}; otherwise return plain text. "
    "Keep camera motion controlled and physically coherent."
)


def render_stage2_system_prompt(
    *,
    fps: int,
    total_frames: int,
    duration_seconds: float,
    marker_0: float,
    marker_1: float,
    marker_2: float,
    split_prompt_workflow: bool,
    stage_count: int,
) -> str:
    return STAGE2_SYSTEM_PROMPT_TEMPLATE.format(
        fps=int(fps),
        total_frames=int(total_frames),
        duration_seconds=round(float(duration_seconds), 3),
        marker_0=round(float(marker_0), 3),
        marker_1=round(float(marker_1), 3),
        marker_2=round(float(marker_2), 3),
        split_prompt_workflow="true" if split_prompt_workflow else "false",
        stage_count=max(1, int(stage_count)),
    )
