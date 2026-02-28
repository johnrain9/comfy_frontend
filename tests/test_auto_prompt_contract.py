from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_auto_prompt_modules_exist():
    assert (ROOT / "auto_prompt" / "__init__.py").exists()
    assert (ROOT / "auto_prompt" / "generator.py").exists()
    assert (ROOT / "auto_prompt" / "prompts.py").exists()


def test_app_registers_auto_prompt_endpoints_and_models():
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "class AutoPromptRequest(BaseModel)" in app_text
    assert "@app.post(\"/api/auto-prompt\")" in app_text
    assert "@app.get(\"/api/auto-prompt/capability\")" in app_text
    assert "AutoPromptGenerator" in app_text
    assert "LMStudioUnavailable" in app_text
