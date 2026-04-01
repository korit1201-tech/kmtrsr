# KMTRSR — 多檔案文本規則取代工具

> **K**orit's **M**ulti-file **T**ext **R**ule **S**earch & **R**eplace

以 Python + PyQt6 打造的桌面工具，專為需要對大量文字檔案執行批次規則取代的場景設計，
例如：翻譯校對、術語統一、程式碼重構、文件批次更新。

---

## 功能特色

### 🗂 三欄式可調整介面
- 左欄：規則管理 ／ 中欄：檔案清單 ／ 右欄：預覽 ＆ 編輯
- 三欄寬度可自由拖曳，關閉後自動還原上次比例

### 📐 強大的規則引擎
| 功能 | 說明 |
|------|------|
| 多關鍵字 | 搜尋欄以逗號分隔多個詞彙，自動編譯為單一 regex pattern |
| 正則模式 `[RE]` | 直接輸入正則表示式，如 `第(\d+)章` |
| 全字比對 `[W]` | 加入 `\b` 邊界，避免「大利」誤觸「義大利」 |
| 捕獲群組 | 取代欄支援 `$1`、`$2`，例：`第(\d+)章` → `Chapter $1` |
| 大小寫切換 | 選單可全域切換區分 / 不區分大小寫 |
| 規則顏色 | 自動分配 10 種視覺明顯色，貫穿整個介面 |

### 📁 檔案清單
- 選擇工作目錄後，**背景執行緒**掃描，UI 不凍結
- 副檔名多選過濾（`.txt .md .csv .html .xml .json …`）
- 自動偵測編碼（chardet），顯示檔名、大小、時間、命中數
- 以規則顏色染色命中檔案；多規則命中時以小色標並列顯示

### 🔍 預覽 ＆ 編輯
- 行號顯示、規則顏色語法高亮
- 比對導覽：上一個 ／ 下一個，計數器顯示「第 3 筆 / 共 11 筆」
- **差異預覽（Diff View）**：紅色刪除線顯示原文、綠色底線顯示取代後，確認後再寫入
- 切換編輯模式，直接在 UI 內修改並存檔

### 💾 安全機制
- 執行取代前自動建立備份 `.bak1`、`.bak2` … 永不覆蓋舊備份
- 完整 **Undo 堆疊**，一鍵從備份還原
- 寫入統一輸出 UTF-8（可選含 BOM）

### 📦 專案管理
- 規則存成人類可讀的 `.json` 專案檔，可跨機器共用
- 批次匯入規則（`.txt`，格式：`搜尋詞|取代詞|RE`）
- 操作完成後可匯出**變更記錄**（CSV 或 TXT），含檔名、行號、取代前後內容

---

## 安裝

```bash
# 1. 安裝相依套件
pip install PyQt6 chardet

# 2. 執行
python main.py
```

**系統需求：** Python 3.11+、Windows / macOS / Linux

---

## 鍵盤快捷鍵

| 快捷鍵 | 功能 |
|--------|------|
| `Ctrl+O` | 開啟工作目錄 |
| `Ctrl+S` | 全部儲存 |
| `Ctrl+Z` | 復原上一步 |
| `Ctrl+D` | 切換差異預覽 |
| `F3` | 下一個比對 |
| `Shift+F3` | 上一個比對 |

---

## 專案結構

```
kmtrsr/
├── main.py            # 進入點，深色主題樣式表
├── main_window.py     # 主視窗，整合三欄與所有操作
├── left_panel.py      # 左欄：規則管理區
├── middle_panel.py    # 中欄：檔案清單區
├── right_panel.py     # 右欄：預覽 / 編輯 / Diff 視圖
├── models.py          # 資料模型（Rule、MatchInfo、ChangeRecord）
├── search_engine.py   # 搜尋引擎與 Diff HTML 產生
├── file_manager.py    # 檔案 I/O、編碼偵測、備份、背景掃描執行緒
├── config_manager.py  # 設定檔讀寫（~/.mtrsr_config.json）
├── requirements.txt
├── CHANGELOG.md
└── README.md
```

---

## 專案檔格式（.json）

```json
{
  "project_name": "我的翻譯規則",
  "rules": [
    {
      "id": "uuid",
      "color": "#E74C3C",
      "search_terms": ["達利", "大利", "達莉"],
      "replace_with": "達麗",
      "enabled": true,
      "regex_mode": false,
      "word_boundary": false
    }
  ]
}
```

---

## 批次匯入格式（.txt）

每行一條規則，欄位以 `|` 分隔：

```
達利,大利,達莉|達麗|0
第(\d+)章|Chapter $1|1
```

第三欄：`1` = 啟用正則，`0` = 一般字串比對。

---

## License

MIT
