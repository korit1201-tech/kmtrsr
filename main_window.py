"""
main_window.py — 主視窗：整合三欄、協調所有操作
"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QStatusBar, QFileDialog, QMessageBox, QMenuBar,
    QMenu,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut, QAction

from models import Rule, ChangeRecord
from search_engine import SearchEngine
from file_manager import read_file, write_file, backup_file
from config_manager import Config, load_config, save_config
from left_panel import LeftPanel
from middle_panel import MiddlePanel
from right_panel import RightPanel


# ──────────────────────────────────────────────
# Undo 堆疊單元
# ──────────────────────────────────────────────

@dataclass
class _UndoEntry:
    description: str
    backups: List[Tuple[str, str]] = field(default_factory=list)
    # [(original_path, backup_path), ...]


# ──────────────────────────────────────────────
# 主視窗
# ──────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.rules: List[Rule] = []
        self.focused_rule: Optional[Rule] = None
        self.undo_stack: List[_UndoEntry] = []
        self.change_log: List[ChangeRecord] = []
        self.enc_cache: dict[str, str] = {}   # path -> detected encoding

        self._engine = SearchEngine(self.config.case_sensitive)

        self._build_ui()
        self._build_menu()
        self._setup_shortcuts()
        self._restore_geometry()

        # 還原上次工作目錄
        if self.config.work_dir and os.path.isdir(self.config.work_dir):
            self.middle.set_work_dir(self.config.work_dir)

    # ── 建構 UI ───────────────────────────────

    def _build_ui(self):
        self.setWindowTitle("MTRSR — 多檔案文本規則取代工具")
        self.setMinimumSize(1000, 600)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        self.left   = LeftPanel()
        self.middle = MiddlePanel()
        self.right  = RightPanel()

        self.splitter.addWidget(self.left)
        self.splitter.addWidget(self.middle)
        self.splitter.addWidget(self.right)
        self.splitter.setSizes(self.config.splitter_sizes)

        root.addWidget(self.splitter)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("就緒 — 請選擇工作目錄並新增規則")

        # ── 連接訊號 ──────────────────────────
        self.left.rules_changed.connect(self._on_rules_changed)
        self.left.rule_focused.connect(self._on_rule_focused)
        self.left.apply_rule.connect(self._apply_single_rule)
        self.left.apply_all.connect(self._apply_all_rules)
        self.left.undo_requested.connect(self._undo)
        self.left.save_project.connect(self._save_project)
        self.left.load_project.connect(self._load_project)

        self.middle.file_selected.connect(self._on_file_selected)

        self.right.save_file_requested.connect(self._save_one_file)
        self.right.apply_file_requested.connect(self._apply_to_single_file)

    def _build_menu(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("檔案(&F)")

        act_open = QAction("開啟資料夾(&O)", self)
        act_open.setShortcut(QKeySequence("Ctrl+O"))
        act_open.triggered.connect(self.middle._open_folder)
        file_menu.addAction(act_open)

        file_menu.addSeparator()

        act_save = QAction("全部儲存(&S)", self)
        act_save.setShortcut(QKeySequence("Ctrl+S"))
        act_save.triggered.connect(self._save_all)
        file_menu.addAction(act_save)

        file_menu.addSeparator()

        act_export = QAction("匯出變更記錄(&E)…", self)
        act_export.triggered.connect(self._export_log)
        file_menu.addAction(act_export)

        file_menu.addSeparator()

        act_quit = QAction("結束(&Q)", self)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        edit_menu = mb.addMenu("編輯(&E)")

        act_undo = QAction("復原上一步(&Z)", self)
        act_undo.setShortcut(QKeySequence("Ctrl+Z"))
        act_undo.triggered.connect(self._undo)
        edit_menu.addAction(act_undo)

        view_menu = mb.addMenu("檢視(&V)")

        act_diff = QAction("切換差異預覽(&D)", self)
        act_diff.setShortcut(QKeySequence("Ctrl+D"))
        act_diff.triggered.connect(self.right.toggle_diff)
        view_menu.addAction(act_diff)

        # 大小寫切換
        self.act_case = QAction("區分大小寫", self)
        self.act_case.setCheckable(True)
        self.act_case.setChecked(self.config.case_sensitive)
        self.act_case.toggled.connect(self._on_case_toggled)
        view_menu.addAction(self.act_case)

        # UTF-8 BOM 切換
        self.act_bom = QAction("輸出含 BOM (UTF-8-sig)", self)
        self.act_bom.setCheckable(True)
        self.act_bom.setChecked(self.config.utf8_bom)
        self.act_bom.toggled.connect(self._on_bom_toggled)
        view_menu.addAction(self.act_bom)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("F3"),        self, self.right.navigate_next)
        QShortcut(QKeySequence("Shift+F3"),  self, self.right.navigate_prev)

    def _restore_geometry(self):
        geo = self.config.window_geometry
        if geo and len(geo) == 4:
            self.setGeometry(*geo)
        else:
            self.resize(1440, 860)

    # ── 設定切換 ──────────────────────────────

    def _on_case_toggled(self, on: bool):
        self.config.case_sensitive = on
        self._engine = SearchEngine(on)
        self.middle.set_rules(self.rules, on)
        self.right.set_rules(self.rules, on)

    def _on_bom_toggled(self, on: bool):
        self.config.utf8_bom = on

    # ── 規則變更 ──────────────────────────────

    def _on_rules_changed(self, rules: list):
        self.rules = rules
        self._engine = SearchEngine(self.config.case_sensitive)
        self.middle.set_rules(rules, self.config.case_sensitive)
        self.right.set_rules(rules, self.config.case_sensitive)
        self.left.set_undo_available(bool(self.undo_stack))

    def _on_rule_focused(self, rule: Optional[Rule]):
        self.focused_rule = rule
        self.middle.set_focused(rule)
        self.right.set_focused_rule(rule)

    # ── 檔案選取 ──────────────────────────────

    def _on_file_selected(self, path: str):
        enc = self.enc_cache.get(path, "utf-8")
        self.right.load_file(path, enc)
        self.status.showMessage(f"已開啟：{path}")

    # ── 套用規則 ──────────────────────────────

    def _apply_single_rule(self, rule_id: str):
        rule = next((r for r in self.rules if r.id == rule_id), None)
        if rule:
            self._do_apply([rule])

    def _apply_all_rules(self):
        active = [r for r in self.rules if r.enabled]
        if not active:
            QMessageBox.information(self, "提示", "沒有啟用的規則。")
            return
        self._do_apply(active)

    def _apply_to_single_file(self, path: str):
        """差異預覽確認後，只對當前檔案套用所有規則。"""
        active = [r for r in self.rules if r.enabled]
        if not active:
            return
        self._do_apply(active, only_paths={path})

    def _do_apply(self, rules: list, only_paths: Optional[set] = None):
        if not self.middle.work_dir:
            QMessageBox.warning(self, "警告", "請先選擇工作目錄。")
            return

        # 找出需要處理的檔案
        rule_ids = {r.id for r in rules}
        candidates = []
        for path, item in self.middle.items.items():
            if only_paths and path not in only_paths:
                continue
            counts = item.info.get("match_counts", {})
            if any(rid in counts for rid in rule_ids):
                candidates.append(path)

        if not candidates:
            QMessageBox.information(self, "提示", "沒有找到符合的檔案。")
            return

        reply = QMessageBox.question(
            self, "確認套用",
            f"即將對 {len(candidates)} 個檔案執行取代，是否繼續？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        entry = _UndoEntry(f"套用 {len(rules)} 條規則")
        total_changes = 0
        modified = 0

        for path in candidates:
            try:
                enc = self.enc_cache.get(path, "utf-8")
                text, actual_enc = read_file(path, enc)
                self.enc_cache[path] = actual_enc

                new_text, count, changes = self._engine.apply_rules_to_text(text, rules)

                if count > 0 and new_text != text:
                    bak = backup_file(path)
                    entry.backups.append((path, bak))
                    write_file(path, new_text, self.config.utf8_bom)

                    for ch in changes:
                        ch.file_path = path
                    self.change_log.extend(changes)

                    total_changes += count
                    modified += 1
                    self.enc_cache[path] = "utf-8"

            except Exception as e:
                self.status.showMessage(f"錯誤（{os.path.basename(path)}）：{e}")

        if entry.backups:
            self.undo_stack.append(entry)
            self.left.set_undo_available(True)

        self.middle.refresh()

        # 若當前開啟的檔案被修改，重新載入
        cur = self.right.current_file
        if cur and cur in candidates:
            self.right.load_file(cur, self.enc_cache.get(cur, "utf-8"))

        msg = (
            f"已套用 {len(rules)} 條規則，"
            f"共修改 {modified} 個檔案，執行了 {total_changes} 處取代。"
        )
        self.status.showMessage(msg)
        QMessageBox.information(self, "完成", msg)

    # ── 復原 ──────────────────────────────────

    def _undo(self):
        if not self.undo_stack:
            self.status.showMessage("沒有可復原的操作。")
            return

        entry = self.undo_stack.pop()
        restored = 0

        for orig, bak in entry.backups:
            try:
                if os.path.exists(bak):
                    text, enc = read_file(bak)
                    write_file(orig, text, False)   # 原樣還原，不加 BOM
                    restored += 1
                    self.enc_cache.pop(orig, None)
            except Exception as e:
                self.status.showMessage(f"復原失敗（{os.path.basename(orig)}）：{e}")

        self.left.set_undo_available(bool(self.undo_stack))
        self.middle.refresh()

        cur = self.right.current_file
        if cur:
            self.right.load_file(cur, self.enc_cache.get(cur, "utf-8"))

        self.status.showMessage(
            f"已還原 {restored} 個檔案（{entry.description}）"
        )

    # ── 儲存 ──────────────────────────────────

    def _save_one_file(self, path: str, content: str):
        try:
            backup_file(path)
            write_file(path, content, self.config.utf8_bom)
            self.status.showMessage(f"已儲存：{path}")
        except Exception as e:
            QMessageBox.warning(self, "錯誤", f"儲存失敗：{e}")

    def _save_all(self):
        if self.right.edit_mode and self.right.current_file:
            self.right.save_current()

    # ── 專案 ──────────────────────────────────

    def _save_project(self):
        fp, _ = QFileDialog.getSaveFileName(
            self, "儲存專案", self.config.last_project or "",
            "MTRSR 專案 (*.json)"
        )
        if not fp:
            return
        if not fp.endswith(".json"):
            fp += ".json"

        data = {
            "project_name": os.path.splitext(os.path.basename(fp))[0],
            "rules": [r.to_dict() for r in self.rules],
        }
        try:
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.config.last_project = fp
            self.status.showMessage(f"專案已儲存：{fp}")
        except Exception as e:
            QMessageBox.warning(self, "錯誤", f"儲存失敗：{e}")

    def _load_project(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "載入專案", self.config.last_project or "",
            "MTRSR 專案 (*.json)"
        )
        if not fp:
            return
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            rules = [Rule.from_dict(rd) for rd in data.get("rules", [])]
            self.left.set_rules(rules)
            self.config.last_project = fp
            self.status.showMessage(
                f"專案已載入：{os.path.basename(fp)}，共 {len(rules)} 條規則"
            )
        except Exception as e:
            QMessageBox.warning(self, "錯誤", f"載入失敗：{e}")

    # ── 匯出記錄 ──────────────────────────────

    def _export_log(self):
        if not self.change_log:
            QMessageBox.information(self, "提示", "沒有變更記錄可匯出。")
            return

        fp, sel = QFileDialog.getSaveFileName(
            self, "匯出變更記錄", "",
            "CSV 檔案 (*.csv);;文字檔案 (*.txt)"
        )
        if not fp:
            return

        try:
            if "csv" in sel.lower() or fp.endswith(".csv"):
                with open(fp, "w", encoding="utf-8-sig", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(["檔案", "行號", "取代前", "取代後", "規則ID"])
                    for r in self.change_log:
                        w.writerow([r.file_path, r.line_number,
                                    r.original, r.replacement, r.rule_id])
            else:
                with open(fp, "w", encoding="utf-8") as f:
                    for r in self.change_log:
                        f.write(f"檔案：{r.file_path}\n")
                        f.write(f"行號：{r.line_number}\n")
                        f.write(f"取代前：{r.original}\n")
                        f.write(f"取代後：{r.replacement}\n")
                        f.write("-" * 50 + "\n")
            self.status.showMessage(f"變更記錄已匯出：{fp}")
        except Exception as e:
            QMessageBox.warning(self, "錯誤", f"匯出失敗：{e}")

    # ── 視窗關閉 ──────────────────────────────

    def closeEvent(self, event):
        geo = self.geometry()
        self.config.window_geometry = [geo.x(), geo.y(), geo.width(), geo.height()]
        self.config.splitter_sizes = self.splitter.sizes()
        if self.middle.work_dir:
            self.config.work_dir = self.middle.work_dir
        save_config(self.config)
        event.accept()
