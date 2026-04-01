"""
file_manager.py — 檔案 I/O、編碼偵測、備份邏輯、背景掃描執行緒
"""
import os
import shutil
from typing import Optional, Tuple

from PyQt6.QtCore import QThread, pyqtSignal

try:
    import chardet
    _HAS_CHARDET = True
except ImportError:
    _HAS_CHARDET = False


# ------------------------------------------------------------------
# 編碼偵測
# ------------------------------------------------------------------

def detect_encoding(filepath: str) -> str:
    """偵測檔案編碼；未安裝 chardet 時回傳 utf-8。"""
    if not _HAS_CHARDET:
        return "utf-8"
    try:
        with open(filepath, "rb") as f:
            raw = f.read(65536)
        result = chardet.detect(raw)
        encoding = (result.get("encoding") or "utf-8").lower()
        # 標準化常見名稱
        if encoding in ("ascii", "utf-8", "utf8"):
            return "utf-8"
        if encoding in ("big5", "big5-hkscs", "big5hkscs"):
            return "big5"
        if encoding in ("gb2312", "gbk", "gb18030"):
            return "gbk"
        return encoding
    except Exception:
        return "utf-8"


# ------------------------------------------------------------------
# 讀寫
# ------------------------------------------------------------------

def read_file(filepath: str, encoding: Optional[str] = None) -> Tuple[str, str]:
    """讀取檔案，回傳 (文字內容, 實際編碼)。未給定 encoding 時自動偵測。"""
    if encoding is None:
        encoding = detect_encoding(filepath)
    try:
        with open(filepath, "r", encoding=encoding, errors="replace") as f:
            return f.read(), encoding
    except Exception:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return f.read(), "utf-8"


def write_file(filepath: str, text: str, bom: bool = False) -> None:
    """將文字寫入檔案，統一輸出為 UTF-8（可選含 BOM）。"""
    enc = "utf-8-sig" if bom else "utf-8"
    with open(filepath, "w", encoding=enc, newline="") as f:
        f.write(text)


# ------------------------------------------------------------------
# 備份
# ------------------------------------------------------------------

def get_next_backup_path(filepath: str) -> str:
    """回傳下一個可用的備份路徑（.bak1、.bak2 … 遞增，絕不覆蓋舊備份）。"""
    n = 1
    while True:
        path = f"{filepath}.bak{n}"
        if not os.path.exists(path):
            return path
        n += 1


def backup_file(filepath: str) -> str:
    """為檔案建立備份，回傳備份路徑。"""
    backup_path = get_next_backup_path(filepath)
    shutil.copy2(filepath, backup_path)
    return backup_path


# ------------------------------------------------------------------
# 格式化工具
# ------------------------------------------------------------------

def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


# ------------------------------------------------------------------
# 背景掃描執行緒
# ------------------------------------------------------------------

class FileScannerThread(QThread):
    file_found = pyqtSignal(dict)     # 每找到一個符合檔案就 emit
    scan_progress = pyqtSignal(str)   # 目前掃描的檔名
    scan_complete = pyqtSignal(int)   # 完成，帶總數
    scan_error = pyqtSignal(str)      # 錯誤訊息

    def __init__(self, work_dir: str, extensions: set, rules: list,
                 case_sensitive: bool, parent=None):
        super().__init__(parent)
        self.work_dir = work_dir
        self.extensions = extensions          # set of lower-case extensions, e.g. {'.txt'}
        self.rules = list(rules)              # snapshot
        self.case_sensitive = case_sensitive
        self._cancelled = False

    def run(self):
        count = 0
        try:
            for root, dirs, files in os.walk(self.work_dir):
                dirs[:] = sorted(d for d in dirs if not d.startswith("."))
                if self._cancelled:
                    break
                for fname in sorted(files):
                    if self._cancelled:
                        break
                    if fname.startswith("."):
                        continue
                    ext = os.path.splitext(fname)[1].lower()
                    if self.extensions and ext not in self.extensions:
                        continue

                    fpath = os.path.join(root, fname)
                    self.scan_progress.emit(fname)

                    try:
                        encoding = detect_encoding(fpath)
                        text, actual_enc = read_file(fpath, encoding)
                        size = os.path.getsize(fpath)
                        mtime = os.path.getmtime(fpath)

                        match_counts: dict = {}
                        for rule in self.rules:
                            if not rule.enabled:
                                continue
                            pattern = rule.get_compiled_pattern(self.case_sensitive)
                            if not pattern:
                                continue
                            hits = pattern.findall(text)
                            if hits:
                                match_counts[rule.id] = len(hits)

                        self.file_found.emit({
                            "path": fpath,
                            "name": fname,
                            "size": size,
                            "mtime": mtime,
                            "encoding": actual_enc,
                            "match_counts": match_counts,
                        })
                        count += 1
                    except Exception as e:
                        self.scan_error.emit(f"無法讀取 {fname}：{e}")
        except Exception as e:
            self.scan_error.emit(f"掃描錯誤：{e}")
        self.scan_complete.emit(count)

    def cancel(self):
        self._cancelled = True
