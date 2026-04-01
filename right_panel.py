"""
right_panel.py — 右欄：檔案預覽 / 編輯 / 差異預覽
"""
from __future__ import annotations

import os
from typing import List, Optional, Tuple

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QPlainTextEdit, QTextEdit, QStackedWidget, QFrame, QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt, QRect, QSize
from PyQt6.QtGui import (
    QColor, QPainter, QTextCharFormat, QFont,
    QSyntaxHighlighter, QTextDocument, QTextCursor,
)

from models import Rule
from search_engine import SearchEngine


# ──────────────────────────────────────────────
# 行號邊欄
# ──────────────────────────────────────────────

class _LineNumberArea(QWidget):
    def __init__(self, editor: _CodeEditor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self.editor.line_number_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_line_numbers(event)


class _CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._ln_area = _LineNumberArea(self)
        self.blockCountChanged.connect(self._update_margin)
        self.updateRequest.connect(self._scroll_ln)
        self._update_margin(0)

        font = QFont("Consolas", 11)
        font.setFixedPitch(True)
        self.setFont(font)
        self.setReadOnly(True)

    def line_number_width(self) -> int:
        digits = max(1, len(str(self.blockCount())))
        return 10 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_margin(self, _=None):
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def _scroll_ln(self, rect, dy):
        if dy:
            self._ln_area.scroll(0, dy)
        else:
            self._ln_area.update(0, rect.y(), self._ln_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_margin()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._ln_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_width(), cr.height())
        )

    def paint_line_numbers(self, event):
        p = QPainter(self._ln_area)
        p.fillRect(event.rect(), QColor(37, 37, 38))

        block = self.firstVisibleBlock()
        bn = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                p.setPen(QColor(100, 100, 100))
                p.drawText(
                    0, top,
                    self._ln_area.width() - 3,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    str(bn + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            bn += 1


# ──────────────────────────────────────────────
# 語法高亮（以規則顏色染色）
# ──────────────────────────────────────────────

class RuleHighlighter(QSyntaxHighlighter):
    def __init__(self, doc: QTextDocument, rules: List[Rule], cs: bool = True):
        super().__init__(doc)
        self.rules = rules
        self.cs = cs
        self._fmts: dict = {}
        self._rebuild()

    def _rebuild(self):
        self._fmts = {}
        for rule in self.rules:
            if not rule.enabled:
                continue
            fmt = QTextCharFormat()
            bg = QColor(rule.color)
            bg.setAlpha(110)
            fmt.setBackground(bg)
            fmt.setForeground(QColor(255, 255, 255))
            self._fmts[rule.id] = fmt

    def highlightBlock(self, text: str):
        for rule in self.rules:
            if not rule.enabled:
                continue
            fmt = self._fmts.get(rule.id)
            if not fmt:
                continue
            pat = rule.get_compiled_pattern(self.cs)
            if not pat:
                continue
            for m in pat.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)

    def update_rules(self, rules: List[Rule], cs: bool = True):
        self.rules = rules
        self.cs = cs
        self._rebuild()
        self.rehighlight()


# ──────────────────────────────────────────────
# 右欄整體
# ──────────────────────────────────────────────

class RightPanel(QWidget):
    save_file_requested  = pyqtSignal(str, str)   # (path, content)
    apply_file_requested = pyqtSignal(str)         # path（差異確認後套用）

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_file: Optional[str] = None
        self.current_text: str = ""
        self.rules: List[Rule] = []
        self.focused_rule: Optional[Rule] = None
        self.case_sensitive: bool = True
        self.edit_mode: bool = False
        self.diff_mode: bool = False
        self._matches: List[Tuple[int, int]] = []   # (start, end) in document chars
        self._match_idx: int = -1
        self._engine = SearchEngine()
        self._build()

    # ── 建構 UI ───────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # 標題列
        top = QHBoxLayout()
        self.title_lbl = QLabel("檔案預覽 / 編輯")
        self.title_lbl.setStyleSheet("font-size:13px;font-weight:bold;color:#CCC;")
        top.addWidget(self.title_lbl, 1)

        self.edit_btn = QPushButton("切換編輯")
        self.edit_btn.setCheckable(True)
        self.edit_btn.setToolTip("切換編輯 / 唯讀模式")
        self.edit_btn.toggled.connect(self._toggle_edit)
        top.addWidget(self.edit_btn)

        self.diff_btn = QPushButton("差異預覽")
        self.diff_btn.setCheckable(True)
        self.diff_btn.setToolTip("切換差異預覽模式 (Ctrl+D)")
        self.diff_btn.toggled.connect(self._toggle_diff)
        top.addWidget(self.diff_btn)

        layout.addLayout(top)

        # 工具列（導覽）
        nav = QHBoxLayout()

        self.file_lbl = QLabel("（未選擇檔案）")
        self.file_lbl.setStyleSheet("color:#AAA;font-size:10px;")
        nav.addWidget(self.file_lbl, 1)

        self.prev_btn = QPushButton("◀ 上一個")
        self.prev_btn.setFixedHeight(24)
        self.prev_btn.clicked.connect(self._prev_match)
        nav.addWidget(self.prev_btn)

        self.counter_lbl = QLabel("無比對")
        self.counter_lbl.setStyleSheet("color:#AAA;min-width:80px;font-size:10px;")
        self.counter_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav.addWidget(self.counter_lbl)

        self.next_btn = QPushButton("下一個 ▶")
        self.next_btn.setFixedHeight(24)
        self.next_btn.clicked.connect(self._next_match)
        nav.addWidget(self.next_btn)

        self.enc_lbl = QLabel("")
        self.enc_lbl.setStyleSheet("color:#555;font-size:10px;margin-left:8px;")
        nav.addWidget(self.enc_lbl)

        layout.addLayout(nav)

        # 堆疊頁：編輯器 / 差異預覽
        self.stack = QStackedWidget()

        # 頁 0：程式碼編輯器（含行號）
        self.editor = _CodeEditor()
        self.editor.setStyleSheet("""
            QPlainTextEdit {
                background:#1E1E1E; color:#D4D4D4;
                border:1px solid #3C3C3C;
                selection-background-color:#264F78;
            }
        """)
        self.highlighter = RuleHighlighter(self.editor.document(), [])
        self.stack.addWidget(self.editor)

        # 頁 1：差異預覽
        self.diff_view = QTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setStyleSheet("""
            QTextEdit {
                background:#1E1E1E; color:#D4D4D4;
                border:1px solid #3C3C3C;
                font-family:Consolas,monospace; font-size:11pt;
            }
        """)
        self.stack.addWidget(self.diff_view)

        layout.addWidget(self.stack, 1)

        # 差異預覽操作按鈕（差異模式時才顯示）
        self.diff_bar = QWidget()
        db = QHBoxLayout(self.diff_bar)
        db.setContentsMargins(0, 0, 0, 0)
        self.confirm_btn = QPushButton("✓ 確認套用")
        self.confirm_btn.clicked.connect(self._confirm_apply)
        self.cancel_diff_btn = QPushButton("✕ 取消")
        self.cancel_diff_btn.clicked.connect(lambda: self.diff_btn.setChecked(False))
        db.addWidget(self.confirm_btn)
        db.addWidget(self.cancel_diff_btn)
        self.diff_bar.setVisible(False)
        layout.addWidget(self.diff_bar)

    # ── 載入檔案 ──────────────────────────────

    def load_file(self, path: str, encoding: str = "utf-8"):
        from file_manager import read_file
        try:
            text, actual_enc = read_file(path, encoding)
            self.current_file = path
            self.current_text = text
            self.enc_lbl.setText(actual_enc.upper())
            self.file_lbl.setText(os.path.basename(path))

            # 不觸發高亮，先設定文字
            self.editor.blockSignals(True)
            self.editor.setPlainText(text)
            self.editor.blockSignals(False)

            if self.diff_mode:
                self._refresh_diff()

            self._collect_matches()
            if self._matches:
                self._match_idx = 0
                self._jump_to_match()
        except Exception as e:
            self.file_lbl.setText(f"載入失敗：{e}")

    # ── 規則 / 焦點 ───────────────────────────

    def set_rules(self, rules: List[Rule], case_sensitive: bool = True):
        self.rules = rules
        self.case_sensitive = case_sensitive
        self._engine = SearchEngine(case_sensitive)
        self.highlighter.update_rules(rules, case_sensitive)
        if self.current_file:
            self._collect_matches()
            if self.diff_mode:
                self._refresh_diff()

    def set_focused_rule(self, rule: Optional[Rule]):
        self.focused_rule = rule
        self._collect_matches()
        if self._matches:
            self._match_idx = 0
            self._jump_to_match()

    # ── 比對導覽 ──────────────────────────────

    def _collect_matches(self):
        self._matches = []
        self._match_idx = -1
        text = self.editor.toPlainText()
        if not text:
            self._update_counter()
            return

        target_rules = (
            [self.focused_rule]
            if self.focused_rule
            else [r for r in self.rules if r.enabled]
        )
        for rule in target_rules:
            if not rule:
                continue
            pat = rule.get_compiled_pattern(self.case_sensitive)
            if not pat:
                continue
            for m in pat.finditer(text):
                self._matches.append((m.start(), m.end()))

        self._matches.sort(key=lambda x: x[0])
        if self._matches:
            self._match_idx = 0
        self._update_counter()

    def _update_counter(self):
        total = len(self._matches)
        current = self._match_idx + 1 if total else 0
        self.counter_lbl.setText(
            f"第 {current} 筆 / 共 {total} 筆" if total else "無比對"
        )

    def _jump_to_match(self):
        if not self._matches or self._match_idx < 0:
            return
        start, end = self._matches[self._match_idx]
        cur = self.editor.textCursor()
        cur.setPosition(start)
        cur.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cur)
        self.editor.ensureCursorVisible()
        self._update_counter()

    def _next_match(self):
        if not self._matches:
            return
        self._match_idx = (self._match_idx + 1) % len(self._matches)
        self._jump_to_match()

    def _prev_match(self):
        if not self._matches:
            return
        self._match_idx = (self._match_idx - 1) % len(self._matches)
        self._jump_to_match()

    # ── 模式切換 ──────────────────────────────

    def _toggle_edit(self, on: bool):
        self.edit_mode = on
        self.editor.setReadOnly(not on)
        self.edit_btn.setText("唯讀模式" if on else "切換編輯")

    def _toggle_diff(self, on: bool):
        self.diff_mode = on
        if on:
            self.stack.setCurrentIndex(1)
            self.diff_bar.setVisible(True)
            self._refresh_diff()
        else:
            self.stack.setCurrentIndex(0)
            self.diff_bar.setVisible(False)

    def _refresh_diff(self):
        text = self.current_text or self.editor.toPlainText()
        active = [r for r in self.rules if r.enabled]
        html = self._engine.generate_diff_html(text, active)
        self.diff_view.setHtml(
            f'<html><body style="background:#1E1E1E;color:#D4D4D4;'
            f'font-family:Consolas,monospace;font-size:11pt;white-space:pre-wrap;">'
            f'{html}</body></html>'
        )

    def _confirm_apply(self):
        if self.current_file:
            self.apply_file_requested.emit(self.current_file)
        self.diff_btn.setChecked(False)

    # ── 公開介面 ──────────────────────────────

    def get_content(self) -> str:
        return self.editor.toPlainText()

    def navigate_next(self):
        self._next_match()

    def navigate_prev(self):
        self._prev_match()

    def toggle_diff(self):
        self.diff_btn.setChecked(not self.diff_btn.isChecked())

    def save_current(self):
        if self.current_file and self.edit_mode:
            self.save_file_requested.emit(self.current_file, self.get_content())

    def keyPressEvent(self, event):
        if (
            event.key() == Qt.Key.Key_S
            and event.modifiers() == Qt.KeyboardModifier.ControlModifier
        ):
            self.save_current()
            return
        super().keyPressEvent(event)
