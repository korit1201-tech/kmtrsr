"""
models.py — 資料模型定義
Rule、MatchInfo、ChangeRecord
"""
# v1.0.0
import re
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

# 10 個視覺明顯色，循環分配給規則
RULE_COLORS = [
    "#E74C3C",  # 紅
    "#3498DB",  # 藍
    "#2ECC71",  # 綠
    "#F39C12",  # 橘
    "#9B59B6",  # 紫
    "#1ABC9C",  # 青綠
    "#E67E22",  # 深橘
    "#16A085",  # 深青
    "#E91E63",  # 粉紅
    "#00BCD4",  # 青
]


@dataclass
class Rule:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    color_index: int = 0
    color: str = RULE_COLORS[0]
    search_terms: List[str] = field(default_factory=list)
    replace_with: str = ""
    enabled: bool = True
    regex_mode: bool = False
    word_boundary: bool = False

    def get_compiled_pattern(self, case_sensitive: bool = True) -> Optional[re.Pattern]:
        """編譯搜尋 Pattern；無有效詞彙時回傳 None。"""
        terms = [t.strip() for t in self.search_terms if t.strip()]
        if not terms:
            return None

        flags = 0 if case_sensitive else re.IGNORECASE

        if self.regex_mode:
            # 正則模式：直接組合多個表達式
            pattern = "|".join(terms)
        else:
            # 字串模式：跳脫後組合
            pattern = "|".join(re.escape(t) for t in terms)

        if self.word_boundary:
            pattern = r"\b(?:" + pattern + r")\b"

        try:
            return re.compile(pattern, flags)
        except re.error:
            return None

    def get_replacement_str(self) -> str:
        """將 $1、$2 轉換為 Python re.sub 使用的 \\1、\\2。"""
        return re.sub(r'\$(\d+)', r'\\\1', self.replace_with)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "color_index": self.color_index,
            "color": self.color,
            "search_terms": self.search_terms,
            "replace_with": self.replace_with,
            "enabled": self.enabled,
            "regex_mode": self.regex_mode,
            "word_boundary": self.word_boundary,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Rule":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            color_index=data.get("color_index", 0),
            color=data.get("color", RULE_COLORS[0]),
            search_terms=data.get("search_terms", []),
            replace_with=data.get("replace_with", ""),
            enabled=data.get("enabled", True),
            regex_mode=data.get("regex_mode", False),
            word_boundary=data.get("word_boundary", False),
        )


@dataclass
class MatchInfo:
    start: int
    end: int
    original: str
    rule_id: str


@dataclass
class ChangeRecord:
    file_path: str
    line_number: int
    original: str
    replacement: str
    rule_id: str
