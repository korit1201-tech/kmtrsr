"""
main.py — 程式進入點
執行：python main.py
"""
import sys
import os

# 確保從正確目錄匯入模組
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

# ──────────────────────────────────────────────
# VS Code 深色主題樣式表
# ──────────────────────────────────────────────

DARK_QSS = """
* {
    font-family: "Microsoft JhengHei UI", "Noto Sans CJK TC",
                 "PingFang TC", "Segoe UI", sans-serif;
    font-size: 12px;
}

QMainWindow, QWidget {
    background-color: #1E1E1E;
    color: #D4D4D4;
}

QMenuBar {
    background: #252526;
    color: #CCCCCC;
    border-bottom: 1px solid #3C3C3C;
}
QMenuBar::item:selected { background: #094771; }

QMenu {
    background: #252526;
    color: #CCCCCC;
    border: 1px solid #454545;
}
QMenu::item:selected { background: #094771; }
QMenu::separator { height: 1px; background: #3C3C3C; margin: 3px 0; }

QPushButton {
    background-color: #3C3C3C;
    color: #CCCCCC;
    border: 1px solid #555555;
    border-radius: 3px;
    padding: 3px 10px;
    min-height: 22px;
}
QPushButton:hover   { background: #505050; border-color: #666; }
QPushButton:pressed { background: #252525; }
QPushButton:checked { background: #094771; border-color: #007ACC; color: #FFF; }
QPushButton:disabled{ background: #2A2A2A; color: #555; border-color: #3A3A3A; }

QLineEdit {
    background: #2D2D2D;
    color: #D4D4D4;
    border: 1px solid #555;
    border-radius: 3px;
    padding: 2px 6px;
    selection-background-color: #264F78;
}
QLineEdit:focus { border-color: #007ACC; }

QCheckBox { color: #D4D4D4; spacing: 5px; }
QCheckBox::indicator {
    width: 13px; height: 13px;
    border: 1px solid #555; border-radius: 2px;
    background: #2D2D2D;
}
QCheckBox::indicator:checked {
    background: #007ACC; border-color: #007ACC;
    image: url(none);
}

QScrollBar:vertical {
    background: #252526; width: 10px; border: none;
}
QScrollBar::handle:vertical {
    background: #424242; border-radius: 4px;
    min-height: 18px; margin: 2px;
}
QScrollBar::handle:vertical:hover { background: #686868; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QScrollBar:horizontal {
    background: #252526; height: 10px; border: none;
}
QScrollBar::handle:horizontal {
    background: #424242; border-radius: 4px;
    min-width: 18px; margin: 2px;
}
QScrollBar::handle:horizontal:hover { background: #686868; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QSplitter::handle { background: #3C3C3C; }
QSplitter::handle:horizontal { width: 3px; }
QSplitter::handle:vertical   { height: 3px; }
QSplitter::handle:hover { background: #007ACC; }

QStatusBar {
    background: #007ACC;
    color: #FFFFFF;
    font-size: 11px;
}

QScrollArea { border: none; background: transparent; }

QFrame[frameShape="4"] { color: #3A3A3A; }

QProgressBar {
    border: none; background: #333;
    border-radius: 2px;
}
QProgressBar::chunk { background: #007ACC; border-radius: 2px; }

QMessageBox        { background: #252526; }
QDialog            { background: #252526; }
QFileDialog        { background: #252526; }

QLabel { color: #D4D4D4; }

QToolTip {
    background: #252526;
    color: #D4D4D4;
    border: 1px solid #454545;
    padding: 3px;
}

QListWidget {
    background: #252526;
    border: 1px solid #3C3C3C;
    outline: none;
}
QListWidget::item {
    padding: 3px 6px;
    border-bottom: 1px solid #2E2E2E;
}
QListWidget::item:selected { background: #094771; }
QListWidget::item:hover    { background: #2A2D2E; }
"""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MTRSR")
    app.setOrganizationName("MTRSR")
    app.setApplicationDisplayName("多檔案文本規則取代工具")
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_QSS)

    from main_window import MainWindow
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
