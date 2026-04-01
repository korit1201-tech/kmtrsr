"""
config_manager.py — 設定檔讀寫（~/.mtrsr_config.json）
"""
import json
import os
from dataclasses import dataclass, field, asdict

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".mtrsr_config.json")


@dataclass
class Config:
    work_dir: str = ""
    splitter_sizes: list = field(default_factory=lambda: [280, 320, 600])
    case_sensitive: bool = True
    utf8_bom: bool = False
    window_geometry: list = field(default_factory=lambda: [80, 80, 1440, 860])
    extensions: list = field(
        default_factory=lambda: [".txt", ".md", ".csv", ".html", ".xml"]
    )
    last_project: str = ""


def load_config() -> Config:
    if not os.path.exists(CONFIG_PATH):
        return Config()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        cfg = Config()
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg
    except Exception:
        return Config()


def save_config(cfg: Config) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(asdict(cfg), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[config] 儲存失敗：{e}")
