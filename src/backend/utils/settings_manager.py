"""
Settings management utilities for LCD rendering.

Provides serialization to .lcd_settings JSON files.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.backend.utils.generate_svg import CustomStyle, LCDStyle


@dataclass(frozen=True)
class LCDSettings:
    rows: int = 4
    cols: int = 20
    style: LCDStyle = field(default_factory=CustomStyle)


def settings_to_dict(settings: LCDSettings) -> dict[str, Any]:
    return {
        "schema": "lcd_settings_v1",
        "rows": settings.rows,
        "cols": settings.cols,
        "style": asdict(settings.style),
    }


def dict_to_settings(data: dict[str, Any]) -> LCDSettings:
    style_data = data.get("style", {})
    style = LCDStyle(**style_data) if style_data else CustomStyle()
    return LCDSettings(
        rows=int(data.get("rows", 4)),
        cols=int(data.get("cols", 20)),
        style=style,
    )


def save_settings(path: str | Path, settings: LCDSettings) -> Path:
    """
    Save settings to a .lcd_settings JSON file.
    """
    file_path = Path(path)
    if file_path.suffix != ".lcd_settings":
        file_path = file_path.with_suffix(".lcd_settings")

    payload = settings_to_dict(settings)
    file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return file_path


def load_settings(path: str | Path) -> LCDSettings:
    """
    Load settings from a .lcd_settings JSON file.
    """
    file_path = Path(path)
    data = json.loads(file_path.read_text(encoding="utf-8"))
    return dict_to_settings(data)
