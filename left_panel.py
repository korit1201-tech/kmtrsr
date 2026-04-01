"""
left_panel.py — 左欄：規則管理區
"""
from __future__ import annotations
import json
import os
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QCheckBox, QScrollArea, QFrame, QFileDialog,
    QMessageBox, QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt, QEvent
from PyQt6.QtGui import QColor

from models import Rule, RULE_COLORS


# ──────────────────────────────────────────────
# 可點擊的輸入框（點擊時發出 clicked 訊號）
# ──────────────────────────────────────────────

class _ClickableLineEdit(QLineEdit):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.clicked.emit()


# ──────────────────────────────────────────────
# 單條規則列
# ──────────────────────────────────────────────

class RuleRow(QWidget):
    rule_changed = pyqtSignal(object)   # Rule
    rule_deleted = pyqtSignal(str)      # rule_id
    rule_applied = pyqtSignal(str)      # rule_id
    rule_focused = pyqtSignal(str)      # rule_id

    def __init__(self, rule: Rule, parent=None):
        super().__init__(parent)
        self.rule = rule
        self._focused = False
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(5)

        # 顏色標籤
        self.color_bar = QLabel()
        self.color_bar.setFixedSize(8, 28)
        self._refresh_color_bar()
        layout.addWidget(self.color_bar)

        # [RE] 正則切換
        self.re_btn = QPushButton("RE")
        self.re_btn.setCheckable(True)
        self.re_btn.setChecked(self.rule.regex_mode)
        self.re_btn.setFixedSize(34, 26)
        self.re_btn.setToolTip("開啟正則表示式模式")
        self.re_btn.toggled.connect(self._on_re)
        layout.addWidget(self.re_btn)

        # [W] 全字比對
        self.w_btn = QPushButton("W")
        self.w_btn.setCheckable(True)
        self.w_btn.setChecked(self.rule.word_boundary)
        self.w_btn.setFixedSize(26, 26)
        self.w_btn.setToolTip("全字比對（\\b 邊界）")
        self.w_btn.toggled.connect(self._on_w)
        layout.addWidget(self.w_btn)

        # 搜尋詞
        self.search_edit = _ClickableLineEdit()
        self.search_edit.setPlaceholderText("搜尋詞（逗號分隔）")
        self.search_edit.setText(",".join(self.rule.search_terms))
        self.search_edit.setMinimumWidth(90)
        self.search_edit.textChanged.connect(self._on_search)
        self.search_edit.clicked.connect(lambda: self.rule_focused.emit(self.rule.id))
        layout.addWidget(self.search_edit, 3)

        # 箭頭
        arrow = QLabel("→")
        arrow.setStyleSheet("color:#777;font-size:13px;")
        layout.addWidget(arrow)

        # 取代為
        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("取代為（$1 $2…）")
        self.replace_edit.setText(self.rule.replace_with)
        self.replace_edit.setMinimumWidth(70)
        self.replace_edit.textChanged.connect(self._on_replace)
        layout.addWidget(self.replace_edit, 2)

        # 啟用開關
        self.enable_cb = QCheckBox()
        self.enable_cb.setChecked(self.rule.enabled)
        self.enable_cb.setToolTip("啟用／停用此規則")
        self.enable_cb.toggled.connect(self._on_enable)
        layout.addWidget(self.enable_cb)

        # 套用此規則
        apply_btn = QPushButton("套用")
        apply_btn.setFixedWidth(48)
        apply_btn.setToolTip("只套用此規則至全部檔案")
        apply_btn.clicked.connect(lambda: self.rule_applied.emit(self.rule.id))
        layout.addWidget(apply_btn)

        # 刪除
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(26, 26)
        del_btn.setToolTip("刪除此規則")
        del_btn.clicked.connect(lambda: self.rule_deleted.emit(self.rule.id))
        layout.addWidget(del_btn)

        self.setFixedHeight(38)

    def mousePressEvent(self, event):
        """點選規則列任意位置都觸發聚焦。"""
        self.rule_focused.emit(self.rule.id)
        super().mousePressEvent(event)

    # ---------- slots ----------

    def _on_re(self, v):
        self.rule.regex_mode = v
        self.rule_changed.emit(self.rule)

    def _on_w(self, v):
        self.rule.word_boundary = v
        self.rule_changed.emit(self.rule)

    def _on_search(self, text):
        self.rule.search_terms = [t.strip() for t in text.split(",") if t.strip()]
        self.rule_changed.emit(self.rule)

    def _on_replace(self, text):
        self.rule.replace_with = text
        self.rule_changed.emit(self.rule)

    def _on_enable(self, v):
        self.rule.enabled = v
        self.rule_changed.emit(self.rule)

    # ---------- UI helpers ----------

    def _refresh_color_bar(self):
        self.color_bar.setStyleSheet(
            f"background:{self.rule.color};border-radius:2px;"
        )

    def set_focused(self, focused: bool):
        self._focused = focused
        if focused:
            self.setStyleSheet(
                f"RuleRow{{background:{self.rule.color}1A;"
                f"border:1px solid {self.rule.color};}}"
            )
        else:
            self.setStyleSheet("")

    def refresh_from_rule(self, rule: Rule):
        """外部修改 rule 物件後重整 UI（不觸發訊號）。"""
        self.rule = rule
        self._refresh_color_bar()
        with _block(self.re_btn):
            self.re_btn.setChecked(rule.regex_mode)
        with _block(self.w_btn):
            self.w_btn.setChecked(rule.word_boundary)
        with _block(self.search_edit):
            self.search_edit.setText(",".join(rule.search_terms))
        with _block(self.replace_edit):
            self.replace_edit.setText(rule.replace_with)
        with _block(self.enable_cb):
            self.enable_cb.setChecked(rule.enabled)


class _block:
    """簡易 signal-blocker context manager。"""
    def __init__(self, widget):
        self._w = widget

    def __enter__(self):
        self._w.blockSignals(True)

    def __exit__(self, *_):
        self._w.blockSignals(False)


# ──────────────────────────────────────────────
# 左欄整體
# ──────────────────────────────────────────────

class LeftPanel(QWidget):
    rules_changed = pyqtSignal(list)    # list[Rule]
    rule_focused  = pyqtSignal(object)  # Rule | None
    apply_rule    = pyqtSignal(str)     # rule_id
    apply_all     = pyqtSignal()
    undo_requested = pyqtSignal()
    save_project   = pyqtSignal()
    load_project   = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules: list[Rule] = []
        self.rows: dict[str, RuleRow] = {}
        self.focused_id: Optional[str] = None
        self._color_counter = 0
        self._build()

    # ── 建構 UI ───────────────────────────────

    def _build(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(6, 6, 6, 6)
        main.setSpacing(5)

        title = QLabel("規則管理")
        title.setStyleSheet("font-size:13px;font-weight:bold;color:#CCC;")
        main.addWidget(title)

        # 捲動區放置規則列
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.rows_widget = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_widget)
        self.rows_layout.setContentsMargins(2, 2, 2, 2)
        self.rows_layout.setSpacing(2)
        self.rows_layout.addStretch()

        self.scroll.setWidget(self.rows_widget)
        main.addWidget(self.scroll, 1)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#3A3A3A;")
        main.addWidget(sep)

        # 批次勾選控制
        r0 = QHBoxLayout()
        btn_all  = QPushButton("全部啟用")
        btn_none = QPushButton("全部取消")
        btn_inv  = QPushButton("反向勾選")
        for b in (btn_all, btn_none, btn_inv):
            b.setFixedHeight(24)
        btn_all.clicked.connect(self._enable_all)
        btn_none.clicked.connect(self._disable_all)
        btn_inv.clicked.connect(self._invert_all)
        r0.addWidget(btn_all)
        r0.addWidget(btn_none)
        r0.addWidget(btn_inv)
        main.addLayout(r0)

        # 按鈕區
        r1 = QHBoxLayout()
        self.add_btn = QPushButton("＋ 新增規則")
        self.add_btn.clicked.connect(lambda: self.add_rule())
        self.apply_all_btn = QPushButton("▶ 套用所有規則")
        self.apply_all_btn.clicked.connect(self.apply_all.emit)
        r1.addWidget(self.add_btn)
        r1.addWidget(self.apply_all_btn)
        main.addLayout(r1)

        r2 = QHBoxLayout()
        self.undo_btn = QPushButton("⟲ 復原上一步")
        self.undo_btn.setEnabled(False)
        self.undo_btn.clicked.connect(self.undo_requested.emit)
        r2.addWidget(self.undo_btn)
        main.addLayout(r2)

        r3 = QHBoxLayout()
        btn_save = QPushButton("💾 儲存專案")
        btn_save.clicked.connect(self.save_project.emit)
        btn_load = QPushButton("📂 載入專案")
        btn_load.clicked.connect(self.load_project.emit)
        r3.addWidget(btn_save)
        r3.addWidget(btn_load)
        main.addLayout(r3)

        btn_import = QPushButton("批次匯入規則（.txt）")
        btn_import.clicked.connect(self._batch_import)
        main.addWidget(btn_import)

    # ── 規則操作 ──────────────────────────────

    def add_rule(self, rule: Optional[Rule] = None) -> Rule:
        if rule is None:
            ci = self._color_counter % len(RULE_COLORS)
            self._color_counter += 1
            rule = Rule(color_index=ci, color=RULE_COLORS[ci])
        else:
            # 確保顏色計數器不重複
            self._color_counter = max(self._color_counter, rule.color_index + 1)

        self.rules.append(rule)
        row = RuleRow(rule)
        row.rule_changed.connect(self._on_rule_changed)
        row.rule_deleted.connect(self._on_rule_deleted)
        row.rule_applied.connect(self.apply_rule.emit)
        row.rule_focused.connect(self._on_rule_focused)
        self.rows[rule.id] = row

        # 插入 stretch 之前
        self.rows_layout.insertWidget(self.rows_layout.count() - 1, row)
        self.rules_changed.emit(self.rules)
        return rule

    def _on_rule_changed(self, rule: Rule):
        for i, r in enumerate(self.rules):
            if r.id == rule.id:
                self.rules[i] = rule
                break
        self.rules_changed.emit(self.rules)

    def _on_rule_deleted(self, rule_id: str):
        self.rules = [r for r in self.rules if r.id != rule_id]
        if rule_id in self.rows:
            w = self.rows.pop(rule_id)
            w.setParent(None)
            w.deleteLater()
        if self.focused_id == rule_id:
            self.focused_id = None
            self.rule_focused.emit(None)
        self.rules_changed.emit(self.rules)

    def _on_rule_focused(self, rule_id: str):
        for rid, row in self.rows.items():
            row.set_focused(rid == rule_id)
        self.focused_id = rule_id
        rule = next((r for r in self.rules if r.id == rule_id), None)
        self.rule_focused.emit(rule)

    # ── 批次匯入 ──────────────────────────────

    def _batch_import(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "批次匯入規則", "", "文字檔案 (*.txt)"
        )
        if not fp:
            return
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            QMessageBox.warning(self, "錯誤", f"無法讀取檔案：{e}")
            return

        imported = 0
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) < 2:
                continue
            search  = parts[0].strip()
            replace = parts[1].strip()
            regex   = len(parts) > 2 and parts[2].strip() == "1"
            ci = self._color_counter % len(RULE_COLORS)
            self._color_counter += 1
            rule = Rule(
                color_index=ci,
                color=RULE_COLORS[ci],
                search_terms=[search],
                replace_with=replace,
                regex_mode=regex,
            )
            self.add_rule(rule)
            imported += 1

        QMessageBox.information(self, "完成", f"已匯入 {imported} 條規則。")

    # ── 批次勾選 ──────────────────────────────

    def _enable_all(self):
        for row in self.rows.values():
            row.enable_cb.setChecked(True)

    def _disable_all(self):
        for row in self.rows.values():
            row.enable_cb.setChecked(False)

    def _invert_all(self):
        for row in self.rows.values():
            row.enable_cb.setChecked(not row.enable_cb.isChecked())

    # ── 外部介面 ──────────────────────────────

    def set_rules(self, rules: list):
        """從專案載入時替換所有規則。"""
        for w in list(self.rows.values()):
            w.setParent(None)
            w.deleteLater()
        self.rows.clear()
        self.rules.clear()
        self.focused_id = None
        for rule in rules:
            self.add_rule(rule)

    def get_rules(self) -> list:
        return list(self.rules)

    def set_undo_available(self, available: bool):
        self.undo_btn.setEnabled(available)
