"""
middle_panel.py — 中欄：檔案清單區

顏色邏輯：
  ┌─ 有聚焦規則 ────────────────────────────────────────────────┐
  │  命中聚焦規則 → 規則顏色（alpha 85）＋正常文字              │
  │  未命中       → 極暗背景（28,28,28）＋灰色文字（視覺隱退）  │
  └─────────────────────────────────────────────────────────────┘
  ┌─ 無聚焦規則（一般模式）─────────────────────────────────────┐
  │  命中任何已啟用規則 → 第一個命中規則顏色（alpha 55）        │
  │  未命中已啟用規則   → 暗淡文字（有規則但此檔不符合）        │
  │  無任何已啟用規則   → 正常顯示                              │
  └─────────────────────────────────────────────────────────────┘

過濾邏輯（僅顯示命中）：
  filter_mode=True → 隱藏不符合聚焦/已啟用規則的檔案
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QFileDialog, QCheckBox,
    QFrame, QScrollArea, QProgressBar,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QBrush

from models import Rule
from file_manager import format_size, FileScannerThread

COMMON_EXTS = [
    ".txt", ".md", ".csv", ".html", ".xml",
    ".json", ".yml", ".yaml", ".ini", ".cfg",
    ".py", ".js", ".ts", ".css",
]
DEFAULT_CHECKED = {".txt", ".md", ".csv", ".html", ".xml"}

_DIM_BG   = QColor(28, 28, 28)
_NORM_BG  = QColor(45, 45, 45)
_DIM_FG   = QColor(72, 72, 72)
_GREY_FG  = QColor(110, 110, 110)
_NORM_FG  = QColor(180, 180, 180)
_BRIGHT_FG = QColor(225, 225, 225)


# ──────────────────────────────────────────────
# 檔案清單項目
# ──────────────────────────────────────────────

class FileListItem(QListWidgetItem):
    def __init__(self, info: dict):
        super().__init__()
        self.info = info
        self._refresh_text()

    # ── 文字 ──────────────────────────────────

    def _refresh_text(self):
        name   = self.info.get("name", "")
        size   = format_size(self.info.get("size", 0))
        enc    = self.info.get("encoding", "?").upper()
        mtime  = self.info.get("mtime", 0)
        counts = self.info.get("match_counts", {})

        mtime_str = (
            datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            if mtime else ""
        )
        total     = sum(counts.values())
        rules_hit = len(counts)
        match_str = f"  [{rules_hit}規則 / {total}處]" if total else ""
        self.setText(f"{name}   {size}   {enc}   {mtime_str}{match_str}")
        self.setToolTip(self.info.get("path", ""))

    # ── 顏色 ──────────────────────────────────

    def apply_color(self, rules: list, focused: Optional[Rule]) -> None:
        counts = self.info.get("match_counts", {})
        enabled_rules = [r for r in rules if r.enabled]

        if focused:
            # ─ 聚焦模式 ───────────────────────
            if focused.id in counts:
                bg = QColor(focused.color)
                bg.setAlpha(85)
                self.setBackground(QBrush(bg))
                self.setForeground(QBrush(_BRIGHT_FG))
            else:
                self.setBackground(QBrush(_DIM_BG))
                self.setForeground(QBrush(_DIM_FG))

        else:
            # ─ 一般模式 ───────────────────────
            matched_rule = next(
                (r for r in enabled_rules if r.id in counts), None
            )
            if matched_rule:
                bg = QColor(matched_rule.color)
                bg.setAlpha(55)
                self.setBackground(QBrush(bg))
                self.setForeground(QBrush(_BRIGHT_FG))
            elif enabled_rules:
                # 有啟用規則，但此檔不符合
                self.setBackground(QBrush(_NORM_BG))
                self.setForeground(QBrush(_GREY_FG))
            else:
                # 無任何啟用規則 → 正常
                self.setBackground(QBrush(_NORM_BG))
                self.setForeground(QBrush(_NORM_FG))

    # ── 過濾可見性 ────────────────────────────

    def should_show(
        self, rules: list, focused: Optional[Rule], filter_mode: bool
    ) -> bool:
        if not filter_mode:
            return True
        counts = self.info.get("match_counts", {})
        if not counts:
            return False
        if focused:
            return focused.id in counts
        enabled_ids = {r.id for r in rules if r.enabled}
        return bool(counts.keys() & enabled_ids)

    # ── 更新計數 ──────────────────────────────

    def update_counts(
        self, counts: dict, rules: list, focused: Optional[Rule]
    ) -> None:
        self.info["match_counts"] = counts
        self._refresh_text()
        self.apply_color(rules, focused)


# ──────────────────────────────────────────────
# 中欄整體
# ──────────────────────────────────────────────

class MiddlePanel(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.work_dir: Optional[str] = None
        self.rules: list = []
        self.focused: Optional[Rule] = None
        self.items: dict[str, FileListItem] = {}
        self.selected_exts: set = set(DEFAULT_CHECKED)
        self.case_sensitive: bool = True
        self.filter_mode: bool = False
        self._scanner: Optional[FileScannerThread] = None
        self._build()

    # ── 建構 UI ───────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        title = QLabel("檔案清單")
        title.setStyleSheet("font-size:13px;font-weight:bold;color:#CCC;")
        layout.addWidget(title)

        # 資料夾選擇
        self.open_btn = QPushButton("📂 開啟資料夾")
        self.open_btn.clicked.connect(self._open_folder)
        layout.addWidget(self.open_btn)

        self.path_label = QLabel("尚未選擇資料夾")
        self.path_label.setStyleSheet("color:#777;font-size:10px;")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        # 副檔名過濾
        ext_lbl = QLabel("副檔名過濾：")
        ext_lbl.setStyleSheet("color:#AAA;font-size:10px;")
        layout.addWidget(ext_lbl)

        ext_scroll = QScrollArea()
        ext_scroll.setMaximumHeight(66)
        ext_scroll.setWidgetResizable(True)
        ext_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        ext_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        ext_inner = QWidget()
        ext_row = QHBoxLayout(ext_inner)
        ext_row.setContentsMargins(4, 2, 4, 2)
        ext_row.setSpacing(6)

        self.ext_checks: dict[str, QCheckBox] = {}
        for ext in COMMON_EXTS:
            cb = QCheckBox(ext)
            cb.setChecked(ext in DEFAULT_CHECKED)
            cb.toggled.connect(self._on_ext_changed)
            ext_row.addWidget(cb)
            self.ext_checks[ext] = cb
        ext_row.addStretch()

        ext_scroll.setWidget(ext_inner)
        layout.addWidget(ext_scroll)

        # 過濾列：僅顯示命中
        filter_row = QHBoxLayout()
        self.filter_cb = QCheckBox("僅顯示命中檔案")
        self.filter_cb.setStyleSheet("color:#AAA;font-size:10px;")
        self.filter_cb.toggled.connect(self._on_filter_toggled)
        filter_row.addWidget(self.filter_cb)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # 進度條
        self.progress = QProgressBar()
        self.progress.setMaximumHeight(4)
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color:#777;font-size:10px;")
        layout.addWidget(self.status_lbl)

        # 檔案清單
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background:#252526; border:1px solid #3C3C3C;
                outline:none;
            }
            QListWidget::item {
                padding:4px 6px;
                border-bottom:1px solid #2E2E2E;
                font-family:Consolas,'Microsoft JhengHei',sans-serif;
                font-size:11px;
            }
            QListWidget::item:selected { background:#094771; }
            QListWidget::item:hover    { background:#2A2D2E; }
        """)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget, 1)

    # ── 事件 / Slot ───────────────────────────

    def _on_ext_changed(self):
        self.selected_exts = {
            ext for ext, cb in self.ext_checks.items() if cb.isChecked()
        }
        if self.work_dir:
            self._start_scan()

    def _on_filter_toggled(self, checked: bool):
        self.filter_mode = checked
        self._refresh_display()

    def _open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "選擇工作目錄")
        if folder:
            self.set_work_dir(folder)

    def _on_item_clicked(self, item: QListWidgetItem):
        if isinstance(item, FileListItem):
            self.file_selected.emit(item.info["path"])

    # ── 掃描 ──────────────────────────────────

    def _start_scan(self):
        if self._scanner and self._scanner.isRunning():
            self._scanner.cancel()
            self._scanner.wait(500)

        self.list_widget.clear()
        self.items.clear()
        self.progress.setVisible(True)
        self.status_lbl.setText("掃描中…")

        self._scanner = FileScannerThread(
            self.work_dir,
            self.selected_exts,
            self.rules,
            self.case_sensitive,
        )
        self._scanner.file_found.connect(self._on_file_found)
        self._scanner.scan_complete.connect(self._on_scan_done)
        self._scanner.scan_progress.connect(
            lambda msg: self.status_lbl.setText(f"掃描：{msg}")
        )
        self._scanner.scan_error.connect(
            lambda msg: self.status_lbl.setText(f"錯誤：{msg}")
        )
        self._scanner.start()

    def _on_file_found(self, info: dict):
        item = FileListItem(info)
        item.apply_color(self.rules, self.focused)
        hidden = not item.should_show(self.rules, self.focused, self.filter_mode)
        item.setHidden(hidden)
        self.list_widget.addItem(item)
        self.items[info["path"]] = item

    def _on_scan_done(self, count: int):
        self.progress.setVisible(False)
        self._update_status()

    # ── 即時重整（不重新掃描）────────────────

    def _refresh_display(self):
        """依據現有 match_counts 重新著色＋套用過濾，無需重新掃描。"""
        for item in self.items.values():
            item.apply_color(self.rules, self.focused)
            hidden = not item.should_show(self.rules, self.focused, self.filter_mode)
            item.setHidden(hidden)
        self._update_status()

    def _update_status(self):
        total   = len(self.items)
        visible = sum(1 for it in self.items.values() if not it.isHidden())
        if self.filter_mode and visible < total:
            self.status_lbl.setText(f"顯示 {visible} / 共 {total} 個檔案")
        else:
            self.status_lbl.setText(f"共 {total} 個檔案")

    @staticmethod
    def _only_enable_changed(old: list, new: list) -> bool:
        """判斷兩份規則清單是否只有 enabled 狀態不同（其他條件不變）。"""
        if len(old) != len(new):
            return False
        for o, n in zip(old, new):
            if o.id != n.id:
                return False
            if (o.search_terms != n.search_terms
                    or o.replace_with  != n.replace_with
                    or o.regex_mode    != n.regex_mode
                    or o.word_boundary != n.word_boundary):
                return False
        return True

    # ── 外部介面 ──────────────────────────────

    def set_work_dir(self, path: str):
        self.work_dir = path
        self.path_label.setText(path)
        self._start_scan()

    def set_rules(self, rules: list, case_sensitive: bool = True):
        old_rules = self.rules
        self.rules = rules
        self.case_sensitive = case_sensitive

        if not self.work_dir:
            return

        # 只有 enabled 狀態改變 → 直接重整顏色，不重新掃描
        if self.items and self._only_enable_changed(old_rules, rules):
            self._refresh_display()
        else:
            self._start_scan()

    def set_focused(self, rule: Optional[Rule]):
        self.focused = rule
        self._refresh_display()

    def refresh(self):
        if self.work_dir:
            self._start_scan()
