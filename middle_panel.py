"""
middle_panel.py — 中欄：檔案清單區
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QFileDialog, QCheckBox,
    QFrame, QScrollArea, QProgressBar, QSizePolicy,
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


# ──────────────────────────────────────────────
# 檔案清單項目
# ──────────────────────────────────────────────

class FileListItem(QListWidgetItem):
    def __init__(self, info: dict):
        super().__init__()
        self.info = info
        self._refresh_text()

    def _refresh_text(self):
        name     = self.info.get("name", "")
        size     = format_size(self.info.get("size", 0))
        enc      = self.info.get("encoding", "?").upper()
        mtime    = self.info.get("mtime", 0)
        counts   = self.info.get("match_counts", {})

        mtime_str = (
            datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            if mtime else ""
        )
        total = sum(counts.values())
        rules_hit = len(counts)
        match_str = f"  [{rules_hit}規則/{total}處]" if total else ""

        self.setText(f"{name}   {size}   {enc}   {mtime_str}{match_str}")
        self.setToolTip(self.info.get("path", ""))

    def apply_color(self, rules: list, focused: Optional[Rule]):
        counts = self.info.get("match_counts", {})
        bg = QColor(45, 45, 45)

        if focused:
            if focused.id in counts:
                bg = QColor(focused.color)
                bg.setAlpha(55)
        else:
            # 以命中的第一條規則顏色做淡染
            for rule in rules:
                if rule.id in counts:
                    bg = QColor(rule.color)
                    bg.setAlpha(40)
                    break

        self.setBackground(QBrush(bg))

    def update_counts(self, counts: dict, rules: list, focused: Optional[Rule]):
        self.info["match_counts"] = counts
        self._refresh_text()
        self.apply_color(rules, focused)


# ──────────────────────────────────────────────
# 中欄整體
# ──────────────────────────────────────────────

class MiddlePanel(QWidget):
    file_selected = pyqtSignal(str)   # 選中檔案路徑

    def __init__(self, parent=None):
        super().__init__(parent)
        self.work_dir: Optional[str] = None
        self.rules: list = []
        self.focused: Optional[Rule] = None
        self.items: dict[str, FileListItem] = {}   # path -> item
        self.selected_exts: set = set(DEFAULT_CHECKED)
        self.case_sensitive: bool = True
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
        self.selected_exts = {ext for ext, cb in self.ext_checks.items() if cb.isChecked()}
        if self.work_dir:
            self._start_scan()

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
        self.list_widget.addItem(item)
        self.items[info["path"]] = item

    def _on_scan_done(self, count: int):
        self.progress.setVisible(False)
        self.status_lbl.setText(f"共 {count} 個檔案")

    # ── 外部介面 ──────────────────────────────

    def set_work_dir(self, path: str):
        self.work_dir = path
        self.path_label.setText(path)
        self._start_scan()

    def set_rules(self, rules: list, case_sensitive: bool = True):
        self.rules = rules
        self.case_sensitive = case_sensitive
        if self.work_dir:
            self._start_scan()

    def set_focused(self, rule: Optional[Rule]):
        self.focused = rule
        for item in self.items.values():
            item.apply_color(self.rules, rule)

    def refresh(self):
        if self.work_dir:
            self._start_scan()
