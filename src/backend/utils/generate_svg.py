"""
Module for generating SVG representations of HD44780-like LCD displays.

Code for generating SVG created with AI.

Author:
    Johannes Schwab

Last Modified:
    2026-02-15
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List

from src.backend.utils.bitmap_manager import BITMAP


@dataclass(frozen=True)
class LCDStyle:
    """
    Style configuration for LCD SVG generation.
    All colors should be valid CSS color strings.
    """

    background: str = "#ccffcc"
    frame: str = "#000000"
    pixel_on: str = "#446644"
    pixel_off: str = "#bbeebb"
    border_radius: int = 12
    padding: int = 16
    pixel_size: int = 3
    pixel_gap: int = 1
    char_gap: int = 4
    row_gap: int = 10
    frame_width: int = 8


@dataclass(frozen=True)
class CustomStyle(LCDStyle):
    """
    Custom style configuration for LCD SVG generation.
    All colors should be valid CSS color strings.
    """

    background: str = "#d8f245"
    frame: str = "#000000"
    pixel_on: str = "#141f14"
    pixel_off: str = "#cde543"


def _glyph_for(
    row: str,
    col_start: int,
    custom_chars: dict[int, List[str]] | None = None,
) -> tuple[List[str], str]:
    custom_chars = custom_chars or {}
    if row[col_start] != "\\":
        return (
            BITMAP.get(row[col_start], BITMAP[" "]),
            row,
        )
    else:
        # Handle backslash escape for custom chars
        escape_sequence, next_col_start = _get_text_till_next_non_numeric(
            row, col_start + 1
        )
        if escape_sequence == "":
            # Just a backslash, render as normal character
            return (
                BITMAP["\\"],
                row[:col_start]
                + row[next_col_start:]
                + " " * (next_col_start - col_start),
            )
        elif re.fullmatch(r"\d+", escape_sequence):
            char_code = int(escape_sequence)
            return (
                custom_chars.get(char_code, BITMAP[" "]),
                row[:col_start]
                + row[next_col_start:]
                + " " * (next_col_start - col_start),
            )

        return BITMAP[" "], row


def _get_text_till_next_non_numeric(
    string: str, start: int
) -> tuple[str, int]:
    """
    Get substring from start index till next non-numeric character.
    If no non-numeric character is found, return the rest of the string.

    Args:
        string:
            The string to search
        start:
            The index to start seachring at.

    Returns:
        str:
            The found string or empty string
        int:
            The index of the next character after the found string
    """
    end = start
    while end < len(string) and string[end].isnumeric():
        end += 1

    return string[start:end], end - 1


def generate_lcd_svg(
    rows: int,
    cols: int,
    lines: Iterable[str],
    style: LCDStyle = CustomStyle(),
    custom_chars: dict[int, List[str]] | None = None,
) -> str:
    """Generate SVG for an HD44780-like LCD (5x8 font).

    rows: number of display rows (e.g., 2, 4)
    cols: number of characters per row (e.g., 16, 20)
    lines: iterable of strings; will be padded/truncated to rows/cols
    """
    # Normalize text
    text_lines = [line.ljust(cols) for line in list(lines)]
    while len(text_lines) < rows:
        text_lines.append(" " * cols)

    # Compute geometry
    px = style.pixel_size
    gap = style.pixel_gap
    char_w = 5 * px + 4 * gap
    char_h = 8 * px + 7 * gap
    w = (
        style.padding * 2
        + cols * char_w
        + (cols - 1) * style.char_gap
        + style.frame_width * 2
    )
    h = (
        style.padding * 2
        + rows * char_h
        + (rows - 1) * style.row_gap
        + style.frame_width * 2
    )

    # SVG header
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" '
        f'viewBox="0 0 {w} {h}">',
        f'<rect x="0" y="0" width="{w}" height="{h}" rx="0" '
        f'fill="{style.frame}"/>',
        f'<rect x="{style.frame_width}" y="{style.frame_width}" '
        f'width="{w - 2 * style.frame_width}" ',
        f'height="{h - 2 * style.frame_width}" '
        f'rx="{max(style.border_radius - 4, 0)}" fill="{style.background}"/>',
    ]

    # Render pixels
    origin_x = style.frame_width + style.padding
    origin_y = style.frame_width + style.padding

    for r in range(rows):
        y0 = origin_y + r * (char_h + style.row_gap)
        for c in range(cols):
            x0 = origin_x + c * (char_w + style.char_gap)
            glyph, new_line = _glyph_for(
                text_lines[r], c, custom_chars=custom_chars
            )
            text_lines[r] = new_line
            for gy, row in enumerate(glyph):
                for gx, bit in enumerate(row):
                    fill = style.pixel_on if bit == "1" else style.pixel_off
                    px_x = x0 + gx * (px + gap)
                    px_y = y0 + gy * (px + gap)
                    parts.append(
                        f'<rect x="{px_x}" y="{px_y}" width="{px}" '
                        f'height="{px}" '
                        f'fill="{fill}"/>'
                    )

    parts.append("</svg>")
    return "\n".join(parts)


def save_svg(path: str, svg_content: str) -> bool:
    """
    Save SVG content to a file.

    Args:
        path:
            The file path to save the SVG content.
        svg_content:
            The SVG content to save.

    Returns:
        bool: True if the file was saved successfully, False otherwise.
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg_content)
        return True
    except OSError as e:
        print(f"Error saving SVG: {e}")
        return False


def _split_string(length: int, string: str) -> List[str]:
    return [
        string[i : i + length]  # noqa: E203
        for i in range(0, len(string), length)
    ]


if __name__ == "__main__":
    test_lines = _split_string(20, "".join(BITMAP.keys()))
    svg = generate_lcd_svg(
        rows=5,
        cols=20,
        lines=test_lines,
    )
    save_svg("lcd.svg", svg)
