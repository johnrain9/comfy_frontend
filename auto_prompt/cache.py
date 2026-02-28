from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CaptionCache:
    _captions: dict[str, str] = field(default_factory=dict)

    def get(self, image_path: str) -> str | None:
        return self._captions.get(str(image_path))

    def set(self, image_path: str, caption: str) -> None:
        self._captions[str(image_path)] = str(caption)

    def to_dict(self) -> dict[str, str]:
        return dict(self._captions)
