"""
Project management for LCD rendering.

Projects are stored as .lcd_project JSON files with settings, custom chars,
and multiple text inputs.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from src.backend.utils.settings_manager import LCDSettings, dict_to_settings


@dataclass
class LCDInput:
    name: str
    text: str


@dataclass
class LCDProject:
    settings: LCDSettings
    custom_chars: Dict[int, List[str]]
    inputs: List[LCDInput]
    active_input: int = 0


def project_to_dict(project: LCDProject) -> dict[str, Any]:
    return {
        "settings": {
            "rows": project.settings.rows,
            "cols": project.settings.cols,
            "style": asdict(project.settings.style),
        },
        "custom_chars": project.custom_chars,
        "inputs": [asdict(item) for item in project.inputs],
        "active_input": project.active_input,
    }


def dict_to_project(data: dict[str, Any]) -> LCDProject:
    settings = dict_to_settings(data.get("settings", {}))
    custom_chars: dict[int, List[str]] = {
        int(k): v for k, v in (data.get("custom_chars", {}) or {}).items()
    }
    inputs_data = data.get("inputs", []) or []
    inputs = [LCDInput(**item) for item in inputs_data]
    if not inputs:
        inputs = [LCDInput(name="Input 1", text="")]
    active_input = int(data.get("active_input", 0))
    active_input = max(0, min(active_input, len(inputs) - 1))
    return LCDProject(
        settings=settings,
        custom_chars=custom_chars,
        inputs=inputs,
        active_input=active_input,
    )


def save_project(path: str | Path, project: LCDProject) -> Path:
    file_path = Path(path)
    if file_path.suffix != ".lcd_project":
        file_path = file_path.with_suffix(".lcd_project")

    payload = project_to_dict(project)
    file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return file_path


def load_project(path: str | Path) -> LCDProject:
    file_path = Path(path)
    data = json.loads(file_path.read_text(encoding="utf-8"))
    return dict_to_project(data)
