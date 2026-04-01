# Changelog

本專案的所有重要變更都記錄於此。
格式參考 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.0.0/)。

---

## [1.0.0] — 2026-04-01

### Added
- 三欄式可調整介面（左：規則管理 ／ 中：檔案清單 ／ 右：預覽編輯）
- 規則引擎：多關鍵字（逗號分隔）、正則模式 `[RE]`、全字比對 `[W]`、捕獲群組 `$1 $2`
- 背景執行緒檔案掃描，chardet 自動編碼偵測
- 備份機制（`.bak1` `.bak2` … 永不覆蓋）與 Undo 堆疊
- 差異預覽（Diff View）：刪除線紅色 + 底線綠色，確認後套用
- 行號顯示、規則顏色語法高亮、比對導覽（F3 / Shift+F3）
- 專案存取（`.json`）、批次匯入（`.txt`）、變更記錄匯出（CSV / TXT）
- 鍵盤快捷鍵：Ctrl+O / S / Z / D，F3 / Shift+F3
- VS Code 深色主題，全繁體中文介面
- 設定持久化：視窗大小、欄寬、工作目錄、大小寫、BOM 偏好

---

<!-- 以下由 hook 自動追加 -->
## [auto] — 2026-04-01 15:19

### Changed
- `middle_panel.py`

## [auto] — 2026-04-01 15:08

### Changed
- `middle_panel.py`

## [auto] — 2026-04-01 15:01

### Changed
- `left_panel.py`
- `middle_panel.py`

## [auto] — 2026-04-01 14:44

### Changed
- `README.md`

