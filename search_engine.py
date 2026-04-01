"""
search_engine.py — 搜尋與取代邏輯
"""
import re
from typing import List, Dict, Tuple

from models import Rule, MatchInfo, ChangeRecord


def _build_line_index(text: str) -> List[int]:
    """回傳每行起始字元位置的清單（0-based）。"""
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _pos_to_line(pos: int, line_starts: List[int]) -> int:
    """二分搜尋找出 pos 對應的行號（1-based）。"""
    lo, hi = 0, len(line_starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if line_starts[mid] <= pos:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1


class SearchEngine:
    def __init__(self, case_sensitive: bool = True):
        self.case_sensitive = case_sensitive

    # ------------------------------------------------------------------
    # 尋找比對
    # ------------------------------------------------------------------

    def find_matches_in_text(
        self, text: str, rules: List[Rule]
    ) -> Dict[str, List[MatchInfo]]:
        """回傳 {rule_id: [MatchInfo]} 的比對結果。"""
        results: Dict[str, List[MatchInfo]] = {}
        for rule in rules:
            if not rule.enabled:
                continue
            pattern = rule.get_compiled_pattern(self.case_sensitive)
            if not pattern:
                continue
            matches = [
                MatchInfo(
                    start=m.start(),
                    end=m.end(),
                    original=m.group(0),
                    rule_id=rule.id,
                )
                for m in pattern.finditer(text)
            ]
            if matches:
                results[rule.id] = matches
        return results

    # ------------------------------------------------------------------
    # 套用取代
    # ------------------------------------------------------------------

    def apply_rule_to_text(
        self, text: str, rule: Rule
    ) -> Tuple[str, int, List[ChangeRecord]]:
        """對文字套用單條規則。回傳 (新文字, 取代次數, 變更記錄)。"""
        pattern = rule.get_compiled_pattern(self.case_sensitive)
        if not pattern:
            return text, 0, []

        replacement = rule.get_replacement_str()
        line_starts = _build_line_index(text)
        changes: List[ChangeRecord] = []

        for m in pattern.finditer(text):
            try:
                rep = pattern.sub(replacement, m.group(0), count=1)
            except re.error:
                rep = replacement
            line_num = _pos_to_line(m.start(), line_starts)
            changes.append(
                ChangeRecord(
                    file_path="",
                    line_number=line_num,
                    original=m.group(0),
                    replacement=rep,
                    rule_id=rule.id,
                )
            )

        if not changes:
            return text, 0, []

        try:
            new_text = pattern.sub(replacement, text)
        except re.error:
            return text, 0, []

        return new_text, len(changes), changes

    def apply_rules_to_text(
        self, text: str, rules: List[Rule]
    ) -> Tuple[str, int, List[ChangeRecord]]:
        """依序套用多條規則。回傳 (新文字, 總取代次數, 所有變更記錄)。"""
        current = text
        total = 0
        all_changes: List[ChangeRecord] = []
        for rule in rules:
            if not rule.enabled:
                continue
            current, count, changes = self.apply_rule_to_text(current, rule)
            total += count
            all_changes.extend(changes)
        return current, total, all_changes

    # ------------------------------------------------------------------
    # 差異預覽 HTML
    # ------------------------------------------------------------------

    def generate_diff_html(self, text: str, rules: List[Rule]) -> str:
        """產生 HTML，以紅色刪除線顯示原文、綠色底線顯示取代結果。"""
        events: List[Tuple[int, int, str, str]] = []  # (start, end, orig, repl)

        for rule in rules:
            if not rule.enabled:
                continue
            pattern = rule.get_compiled_pattern(self.case_sensitive)
            if not pattern:
                continue
            repl_str = rule.get_replacement_str()
            for m in pattern.finditer(text):
                try:
                    rep = pattern.sub(repl_str, m.group(0), count=1)
                except re.error:
                    rep = repl_str
                events.append((m.start(), m.end(), m.group(0), rep))

        if not events:
            return _escape_html(text)

        events.sort(key=lambda x: x[0])

        parts: List[str] = []
        pos = 0
        for start, end, original, replacement in events:
            if start < pos:
                continue
            if pos < start:
                parts.append(_escape_html(text[pos:start]))
            parts.append(
                f'<span style="text-decoration:line-through;color:#FF6B6B;'
                f'background:#3D1A1A;">{_escape_html(original)}</span>'
                f'<span style="text-decoration:underline;color:#6BCB77;'
                f'background:#1A3D1A;">{_escape_html(replacement)}</span>'
            )
            pos = end

        if pos < len(text):
            parts.append(_escape_html(text[pos:]))

        return "".join(parts)


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>\n")
            .replace("  ", "&nbsp;&nbsp;")
    )
