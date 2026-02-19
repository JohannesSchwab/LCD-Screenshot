"""
Bitmap management utilities for LCD rendering.

Provides serialization to .lcd_bitmap JSON files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

RESOURCE_DIR = Path(__file__).resolve().parents[2] / "resources"
DEFAULT_FONT_PATH = RESOURCE_DIR / "bitmap.lcd_bitmap"


def load_font_map(
    path: str | Path = DEFAULT_FONT_PATH,
) -> Dict[str, List[str]]:
    file_path = Path(path)
    data = json.loads(file_path.read_text(encoding="utf-8"))
    font_data = data.get("font_5x8") or data.get("font") or data
    return {str(k): list(v) for k, v in font_data.items()}


BITMAP = load_font_map()


def get_bitmap_keys() -> List[str]:
    return list(BITMAP.keys())


if __name__ == "__main__":
    print(get_bitmap_keys())
