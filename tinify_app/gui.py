from __future__ import annotations

import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any

import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD

from tinify_app import compressor
from tinify_app.config import load_config, save_config

# Prefer Windows UI fonts that actually cover Chinese. CustomTkinter's
# default "Roboto" makes CJK fall back to mismatched system fonts.
_UI_FONT_CANDIDATES = (
    "Microsoft YaHei UI",
    "微软雅黑",
    "Segoe UI",
    "Noto Sans SC",
)
API_KEY_URL = "https://tinypng.com/developers"


def _enable_windows_dpi() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            import ctypes

            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _pick_ui_font_family(root: tk.Misc) -> str:
    available = set(tkfont.families(root))
    for name in _UI_FONT_CANDIDATES:
        if name in available:
            return name
    return "TkDefaultFont"


def _apply_ui_font(root: tk.Misc) -> str:
    family = _pick_ui_font_family(root)
    theme_font = ctk.ThemeManager.theme.get("CTkFont")
    if isinstance(theme_font, dict):
        theme_font["family"] = family
    return family


class CTkDnD(ctk.CTk, TkinterDnD.DnDWrapper):
    """CustomTkinter root with Windows drag-and-drop support."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)


class TinifyApp:
    ACCENT = "#0D9488"
    ACCENT_HOVER = "#0F766E"
    SURFACE = "#F4F7F6"
    CARD = "#FFFFFF"
    INK = "#0F172A"
    MUTED = "#64748B"
    BORDER = "#D8E2DE"
    DANGER = "#DC2626"
    OK = "#059669"

    def __init__(self) -> None:
        _enable_windows_dpi()
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("green")

        self.config = load_config()
        self.root = CTkDnD()
        self.ui_font = _apply_ui_font(self.root)
        self.root.title("Tinify Compress")
        self.root.geometry("1000x680")
        self.root.minsize(880, 580)
        self.root.configure(fg_color=self.SURFACE)

        self.files: list[Path] = []
        self.busy = False
        self.file_vars: dict[str, ctk.StringVar] = {}

        self._build_ui()
        self._bind_dnd()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        if self.config.get("api_key"):
            self.api_key_var.set(self.config["api_key"])
            self._set_status("已加载本地保存的 API Key，可点击「校验」确认。")

    def _font(self, size: int = 13, weight: str = "normal") -> ctk.CTkFont:
        return ctk.CTkFont(family=self.ui_font, size=size, weight=weight)

    def _build_ui(self) -> None:
        pad = {"padx": 20, "pady": (16, 0)}

        header = ctk.CTkFrame(self.root, fg_color="transparent")
        header.pack(fill="x", **pad)

        title = ctk.CTkLabel(
            header,
            text="Tinify",
            font=self._font(size=28, weight="bold"),
            text_color=self.INK,
        )
        title.pack(side="left")

        subtitle = ctk.CTkLabel(
            header,
            text="  图片压缩客户端",
            font=self._font(size=16),
            text_color=self.MUTED,
        )
        subtitle.pack(side="left", pady=(8, 0))

        # API key row
        key_card = ctk.CTkFrame(
            self.root,
            fg_color=self.CARD,
            corner_radius=14,
            border_width=1,
            border_color=self.BORDER,
        )
        key_card.pack(fill="x", padx=20, pady=(14, 0))

        key_inner = ctk.CTkFrame(key_card, fg_color="transparent")
        key_inner.pack(fill="x", padx=14, pady=12)

        key_title = ctk.CTkFrame(key_inner, fg_color="transparent")
        key_title.pack(fill="x")

        ctk.CTkLabel(
            key_title,
            text="API Key",
            font=self._font(size=13, weight="bold"),
            text_color=self.INK,
        ).pack(side="left")

        apply_link = ctk.CTkLabel(
            key_title,
            text="申请 API Key →",
            font=self._font(size=12),
            text_color=self.ACCENT,
            cursor="hand2",
        )
        apply_link.pack(side="right")
        apply_link.bind("<Button-1>", self._open_api_key_page)
        apply_link.bind(
            "<Enter>",
            lambda _e: apply_link.configure(text_color=self.ACCENT_HOVER),
        )
        apply_link.bind(
            "<Leave>",
            lambda _e: apply_link.configure(text_color=self.ACCENT),
        )

        key_row = ctk.CTkFrame(key_inner, fg_color="transparent")
        key_row.pack(fill="x", pady=(6, 0))

        self.api_key_var = ctk.StringVar()
        self.api_entry = ctk.CTkEntry(
            key_row,
            textvariable=self.api_key_var,
            placeholder_text="填入申请到的 API Key",
            show="•",
            height=36,
            font=self._font(size=13),
        )
        self.api_entry.pack(side="left", fill="x", expand=True)

        self.show_key = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            key_row,
            text="显示",
            variable=self.show_key,
            command=self._toggle_key_visibility,
            width=56,
            checkbox_width=18,
            checkbox_height=18,
            font=self._font(size=13),
        ).pack(side="left", padx=(10, 0))

        self.validate_btn = ctk.CTkButton(
            key_row,
            text="校验",
            width=72,
            height=36,
            fg_color=self.ACCENT,
            hover_color=self.ACCENT_HOVER,
            font=self._font(size=13),
            command=self._validate_key,
        )
        self.validate_btn.pack(side="left", padx=(8, 0))

        ctk.CTkButton(
            key_row,
            text="保存",
            width=72,
            height=36,
            fg_color="#E2E8F0",
            hover_color="#CBD5E1",
            text_color=self.INK,
            font=self._font(size=13),
            command=self._save_key,
        ).pack(side="left", padx=(8, 0))

        self.key_hint = ctk.CTkLabel(
            key_inner,
            text="",
            font=self._font(size=12),
            text_color=self.MUTED,
            anchor="w",
        )
        self.key_hint.pack(fill="x", pady=(6, 0))

        # Options
        options = ctk.CTkFrame(
            self.root,
            fg_color=self.CARD,
            corner_radius=14,
            border_width=1,
            border_color=self.BORDER,
        )
        options.pack(fill="x", padx=20, pady=(12, 0))

        opt_inner = ctk.CTkFrame(options, fg_color="transparent")
        opt_inner.pack(fill="x", padx=14, pady=12)

        ctk.CTkLabel(
            opt_inner,
            text="输出方式",
            font=self._font(size=13, weight="bold"),
            text_color=self.INK,
        ).pack(anchor="w")

        mode_row = ctk.CTkFrame(opt_inner, fg_color="transparent")
        mode_row.pack(fill="x", pady=(6, 0))

        self.output_mode = ctk.StringVar(value=self.config.get("output_mode", "suffix"))
        self.suffix_var = ctk.StringVar(value=self.config.get("suffix", "_tinified"))

        # Keep radio + suffix field in one group so the entry always follows this option.
        self.suffix_group = ctk.CTkFrame(mode_row, fg_color="transparent")
        self.suffix_group.pack(side="left")

        ctk.CTkRadioButton(
            self.suffix_group,
            text="同目录加后缀",
            variable=self.output_mode,
            value="suffix",
            command=self._on_mode_change,
            font=self._font(size=13),
        ).pack(side="left")

        self.suffix_entry = ctk.CTkEntry(
            self.suffix_group,
            textvariable=self.suffix_var,
            width=120,
            height=32,
            placeholder_text="如 _tinified",
            font=self._font(size=13),
        )

        ctk.CTkRadioButton(
            mode_row,
            text="覆盖原文件",
            variable=self.output_mode,
            value="overwrite",
            command=self._on_mode_change,
            font=self._font(size=13),
        ).pack(side="left", padx=(18, 0))

        ctk.CTkRadioButton(
            mode_row,
            text="指定文件夹",
            variable=self.output_mode,
            value="custom",
            command=self._on_mode_change,
            font=self._font(size=13),
        ).pack(side="left", padx=(18, 0))

        self.dir_row = ctk.CTkFrame(opt_inner, fg_color="transparent")

        self.output_dir_var = ctk.StringVar(value=self.config.get("output_dir", ""))
        self.output_dir_entry = ctk.CTkEntry(
            self.dir_row,
            textvariable=self.output_dir_var,
            placeholder_text="自定义输出目录",
            height=32,
            font=self._font(size=13),
        )
        self.output_dir_entry.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            self.dir_row,
            text="浏览…",
            width=72,
            height=32,
            fg_color="#E2E8F0",
            hover_color="#CBD5E1",
            text_color=self.INK,
            font=self._font(size=13),
            command=self._browse_output_dir,
        ).pack(side="left", padx=(8, 0))

        self._on_mode_change()

        # Footer pinned to bottom so status + notice stay visible.
        footer = ctk.CTkFrame(self.root, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=20, pady=(8, 14))

        ctk.CTkLabel(
            footer,
            text="提示：本软件通过调用 Tinify API 上传并压缩图片，如需处理机密图片，请不要使用。",
            font=self._font(size=11),
            text_color="#B45309",
            anchor="w",
        ).pack(fill="x", pady=(0, 6))

        status_bar = ctk.CTkFrame(footer, fg_color="transparent")
        status_bar.pack(fill="x")

        self.status_var = ctk.StringVar(value="准备就绪。填入 API Key 后拖入图片即可压缩。")
        ctk.CTkLabel(
            status_bar,
            textvariable=self.status_var,
            font=self._font(size=12),
            text_color=self.MUTED,
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        self.progress = ctk.CTkProgressBar(
            status_bar,
            width=160,
            height=8,
            progress_color=self.ACCENT,
        )
        self.progress.pack(side="right")
        self.progress.set(0)

        # Main work area: drop zone (left) + file queue (right)
        content = ctk.CTkFrame(self.root, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=(10, 0))
        # Left drop zone should dominate width; queue is secondary.
        content.grid_columnconfigure(0, weight=3, minsize=360)
        content.grid_columnconfigure(1, weight=2, minsize=280)
        content.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(content, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.drop_frame = ctk.CTkFrame(
            left,
            fg_color="#ECFDF8",
            corner_radius=14,
            border_width=2,
            border_color="#99F6E4",
        )
        self.drop_frame.pack(fill="both", expand=True)

        drop_inner = ctk.CTkFrame(self.drop_frame, fg_color="transparent")
        drop_inner.place(relx=0.5, rely=0.45, anchor="center")

        ctk.CTkLabel(
            drop_inner,
            text="把图片拖到这里",
            font=self._font(size=18, weight="bold"),
            text_color=self.INK,
        ).pack()
        ctk.CTkLabel(
            drop_inner,
            text="支持 PNG / JPEG / WebP / AVIF / JXL / HEIC",
            font=self._font(size=12),
            text_color=self.MUTED,
        ).pack(pady=(6, 0))
        ctk.CTkLabel(
            drop_inner,
            text="也可使用下方按钮选择文件",
            font=self._font(size=12),
            text_color=self.MUTED,
        ).pack(pady=(2, 0))

        actions = ctk.CTkFrame(left, fg_color="transparent")
        actions.pack(fill="x", pady=(10, 0))

        ctk.CTkButton(
            actions,
            text="添加图片",
            height=34,
            fg_color="#E2E8F0",
            hover_color="#CBD5E1",
            text_color=self.INK,
            font=self._font(size=13),
            command=self._browse_files,
        ).pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            actions,
            text="清空列表",
            height=34,
            fg_color="#E2E8F0",
            hover_color="#CBD5E1",
            text_color=self.INK,
            font=self._font(size=13),
            command=self._clear_files,
        ).pack(side="left", fill="x", expand=True, padx=(8, 0))

        self.compress_btn = ctk.CTkButton(
            left,
            text="开始压缩",
            height=40,
            fg_color=self.ACCENT,
            hover_color=self.ACCENT_HOVER,
            font=self._font(size=14, weight="bold"),
            command=self._start_compress,
        )
        self.compress_btn.pack(fill="x", pady=(8, 0))

        list_card = ctk.CTkFrame(
            content,
            fg_color=self.CARD,
            corner_radius=14,
            border_width=1,
            border_color=self.BORDER,
        )
        list_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        list_header = ctk.CTkFrame(list_card, fg_color="transparent")
        list_header.pack(fill="x", padx=14, pady=(10, 2))
        ctk.CTkLabel(
            list_header,
            text="文件队列",
            font=self._font(size=13, weight="bold"),
            text_color=self.INK,
        ).pack(side="left")
        self.queue_count = ctk.CTkLabel(
            list_header,
            text="0 个文件",
            font=self._font(size=12),
            text_color=self.MUTED,
        )
        self.queue_count.pack(side="right")

        self.file_list = ctk.CTkScrollableFrame(
            list_card,
            fg_color="transparent",
            corner_radius=0,
        )
        self.file_list.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _bind_dnd(self) -> None:
        # Register drop on the visual drop zone and the whole window.
        for widget in (self.drop_frame, self.root):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_drop)

    def _open_api_key_page(self, _event: Any = None) -> None:
        webbrowser.open(API_KEY_URL)

    def _toggle_key_visibility(self) -> None:
        self.api_entry.configure(show="" if self.show_key.get() else "•")

    def _on_mode_change(self) -> None:
        mode = self.output_mode.get()
        if mode == "suffix":
            if not self.suffix_entry.winfo_manager():
                self.suffix_entry.pack(side="left", padx=(8, 0))
        elif self.suffix_entry.winfo_manager():
            self.suffix_entry.pack_forget()

        if mode == "custom":
            if not self.dir_row.winfo_manager():
                self.dir_row.pack(fill="x", pady=(8, 0))
        elif self.dir_row.winfo_manager():
            self.dir_row.pack_forget()

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _set_key_hint(self, text: str, *, ok: bool | None = None) -> None:
        if ok is True:
            color = self.OK
        elif ok is False:
            color = self.DANGER
        else:
            color = self.MUTED
        self.key_hint.configure(text=text, text_color=color)

    def _save_settings_to_config(self) -> None:
        self.config["api_key"] = self.api_key_var.get().strip()
        self.config["output_mode"] = self.output_mode.get()
        self.config["suffix"] = self.suffix_var.get().strip() or "_tinified"
        self.config["output_dir"] = self.output_dir_var.get().strip()
        save_config(self.config)

    def _save_key(self) -> None:
        self._save_settings_to_config()
        self._set_status(f"已保存到 {Path.home() / 'AppData' / 'Roaming' / 'TinifyCompress' / 'config.json'}")

    def _validate_key(self) -> None:
        key = self.api_key_var.get().strip()
        if not key:
            self._set_key_hint("请先填写 API Key", ok=False)
            self._set_status("请先填写 API Key")
            messagebox.showwarning("缺少 API Key", "请先填写 Tinify API Key。")
            return

        self.validate_btn.configure(state="disabled", text="校验中…")
        self._set_key_hint("正在校验 API Key…")
        self._set_status("正在校验 API Key…")
        self.root.update_idletasks()

        def worker() -> None:
            ok, message, count = compressor.validate_api_key(key)

            def done() -> None:
                self.validate_btn.configure(state="normal", text="校验")
                if ok:
                    self._save_settings_to_config()
                    count_text = f"{count}" if count is not None else "—"
                    hint = f"校验成功 · 本月已压缩 {count_text} 次"
                    self._set_key_hint(hint, ok=True)
                    self._set_status(hint)
                    messagebox.showinfo(
                        "校验成功",
                        f"API Key 有效。\n本月已压缩 {count_text} 次。",
                    )
                else:
                    self._set_key_hint(message, ok=False)
                    self._set_status(message)
                    messagebox.showerror("校验失败", message)

            self.root.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _browse_output_dir(self) -> None:
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.output_dir_var.set(path)
            self.output_mode.set("custom")
            self._on_mode_change()

    def _browse_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="选择图片",
            filetypes=[
                (
                    "Images",
                    "*.png *.jpg *.jpeg *.webp *.avif *.jxl *.heic *.heif",
                ),
                ("All files", "*.*"),
            ],
        )
        if paths:
            self._add_files([Path(p) for p in paths])

    def _on_drop(self, event: Any) -> None:
        raw = self.root.tk.splitlist(event.data)
        paths = [Path(item) for item in raw]
        self._add_files(paths)

    def _add_files(self, paths: list[Path]) -> None:
        added = 0
        skipped = 0
        existing = {str(p.resolve()) for p in self.files}

        for path in paths:
            path = Path(path)
            if path.is_dir():
                for child in path.rglob("*"):
                    if compressor.is_supported_image(child):
                        key = str(child.resolve())
                        if key not in existing:
                            self.files.append(child)
                            existing.add(key)
                            added += 1
                        else:
                            skipped += 1
                continue

            if not compressor.is_supported_image(path):
                skipped += 1
                continue

            key = str(path.resolve())
            if key in existing:
                skipped += 1
                continue

            self.files.append(path)
            existing.add(key)
            added += 1

        self._refresh_file_list()
        msg = f"已添加 {added} 个文件"
        if skipped:
            msg += f"，跳过 {skipped} 个"
        self._set_status(msg)

    def _clear_files(self) -> None:
        if self.busy:
            return
        self.files.clear()
        self._refresh_file_list()
        self.progress.set(0)
        self._set_status("已清空队列。")

    def _refresh_file_list(self) -> None:
        for child in self.file_list.winfo_children():
            child.destroy()
        self.file_vars.clear()

        self.queue_count.configure(text=f"{len(self.files)} 个文件")

        if not self.files:
            ctk.CTkLabel(
                self.file_list,
                text="暂无文件。拖拽或点击「添加图片」。",
                text_color=self.MUTED,
                font=self._font(size=13),
            ).pack(pady=12)
            return

        for path in self.files:
            row = ctk.CTkFrame(self.file_list, fg_color="#F8FAFC", corner_radius=8)
            row.pack(fill="x", pady=3, padx=4)

            name = ctk.CTkLabel(
                row,
                text=path.name,
                anchor="w",
                font=self._font(size=13),
                text_color=self.INK,
            )
            name.pack(side="left", padx=(10, 8), pady=8)

            try:
                size_text = compressor.format_size(path.stat().st_size)
            except OSError:
                size_text = "?"

            ctk.CTkLabel(
                row,
                text=size_text,
                width=70,
                anchor="e",
                font=self._font(size=12),
                text_color=self.MUTED,
            ).pack(side="left")

            status_var = ctk.StringVar(value="待处理")
            self.file_vars[str(path.resolve())] = status_var
            ctk.CTkLabel(
                row,
                textvariable=status_var,
                width=220,
                anchor="e",
                font=self._font(size=12),
                text_color=self.MUTED,
            ).pack(side="right", padx=(0, 10))

            ctk.CTkButton(
                row,
                text="×",
                width=28,
                height=28,
                fg_color="transparent",
                hover_color="#FEE2E2",
                text_color=self.DANGER,
                command=lambda p=path: self._remove_file(p),
            ).pack(side="right", padx=(0, 4))

    def _remove_file(self, path: Path) -> None:
        if self.busy:
            return
        key = str(path.resolve())
        self.files = [p for p in self.files if str(p.resolve()) != key]
        self._refresh_file_list()

    def _start_compress(self) -> None:
        if self.busy:
            return
        if not self.files:
            messagebox.showinfo("提示", "请先添加要压缩的图片。")
            return

        key = self.api_key_var.get().strip()
        if not key:
            messagebox.showwarning("缺少 API Key", "请先填写 Tinify API Key。")
            return

        mode = self.output_mode.get()
        if mode == "custom" and not self.output_dir_var.get().strip():
            messagebox.showwarning("缺少输出目录", "请选择自定义输出文件夹。")
            return

        if mode == "overwrite":
            ok = messagebox.askyesno(
                "确认覆盖",
                f"将直接覆盖原文件（共 {len(self.files)} 个）。是否继续？",
            )
            if not ok:
                return

        self._save_settings_to_config()
        compressor.set_api_key(key)

        paths = list(self.files)
        workers = compressor.recommended_workers()
        output_mode = self.output_mode.get()
        suffix = self.suffix_var.get().strip() or "_tinified"
        output_dir = self.output_dir_var.get().strip()

        self.busy = True
        self.compress_btn.configure(state="disabled", text="压缩中…")
        self.progress.set(0)

        large_count = 0
        for path in paths:
            key_path = str(path.resolve())
            try:
                is_large = path.stat().st_size >= compressor.LARGE_FILE_BYTES
            except OSError:
                is_large = False
            if is_large:
                large_count += 1
                if key_path in self.file_vars:
                    self.file_vars[key_path].set("等待小图完成…")

        if large_count:
            self._set_status(
                f"开始压缩…小图并发 {workers}，{large_count} 张大图稍后单线程处理"
            )
        else:
            self._set_status(f"开始压缩…（并发 {workers} 线程）")

        def worker() -> None:
            total = len(paths)
            finished = 0
            counter_lock = threading.Lock()

            def on_start(path: Path) -> None:
                key_path = str(path.resolve())

                def ui() -> None:
                    if key_path in self.file_vars:
                        self.file_vars[key_path].set("压缩中…")
                    self._set_status(f"正在压缩: {path.name}")

                self.root.after(0, ui)

            def on_done(result: compressor.CompressResult) -> None:
                nonlocal finished
                key_path = str(result.source.resolve())
                with counter_lock:
                    finished += 1
                    current = finished

                def ui() -> None:
                    if key_path in self.file_vars:
                        if result.success:
                            self.file_vars[key_path].set(
                                f"完成 · 省 {compressor.format_size(result.saved_bytes)} "
                                f"({result.saved_percent:.0f}%)"
                            )
                        else:
                            err = result.error
                            if len(err) > 48:
                                err = err[:45] + "…"
                            self.file_vars[key_path].set(f"失败 · {err}")
                    self.progress.set(current / total)

                self.root.after(0, ui)

            def on_progress(message: str) -> None:
                self.root.after(0, lambda: self._set_status(message))

            results = compressor.compress_many(
                paths,
                output_mode=output_mode,
                suffix=suffix,
                output_dir=output_dir,
                max_workers=workers,
                on_start=on_start,
                on_done=on_done,
                on_progress=on_progress,
            )

            def finish() -> None:
                self.busy = False
                self.compress_btn.configure(state="normal", text="开始压缩")
                self.progress.set(1)
                ok_count = sum(1 for r in results if r.success)
                fail_count = len(results) - ok_count
                saved = sum(r.saved_bytes for r in results if r.success)
                count = compressor.get_compression_count()
                status = (
                    f"完成：成功 {ok_count}，失败 {fail_count}，"
                    f"共节省 {compressor.format_size(saved)}（并发 {workers}）"
                )
                if count is not None:
                    status += f" · 本月压缩 {count} 次"
                self._set_status(status)
                if fail_count:
                    errors = "\n".join(
                        f"• {r.source.name}: {r.error}" for r in results if not r.success
                    )
                    messagebox.showwarning("部分失败", errors[:2000])

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _on_close(self) -> None:
        self._save_settings_to_config()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def run_app() -> None:
    # Avoid unused import warning for tk when DnD needs Tk symbols.
    _ = tk
    TinifyApp().run()
