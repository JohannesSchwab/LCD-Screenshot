"""
GUI for LCD SVG rendering with debounce updates.
"""

from __future__ import annotations

import io
import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog
from typing import Any, Optional

import cairosvg
import ttkbootstrap as ttk
from PIL import Image, ImageOps, ImageTk
from ttkbootstrap.constants import BOTH, LEFT, RIGHT, X
from ttkbootstrap.widgets.scrolled import ScrolledText

from src.backend.utils.generate_svg import LCDStyle, generate_lcd_svg
from src.backend.utils.project_manager import (
    LCDInput,
    LCDProject,
    load_project,
    save_project,
)
from src.backend.utils.settings_manager import LCDSettings, load_settings

RESOURCE_DIR = Path(__file__).resolve().parents[2] / "resources"
PRESETS_PATH = RESOURCE_DIR / "presets.json"


class LCDApp(ttk.Window):
    def __init__(self) -> None:
        super().__init__(themename="darkly")
        self.title("LCD Screenshot Generator")
        self.geometry("900x600")

        self.project = self._load_initial_project()
        self.settings = self.project.settings
        self._render_job: Optional[str] = None
        self._image_ref: Optional[ImageTk.PhotoImage] = None
        self._last_svg: Optional[str] = None
        self._settings_window: Optional[tk.Toplevel] = None
        self._custom_chars_window: Optional[tk.Toplevel] = None
        self._suppress_text_events = False
        self._presets: list[dict[str, Any]] = []
        self._preset_choice = tk.StringVar(value="custom")
        self._settings_controls: list[tk.Widget] = []
        self._settings_scroll_widgets: list[tk.Widget] = []
        self._applying_preset = False
        self._custom_char_number = tk.IntVar(value=0)
        self._custom_char_selector: Optional[ttk.Combobox] = None
        self._custom_char_buttons: list[list[tk.Button]] = []
        self._custom_char_bg_frame: Optional[ttk.Frame] = None
        self._custom_char_grid_frame: Optional[ttk.Frame] = None
        self._custom_char_bg_style = "CustomCharBg.TFrame"
        self._custom_char_grid_style = "CustomCharGrid.TFrame"
        self._custom_char_bits: list[list[int]] = [
            [0 for _ in range(5)] for _ in range(8)
        ]
        self._custom_char_updating = False
        self._init_settings_vars()

        self._build_ui()
        self._schedule_render()

    def _load_initial_settings(self) -> LCDSettings:
        presets = self._load_presets()
        if presets:
            preset = presets[0]
            settings_data = preset.get("settings", {})
            style_data = settings_data.get("style", {})
            try:
                return LCDSettings(
                    rows=int(settings_data.get("rows", 4)),
                    cols=int(settings_data.get("cols", 20)),
                    style=LCDStyle(**style_data),
                )
            except (ValueError, tk.TclError):
                return LCDSettings()
        return LCDSettings()

    def _load_initial_project(self) -> LCDProject:
        settings = self._load_initial_settings()
        return LCDProject(
            settings=settings,
            custom_chars={},
            inputs=[LCDInput(name="Input 1", text="")],
            active_input=0,
        )

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=X, padx=8, pady=6)

        ttk.Button(
            toolbar, text="Load Project", command=self._on_load_project
        ).pack(side=LEFT, padx=4)
        ttk.Button(
            toolbar, text="Save Project", command=self._on_save_project
        ).pack(side=LEFT, padx=4)
        ttk.Button(
            toolbar, text="Edit Settings", command=self._open_settings_modal
        ).pack(side=LEFT, padx=4)
        ttk.Button(
            toolbar, text="Custom Chars", command=self._open_custom_chars_modal
        ).pack(side=LEFT, padx=4)
        ttk.Button(toolbar, text="Save SVG", command=self._on_save_svg).pack(
            side=LEFT, padx=4
        )

        main = ttk.Frame(self)
        main.pack(fill=BOTH, expand=True, padx=8, pady=8)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=0)
        main.rowconfigure(1, weight=1)
        main.rowconfigure(2, weight=3)

        input_bar = ttk.Frame(main)
        input_bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        input_bar.columnconfigure(1, weight=1)

        ttk.Label(input_bar, text="Input").grid(
            row=0, column=0, sticky="w", padx=(0, 6)
        )
        self.input_selector = ttk.Combobox(
            input_bar, state="readonly", values=[]
        )
        self.input_selector.grid(row=0, column=1, sticky="ew")
        self.input_selector.bind("<<ComboboxSelected>>", self._on_input_select)
        ttk.Button(input_bar, text="Add", command=self._on_add_input).grid(
            row=0, column=2, padx=(6, 0)
        )
        ttk.Button(
            input_bar, text="Rename", command=self._on_rename_input
        ).grid(row=0, column=3, padx=(6, 0))
        ttk.Button(
            input_bar, text="Remove", command=self._on_remove_input
        ).grid(row=0, column=4, padx=(6, 0))

        self.text_input = ScrolledText(main, height=6)
        self.text_input.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        self._text_widget = (
            getattr(self.text_input, "text", None)
            or getattr(self.text_input, "_text", None)
            or self.text_input
        )
        self._text_widget.bind("<KeyRelease>", self._on_text_change)
        self._text_widget.bind("<<Modified>>", self._on_text_modified)
        self._text_widget.edit_modified(False)

        preview_frame = ttk.Frame(main)
        preview_frame.grid(row=2, column=0, sticky="nsew")
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.bind("<Configure>", self._on_preview_resize)

        self.image_label = ttk.Label(preview_frame, text="Rendering...")
        self.image_label.grid(row=0, column=0, sticky="nsew")

        self._refresh_input_selector()
        self._load_active_input_text()

    def _open_settings_modal(self) -> None:
        if self._settings_window and self._settings_window.winfo_exists():
            self._settings_window.lift()
            self._settings_window.focus_set()
            return

        window = ttk.Toplevel(self)
        window.title("Settings")
        window.transient(self)
        window.grab_set()
        window.attributes("-topmost", True)
        window.geometry("420x520")
        window.resizable(True, True)

        container = ttk.Frame(window, padding=10)
        container.pack(fill=BOTH, expand=True)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        canvas = tk.Canvas(container, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(
            container, orient="vertical", command=canvas.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        scroll_frame = ttk.Frame(canvas)
        scroll_window = canvas.create_window(
            (0, 0), window=scroll_frame, anchor="nw"
        )

        def on_configure(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_configure(event) -> None:
            canvas.itemconfigure(scroll_window, width=event.width)

        scroll_frame.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", on_canvas_configure)

        def _on_mousewheel(event: tk.Event) -> None:
            if event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif getattr(event, "num", None) in (4, 5):
                direction = -1 if event.num == 4 else 1
                canvas.yview_scroll(direction, "units")

        def _bind_scroll(widget: tk.Widget) -> None:
            widget.bind("<MouseWheel>", _on_mousewheel)
            widget.bind("<Button-4>", _on_mousewheel)
            widget.bind("<Button-5>", _on_mousewheel)
            self._settings_scroll_widgets.append(widget)

        def _unbind_mousewheel() -> None:
            for widget in self._settings_scroll_widgets:
                try:
                    widget.unbind("<MouseWheel>")
                    widget.unbind("<Button-4>")
                    widget.unbind("<Button-5>")
                except tk.TclError:
                    continue
            self._settings_scroll_widgets = []

        _bind_scroll(canvas)
        _bind_scroll(scroll_frame)

        window.protocol(
            "WM_DELETE_WINDOW",
            lambda: (_unbind_mousewheel(), window.destroy()),
        )

        self._presets = self._load_presets()
        preset_frame = ttk.Labelframe(scroll_frame, text="Preset")
        preset_frame.pack(fill=X, expand=False, pady=(0, 8))
        self._build_preset_radios(preset_frame)
        _bind_scroll(preset_frame)

        settings_frame = ttk.Labelframe(scroll_frame, text="Display Settings")
        settings_frame.pack(fill=BOTH, expand=True)
        self._build_settings_widgets(settings_frame)
        _bind_scroll(settings_frame)

        button_row = ttk.Frame(container)
        button_row.grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0)
        )
        ttk.Button(
            button_row,
            text="Close",
            command=lambda: (_unbind_mousewheel(), window.destroy()),
        ).pack(side=RIGHT)

        self._sync_preset_selection()
        self._settings_window = window

    def _open_custom_chars_modal(self) -> None:
        if (
            self._custom_chars_window
            and self._custom_chars_window.winfo_exists()
        ):
            self._custom_chars_window.lift()
            self._custom_chars_window.focus_set()
            return

        window = ttk.Toplevel(self)
        window.title("Custom Characters")
        window.transient(self)
        window.grab_set()
        window.attributes("-topmost", True)
        window.geometry("420x420")
        window.resizable(True, True)

        def on_close() -> None:
            self._custom_char_buttons = []
            self._custom_char_selector = None
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", on_close)

        container = ttk.Frame(window, padding=10)
        container.pack(fill=BOTH, expand=True)

        custom_frame = ttk.Labelframe(container, text="Custom Characters")
        custom_frame.pack(fill=BOTH, expand=True)
        self._build_custom_char_widgets(custom_frame)

        button_row = ttk.Frame(container)
        button_row.pack(fill=X, pady=(10, 0))
        ttk.Button(button_row, text="Close", command=window.destroy).pack(
            side=RIGHT
        )

        self._custom_chars_window = window

    def _init_settings_vars(self) -> None:
        self.var_rows = tk.IntVar(value=self.settings.rows)
        self.var_cols = tk.IntVar(value=self.settings.cols)
        self.var_pixel_size = tk.IntVar(value=self.settings.style.pixel_size)
        self.var_pixel_gap = tk.IntVar(value=self.settings.style.pixel_gap)
        self.var_char_gap = tk.IntVar(value=self.settings.style.char_gap)
        self.var_row_gap = tk.IntVar(value=self.settings.style.row_gap)
        self.var_padding = tk.IntVar(value=self.settings.style.padding)
        self.var_frame_width = tk.IntVar(value=self.settings.style.frame_width)
        self.var_border_radius = tk.IntVar(
            value=self.settings.style.border_radius
        )
        self.var_bg = tk.StringVar(value=self.settings.style.background)
        self.var_frame = tk.StringVar(value=self.settings.style.frame)
        self.var_pixel_on = tk.StringVar(value=self.settings.style.pixel_on)
        self.var_pixel_off = tk.StringVar(value=self.settings.style.pixel_off)

        for var in (
            self.var_rows,
            self.var_cols,
            self.var_pixel_size,
            self.var_pixel_gap,
            self.var_char_gap,
            self.var_row_gap,
            self.var_padding,
            self.var_frame_width,
            self.var_border_radius,
            self.var_bg,
            self.var_frame,
            self.var_pixel_on,
            self.var_pixel_off,
        ):
            var.trace_add("write", self._on_settings_change)

    def _build_settings_widgets(self, parent: ttk.Frame) -> None:
        self._settings_controls = []
        row = 0

        def add_spin(label: str, var: tk.IntVar, from_: int, to: int) -> None:
            nonlocal row
            label_widget = ttk.Label(parent, text=label)
            label_widget.grid(row=row, column=0, sticky="w", padx=6, pady=3)
            self._settings_scroll_widgets.append(label_widget)
            spin = ttk.Spinbox(parent, from_=from_, to=to, textvariable=var)
            spin.grid(row=row, column=1, sticky="ew", padx=6, pady=3)
            self._settings_controls.append(spin)
            row += 1

        def add_entry(label: str, var: tk.StringVar) -> None:
            nonlocal row
            label_widget = ttk.Label(parent, text=label)
            label_widget.grid(row=row, column=0, sticky="w", padx=6, pady=3)
            self._settings_scroll_widgets.append(label_widget)
            entry = ttk.Entry(parent, textvariable=var)
            entry.grid(row=row, column=1, sticky="ew", padx=6, pady=3)
            self._settings_controls.append(entry)
            row += 1

        add_spin("Rows", self.var_rows, 1, 8)
        add_spin("Cols", self.var_cols, 8, 40)
        add_spin("Pixel Size", self.var_pixel_size, 1, 10)
        add_spin("Pixel Gap", self.var_pixel_gap, 0, 6)
        add_spin("Char Gap", self.var_char_gap, 0, 12)
        add_spin("Row Gap", self.var_row_gap, 0, 20)
        add_spin("Padding", self.var_padding, 0, 30)
        add_spin("Frame Width", self.var_frame_width, 0, 20)
        add_spin("Border Radius", self.var_border_radius, 0, 30)
        add_entry("Background", self.var_bg)
        add_entry("Frame", self.var_frame)
        add_entry("Pixel On", self.var_pixel_on)
        add_entry("Pixel Off", self.var_pixel_off)

        parent.columnconfigure(1, weight=1)

    def _build_custom_char_widgets(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.pack(fill=X, pady=(4, 8))

        ttk.Label(header, text="Char").pack(side=LEFT, padx=(0, 6))
        self._custom_char_selector = ttk.Combobox(
            header, state="readonly", values=[], width=8
        )
        self._custom_char_selector.pack(side=LEFT)
        self._custom_char_selector.bind(
            "<<ComboboxSelected>>", self._on_custom_char_select
        )
        ttk.Button(header, text="Add", command=self._on_add_custom_char).pack(
            side=LEFT, padx=(8, 0)
        )
        ttk.Button(
            header, text="Rename", command=self._on_rename_custom_char
        ).pack(side=LEFT, padx=(6, 0))
        ttk.Button(
            header, text="Remove", command=self._on_remove_custom_char
        ).pack(side=LEFT, padx=(6, 0))
        ttk.Button(header, text="Clear", command=self._clear_custom_char).pack(
            side=LEFT, padx=(6, 0)
        )

        self._configure_custom_char_styles()
        self._custom_char_bg_frame = ttk.Frame(
            parent,
            style=self._custom_char_bg_style,
        )
        self._custom_char_bg_frame.pack(padx=6, pady=6)

        self._custom_char_grid_frame = ttk.Frame(
            self._custom_char_bg_frame,
            style=self._custom_char_grid_style,
        )
        self._custom_char_grid_frame.pack(padx=8, pady=8)

        self._custom_char_buttons = []
        for r in range(8):
            row_buttons: list[tk.Button] = []
            for c in range(5):
                btn = tk.Button(
                    self._custom_char_grid_frame,
                    width=2,
                    height=1,
                    command=lambda rr=r, cc=c: self._toggle_custom_char(
                        rr, cc
                    ),
                    borderwidth=0,
                    highlightthickness=0,
                    padx=0,
                    pady=0,
                )
                btn.grid(row=r, column=c, padx=2, pady=2)
                row_buttons.append(btn)
            self._custom_char_buttons.append(row_buttons)

        self._refresh_custom_char_selector()

    def _on_text_change(self, _event: Any = None) -> None:
        self._update_active_input_text()
        self._schedule_render()

    def _on_text_modified(self, _event: Any = None) -> None:
        if self._text_widget.edit_modified():
            self._text_widget.edit_modified(False)
            self._update_active_input_text()
            self._schedule_render()

    def _on_settings_change(self, *_args: Any) -> None:
        if self._applying_preset:
            return
        self._apply_settings_from_ui()
        self._preset_choice.set("custom")
        self._set_settings_controls_state(True)
        self._schedule_render()

    def _apply_settings_from_ui(self) -> None:
        try:
            style = LCDStyle(
                background=self.var_bg.get(),
                frame=self.var_frame.get(),
                pixel_on=self.var_pixel_on.get(),
                pixel_off=self.var_pixel_off.get(),
                border_radius=int(self.var_border_radius.get()),
                padding=int(self.var_padding.get()),
                pixel_size=int(self.var_pixel_size.get()),
                pixel_gap=int(self.var_pixel_gap.get()),
                char_gap=int(self.var_char_gap.get()),
                row_gap=int(self.var_row_gap.get()),
                frame_width=int(self.var_frame_width.get()),
            )
            self.settings = LCDSettings(
                rows=int(self.var_rows.get()),
                cols=int(self.var_cols.get()),
                style=style,
            )
            self.project.settings = self.settings
            self._refresh_custom_char_grid_colors()
        except (ValueError, tk.TclError):
            return

    def _build_preset_radios(self, parent: ttk.Frame) -> None:
        for index, preset in enumerate(self._presets):
            name = preset.get("name", f"Preset {index + 1}")
            ttk.Radiobutton(
                parent,
                text=name,
                value=f"preset:{index}",
                variable=self._preset_choice,
                command=self._on_preset_choice,
            ).pack(anchor="w", padx=6, pady=2)

        ttk.Radiobutton(
            parent,
            text="Custom",
            value="custom",
            variable=self._preset_choice,
            command=self._on_preset_choice,
        ).pack(anchor="w", padx=6, pady=2)

    def _on_preset_choice(self) -> None:
        value = self._preset_choice.get()
        if value == "custom":
            self._set_settings_controls_state(True)
            return
        if value.startswith("preset:"):
            index = int(value.split(":", 1)[1])
            if 0 <= index < len(self._presets):
                self._apply_preset(self._presets[index])

    def _apply_preset(self, preset: dict) -> None:
        settings_data = preset.get("settings", {})
        style_data = settings_data.get("style", {})
        self._applying_preset = True
        self.settings = LCDSettings(
            rows=int(settings_data.get("rows", 4)),
            cols=int(settings_data.get("cols", 20)),
            style=LCDStyle(**style_data),
        )
        self.project.settings = self.settings
        self._load_settings_into_ui()
        self._set_settings_controls_state(False)
        self._applying_preset = False
        self._refresh_custom_char_grid_colors()
        self._schedule_render()

    def _sync_preset_selection(self) -> None:
        for index, preset in enumerate(self._presets):
            settings_data = preset.get("settings", {})
            style_data = settings_data.get("style", {})
            if (
                self.settings.rows == int(settings_data.get("rows", 4))
                and self.settings.cols == int(settings_data.get("cols", 20))
                and self.settings.style == LCDStyle(**style_data)
            ):
                self._preset_choice.set(f"preset:{index}")
                self._set_settings_controls_state(False)
                return
        self._preset_choice.set("custom")
        self._set_settings_controls_state(True)

    def _set_settings_controls_state(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for widget in self._settings_controls:
            try:
                widget.configure(state=state)
            except tk.TclError:
                continue

    def _on_custom_char_select(self, *_args) -> None:
        if self._custom_char_updating:
            return
        if not self._custom_char_selector:
            return
        value = self._custom_char_selector.get()
        if value == "":
            return
        try:
            number = int(value)
        except ValueError:
            return
        self._custom_char_number.set(number)
        self._load_custom_char_bits(number)

    def _refresh_custom_char_selector(self) -> None:
        if not self._custom_char_selector:
            return
        numbers = sorted(self.project.custom_chars.keys())
        if not numbers:
            numbers = [0]
        values = [str(n) for n in numbers]
        self._custom_char_selector["values"] = values
        current = (
            str(self._custom_char_number.get())
            if str(self._custom_char_number.get()) in values
            else values[0]
        )
        self._custom_char_selector.set(current)
        self._custom_char_number.set(int(current))
        self._load_custom_char_bits(int(current))

    def _on_add_custom_char(self) -> None:
        new_value = simpledialog.askstring(
            "Add Custom Char",
            "Char number (0-255):",
            parent=self._get_dialog_parent(),
        )
        if new_value is None:
            return
        try:
            number = int(new_value)
        except ValueError:
            messagebox.showerror(
                "Custom Char",
                "Enter a valid number.",
                parent=self._get_dialog_parent(),
            )
            return
        if number < 0 or number > 255:
            messagebox.showerror(
                "Custom Char",
                "Number must be 0-255.",
                parent=self._get_dialog_parent(),
            )
            return
        if number in self.project.custom_chars:
            messagebox.showerror(
                "Custom Char",
                "That number already exists.",
                parent=self._get_dialog_parent(),
            )
            return
        self.project.custom_chars[number] = ["00000" for _ in range(8)]
        self._custom_char_number.set(number)
        self._refresh_custom_char_selector()

    def _on_remove_custom_char(self) -> None:
        number = int(self._custom_char_number.get())
        if number not in self.project.custom_chars:
            return
        if not messagebox.askyesno(
            "Remove Custom Char",
            f"Remove custom char {number}?",
            parent=self._get_dialog_parent(),
        ):
            return
        self.project.custom_chars.pop(number, None)
        self._refresh_custom_char_selector()

    def _on_rename_custom_char(self) -> None:
        number = int(self._custom_char_number.get())
        if number not in self.project.custom_chars:
            return
        new_value = simpledialog.askstring(
            "Rename Custom Char",
            "New number (0-255):",
            initialvalue=str(number),
            parent=self._get_dialog_parent(),
        )
        if new_value is None:
            return
        try:
            new_number = int(new_value)
        except ValueError:
            messagebox.showerror(
                "Custom Char",
                "Enter a valid number.",
                parent=self._get_dialog_parent(),
            )
            return
        if new_number < 0 or new_number > 255:
            messagebox.showerror(
                "Custom Char",
                "Number must be 0-255.",
                parent=self._get_dialog_parent(),
            )
            return
        if new_number in self.project.custom_chars and new_number != number:
            messagebox.showerror(
                "Custom Char",
                "That number already exists.",
                parent=self._get_dialog_parent(),
            )
            return
        pattern = self.project.custom_chars.pop(number)
        self.project.custom_chars[new_number] = pattern
        self._custom_char_number.set(new_number)
        self._refresh_custom_char_selector()

    def _load_custom_char_bits(self, number: int) -> None:
        self._custom_char_updating = True
        pattern = self.project.custom_chars.get(number)
        if not pattern:
            self._custom_char_bits = [[0 for _ in range(5)] for _ in range(8)]
        else:
            self._custom_char_bits = [
                [1 if bit == "1" else 0 for bit in row[:5]]
                for row in pattern[:8]
            ]
            while len(self._custom_char_bits) < 8:
                self._custom_char_bits.append([0 for _ in range(5)])

        self._render_custom_char_grid()
        self._custom_char_updating = False

    def _render_custom_char_grid(self) -> None:
        if not self._custom_char_buttons:
            return
        on_color = self.settings.style.pixel_on
        off_color = self.settings.style.pixel_off
        border_color = self.settings.style.frame
        for r in range(8):
            for c in range(5):
                color = on_color if self._custom_char_bits[r][c] else off_color
                self._custom_char_buttons[r][c].configure(
                    background=color,
                    activebackground=color,
                    highlightbackground=border_color,
                    highlightthickness=1,
                    relief="flat",
                )

    def _refresh_custom_char_grid_colors(self) -> None:
        if not self._custom_char_buttons:
            return
        self._configure_custom_char_styles()
        self._render_custom_char_grid()

    def _configure_custom_char_styles(self) -> None:
        style = ttk.Style()
        style.configure(
            self._custom_char_bg_style,
            background=self.settings.style.background,
        )
        style.configure(
            self._custom_char_grid_style,
            background=self.settings.style.background,
        )

    def _toggle_custom_char(self, row: int, col: int) -> None:
        if row < 0 or row >= 8 or col < 0 or col >= 5:
            return
        self._custom_char_bits[row][col] = (
            0 if self._custom_char_bits[row][col] else 1
        )
        self._render_custom_char_grid()
        self._save_custom_char_bits()
        self._schedule_render()

    def _save_custom_char_bits(self) -> None:
        number = int(self._custom_char_number.get())
        rows = [
            "".join("1" if bit else "0" for bit in row)
            for row in self._custom_char_bits
        ]
        if all(row == "00000" for row in rows):
            self.project.custom_chars.pop(number, None)
            return
        self.project.custom_chars[number] = rows

    def _clear_custom_char(self) -> None:
        self._custom_char_bits = [[0 for _ in range(5)] for _ in range(8)]
        self._render_custom_char_grid()
        self._save_custom_char_bits()
        self._schedule_render()

    def _schedule_render(self) -> None:
        if self._render_job is not None:
            self.after_cancel(self._render_job)
        self._render_job = self.after(500, self._render_svg)

    def _render_svg(self) -> None:
        self._render_job = None
        text = self._text_widget.get("1.0", "end-1c")
        lines = text.splitlines()

        svg = generate_lcd_svg(
            rows=self.settings.rows,
            cols=self.settings.cols,
            lines=lines,
            style=self.settings.style,
            custom_chars=self.project.custom_chars,
        )

        self._last_svg = svg
        self._update_preview()

    def _on_preview_resize(self, _event: Any = None) -> None:
        if self._last_svg:
            self._update_preview()

    def _update_preview(self) -> None:
        if not self._last_svg:
            return
        width = max(self.image_label.winfo_width(), 1)
        height = max(self.image_label.winfo_height(), 1)
        try:
            png_bytes = cairosvg.svg2png(
                bytestring=self._last_svg.encode("utf-8"),
                output_width=width,
            )
            image = Image.open(io.BytesIO(png_bytes))
            image = ImageOps.contain(
                image,
                (width, height),
                method=Image.LANCZOS,
            )
            self._image_ref = ImageTk.PhotoImage(image)
            self.image_label.configure(image=self._image_ref, text="")
        except Exception as exc:  # noqa: BLE001
            self.image_label.configure(
                text=(
                    "Failed to render SVG. Ensure cairosvg is installed.\n"
                    f"Error: {exc}"
                ),
                image="",
            )

    def _on_load_settings(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Load Settings",
            filetypes=[("LCD Settings", "*.lcd_settings")],
        )
        if not file_path:
            return
        try:
            self.settings = load_settings(file_path)
            self.project.settings = self.settings
            self._load_settings_into_ui()
            self._schedule_render()
        except OSError as exc:
            messagebox.showerror("Settings", f"Failed to load settings: {exc}")

    def _on_save_settings(self) -> None:
        file_path = filedialog.asksaveasfilename(
            title="Save Settings",
            defaultextension=".lcd_settings",
            filetypes=[("LCD Settings", "*.lcd_settings")],
        )
        if not file_path:
            return
        try:
            save_settings(file_path, self.settings)
        except OSError as exc:
            messagebox.showerror("Settings", f"Failed to save settings: {exc}")

    def _load_settings_into_ui(self) -> None:
        self.var_rows.set(self.settings.rows)
        self.var_cols.set(self.settings.cols)
        self.var_pixel_size.set(self.settings.style.pixel_size)
        self.var_pixel_gap.set(self.settings.style.pixel_gap)
        self.var_char_gap.set(self.settings.style.char_gap)
        self.var_row_gap.set(self.settings.style.row_gap)
        self.var_padding.set(self.settings.style.padding)
        self.var_frame_width.set(self.settings.style.frame_width)
        self.var_border_radius.set(self.settings.style.border_radius)
        self.var_bg.set(self.settings.style.background)
        self.var_frame.set(self.settings.style.frame)
        self.var_pixel_on.set(self.settings.style.pixel_on)
        self.var_pixel_off.set(self.settings.style.pixel_off)

    def _on_load_project(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Load Project",
            filetypes=[("LCD Project", "*.lcd_project")],
        )
        if not file_path:
            return
        try:
            self.project = load_project(file_path)
            self.settings = self.project.settings
            self._load_settings_into_ui()
            self._refresh_input_selector()
            self._load_active_input_text()
            self._schedule_render()
        except OSError as exc:
            messagebox.showerror("Project", f"Failed to load project: {exc}")

    def _on_save_project(self) -> None:
        file_path = filedialog.asksaveasfilename(
            title="Save Project",
            defaultextension=".lcd_project",
            filetypes=[("LCD Project", "*.lcd_project")],
        )
        if not file_path:
            return
        self._update_active_input_text()
        try:
            save_project(file_path, self.project)
        except OSError as exc:
            messagebox.showerror("Project", f"Failed to save project: {exc}")

    def _load_presets(self) -> list[dict[str, Any]]:
        if not PRESETS_PATH.exists():
            return [
                {
                    "name": "Yellow LCD",
                    "settings": {
                        "rows": 4,
                        "cols": 20,
                        "style": {
                            "background": "#d8f245",
                            "frame": "#000000",
                            "pixel_on": "#141f14",
                            "pixel_off": "#cde543",
                            "border_radius": 12,
                            "padding": 16,
                            "pixel_size": 3,
                            "pixel_gap": 1,
                            "char_gap": 4,
                            "row_gap": 10,
                            "frame_width": 8,
                        },
                    },
                }
            ]
        try:
            data = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
            return list(data.get("presets", []))
        except (OSError, json.JSONDecodeError):
            return []

    def _refresh_input_selector(self) -> None:
        names = [item.name for item in self.project.inputs]
        if not names:
            names = ["Input 1"]
            self.project.inputs = [LCDInput(name="Input 1", text="")]
            self.project.active_input = 0
        self.input_selector["values"] = names
        active = min(self.project.active_input, len(names) - 1)
        self.project.active_input = active
        self.input_selector.current(active)

    def _load_active_input_text(self) -> None:
        if not self.project.inputs:
            return
        text = self.project.inputs[self.project.active_input].text
        self._suppress_text_events = True
        self._text_widget.delete("1.0", "end")
        self._text_widget.insert("1.0", text)
        self._text_widget.edit_modified(False)
        self._suppress_text_events = False

    def _update_active_input_text(self) -> None:
        if self._suppress_text_events or not self.project.inputs:
            return
        text = self._text_widget.get("1.0", "end-1c")
        self.project.inputs[self.project.active_input].text = text

    def _on_input_select(self, _event: Any = None) -> None:
        index = self.input_selector.current()
        if index < 0:
            return
        self.project.active_input = index
        self._load_active_input_text()
        self._schedule_render()

    def _on_add_input(self) -> None:
        new_index = len(self.project.inputs) + 1
        self.project.inputs.append(
            LCDInput(name=f"Input {new_index}", text="")
        )
        self.project.active_input = len(self.project.inputs) - 1
        self._refresh_input_selector()
        self._load_active_input_text()
        self._schedule_render()

    def _on_remove_input(self) -> None:
        if len(self.project.inputs) <= 1:
            return
        index = self.project.active_input
        name = self.project.inputs[index].name
        if not messagebox.askyesno(
            "Remove Input",
            f"Remove input '{name}'?",
            parent=self._get_dialog_parent(),
        ):
            return
        self.project.inputs.pop(index)
        self.project.active_input = max(0, index - 1)
        self._refresh_input_selector()
        self._load_active_input_text()
        self._schedule_render()

    def _on_rename_input(self) -> None:
        if not self.project.inputs:
            return
        index = self.project.active_input
        current_name = self.project.inputs[index].name
        new_name = simpledialog.askstring(
            "Rename Input",
            "New name:",
            initialvalue=current_name,
            parent=self._get_dialog_parent(),
        )
        if not new_name:
            return
        self.project.inputs[index].name = new_name.strip() or current_name
        self._refresh_input_selector()

    def _on_save_svg(self) -> None:
        file_path = filedialog.asksaveasfilename(
            title="Save SVG",
            defaultextension=".svg",
            filetypes=[("SVG", "*.svg")],
        )
        if not file_path:
            return
        if not self._last_svg:
            self._render_svg()
        if not self._last_svg:
            messagebox.showerror("SVG", "Nothing to save yet.")
            return
        try:
            Path(file_path).write_text(self._last_svg, encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("SVG", f"Failed to save SVG: {exc}")

    def _get_dialog_parent(self) -> tk.Misc:
        if (
            self._custom_chars_window
            and self._custom_chars_window.winfo_exists()
        ):
            return self._custom_chars_window
        if self._settings_window and self._settings_window.winfo_exists():
            return self._settings_window
        return self


if __name__ == "__main__":
    app = LCDApp()
    app.mainloop()
