from __future__ import annotations

import pytest

from app import _validate_prompt_mode


def test_prompt_mode_manual_is_valid_without_per_file_params():
    assert _validate_prompt_mode(prompt_mode="manual", per_file_params={}) == "manual"


def test_prompt_mode_per_image_manual_requires_per_file_params():
    with pytest.raises(ValueError):
        _validate_prompt_mode(prompt_mode="per-image manual", per_file_params={})


def test_prompt_mode_per_image_auto_requires_per_file_params():
    with pytest.raises(ValueError):
        _validate_prompt_mode(prompt_mode="per-image auto", per_file_params={})


def test_prompt_mode_accepts_case_and_spacing_normalization():
    assert _validate_prompt_mode(
        prompt_mode=" per-image manual ",
        per_file_params={"a.png": {"positive_prompt": "x"}},
    ) == "per-image manual"


def test_prompt_mode_rejects_unknown_values():
    with pytest.raises(ValueError):
        _validate_prompt_mode(prompt_mode="auto", per_file_params={})
