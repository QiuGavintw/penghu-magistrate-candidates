# 2026 澎湖縣長候選人公開資料集

蒐集並整理 2026 年澎湖縣長選舉 6 位登記參選人的公開資料，包含登記號次、黨派、登記日期、政見摘要與可追溯的來源連結。

本專案以**資料正確性、來源可追溯性與可維護性**為優先，不追求擷取速度，也不自行補寫來源沒有的內容。

- 主要來源：[台灣選舉懶人包・澎湖縣](https://taiwanpoliticalzoo.com/other-cities/penghu/)
- 資料擷取日：2026-11-08
- 來源頁標示最後更新：2026-11-02
- 候選人數：6 位
- 已收錄政見：23 項（皆為來源網站的摘要，非完整政見全文）

> **非官方專案。** 本資料集不是中央選舉委員會或任何政黨的官方出版品。選舉事務請以[中央選舉委員會](https://www.cec.gov.tw/)公告為準。

---

## 目錄

- [重要聲明](#重要聲明)
- [資料集摘要](#資料集摘要)
- [資料夾結構](#資料夾結構)
- [資料欄位說明](#資料欄位說明)
- [使用方式](#使用方式)
- [測試與驗收](#測試與驗收)
- [資料品質與已知限制](#資料品質與已知限制)
- [授權與引用](#授權與引用)

---

## 重要聲明

1. **政見不是全文。** 來源網站以「新聞彙整摘要」或「候選人公開自述」標記每項政見，內容多為一至兩句。本專案如實保留，並以 `is_full_platform: false` 明確標記，避免被誤認為候選人完整政見。
2. **缺漏不代表沒有。** 來源網站未提供學歷、經歷、個人介紹，因此 `education`、`experience`、`biography` 一律為 `null`，並列於 `missing_fields`。這不代表候選人沒有相關背景。
3. **區分網站資料與官方登記資料。** 號次、黨派、登記日期是來源網站轉載之中央選舉委員會／澎湖縣選舉委員會資料；本專案保留官方連結，但未重新解析官方 PDF。
4. **不加入未經查證的評價。** 本專案不收錄新聞與爭議、刑事案件、財產申報等未經完整查證的內容，也不做負面描述。
5. **不重製照片與報導全文。** 照片、完整新聞報導及其他素材權利屬原權利人。

## 資料集摘要

| 號次 | 姓名 | 政黨 | 登記日期 | 政見數 | 欄位完整度 |
| --- | --- | --- | --- | --- | --- |
| 1 | 許智富 | 無黨籍 | 2026-09-03 | 4 | 3/6 |
| 2 | 周倪安 | 台聯黨 | 2026-09-03 | 5 | 3/6 |
| 3 | 葉竹林 | 無黨籍 | 2026-09-04 | 3 | 3/6 |
| 4 | 吳淑瑾 | 民主進步黨 | 2026-09-02 | 2 | 3/6 |
| 5 | 陳振中 | 中國國民黨 | 2026-09-03 | 4 | 3/6 |
| 6 | 陳盡川 | 無黨籍 | 2026-09-03 | 5 | 3/6 |

「欄位完整度 3/6」表示在 `number`、`party`、`registration_date`、`education`、`experience`、`biography` 六個欄位中，有 3 個由來源提供。所有 23 項政見皆有內容、原始來源網址、發布日期與查閱日期。

## 資料夾結構

```text
penghu-magistrate-candidates/
├── candidates.json                 # 主要資料集（結構化、含完整來源）
├── candidates.csv                  # 一位候選人一列（UTF-8 with BOM，Excel 可直接開啟）
├── platforms.csv                   # 一項政見一列，方便分析
├── sources.md                      # 逐筆來源與查證紀錄（由程式產生）
├── README.md
├── 澎湖縣長候選人資料整理問題與解決.txt
├── requirements.txt
├── pytest.ini
├── scraper/
│   ├── __main__.py                 # python -m scraper
│   ├── config.py                   # 來源網址、請求參數、路徑
│   ├── fetch.py                    # HTTP 重試、速率限制、快取
│   ├── parse.py                    # HTML 解析（BeautifulSoup）
│   ├── build.py                    # 資料正規化與 JSON/CSV 輸出
│   └── report.py                   # 產生 sources.md
└── tests/
    ├── fixtures/                   # 自製最小 HTML，測試不依賴網路
    ├── test_parse.py               # 解析器單元測試
    ├── test_dataset.py             # 資料集驗收測試
    ├── test_isolation.py           # 單頁失敗不影響其他資料
    └── test_live.py                # 即時來源測試（預設跳過）
```

## 資料欄位說明

### 頂層欄位

| 欄位 | 說明 |
| --- | --- |
| `election` | 選舉名稱 |
| `county` | 縣市 |
| `source` | 主要來源網址 |
| `source_site` | 來源網站名稱 |
| `source_last_modified` | 來源頁 JSON-LD 標示的 `dateModified` |
| `last_updated` | 本資料集資料日期 |
| `scraped_at` | 實際擷取時間（UTC+8） |
| `candidate_count` | 候選人總數 |
| `platform_count` | 政見總數 |
| `data_scope_notes` | 資料範圍與限制說明 |
| `errors` | 擷取錯誤；正常應為空陣列 |
| `candidates` | 候選人陣列 |

### 候選人欄位

| 欄位 | 說明 |
| --- | --- |
| `id` | 來源網站的候選人 UUID |
| `name` | 姓名 |
| `number` | 登記號次（整數） |
| `party` | 登記黨派 |
| `registration_date` | 登記日期（YYYY-MM-DD） |
| `birth_date` | 國曆生日（來源網站標示） |
| `zodiac` | 星座（僅供參考，不作為分析依據） |
| `education` | 學歷；來源未提供時為 `null` |
| `experience` | 經歷；來源未提供時為 `null` |
| `biography` | 個人介紹；來源未提供時為 `null` |
| `missing_fields` | 缺漏欄位清單 |
| `platform_count` | 該候選人政見數 |
| `platforms` | 政見陣列 |
| `sources` | 來源陣列（網站頁面、CEC、選委會） |
| `verified_at` | 官方來源最後查閱日期 |
| `qualification_status` | 來源網站對資格審定的註記（非官方結論） |
| `data_origin` | 各類資料的來源層級說明 |
| `completeness` | 自動計算的完整度統計 |
| `partial` | 個人頁擷取失敗時為 `true` |

### 政見欄位

| 欄位 | 說明 |
| --- | --- |
| `order` | 在來源頁的排序 |
| `id` | 來源網站的政見 UUID |
| `title` | 政見標題 |
| `category` | 來源網站分類 |
| `content` | 來源網站公開的內容（多為摘要） |
| `content_type` | `新聞彙整摘要` 或 `候選人公開自述` |
| `is_full_platform` | 是否為完整政見全文；本資料集全為 `false` |
| `caveats` | 來源網站標示的限制與待確認事項 |
| `source` | 原始新聞／政黨新聞稿的標題、網址、段落、發布與查閱日期 |
| `url` | 來源網站的政見頁網址 |

## 使用方式

### 直接使用資料

- `candidates.json`：UTF-8，適合程式處理。
- `candidates.csv`：UTF-8 with BOM，Excel／Numbers／LibreOffice 可直接開啟。
- `platforms.csv`：以政見為單位，適合篩選與統計。

### 重新擷取

需要 Python 3.11 以上。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 重新擷取並覆寫 candidates.json / CSV / sources.md
python -m scraper

# 使用本機快取（離線除錯）
python -m scraper --use-cache
```

擷取程式會：

1. 讀取澎湖縣總覽頁，取得候選人清單。
2. 逐一讀取候選人頁與政見列表頁。
3. 逐一讀取 23 個政見明細頁。
4. 單一頁面失敗時記錄於 `errors`，不中斷其他候選人。
5. 以 UTF-8 寫出 JSON、CSV 與 `sources.md`。

### 測試

```powershell
python -m pytest                  # 19 項離線測試
$env:RUN_LIVE_TESTS="1"; python -m pytest tests/test_live.py   # 即時來源測試
```

## 測試與驗收

| 驗收項目 | 結果 |
| --- | --- |
| 候選人總數與來源頁一致 | 通過（6 位） |
| 個人頁連結正確 | 通過（6/6 可讀取） |
| 政見資料完整度 | 通過（23/23 有內容與來源） |
| JSON 格式正確 | 通過（`json.load` 可解析） |
| CSV 可正常開啟 | 通過（UTF-8 with BOM，7 列／24 列） |
| 中文 UTF-8 編碼正常 | 通過（無 U+FFFD） |
| 缺漏欄位正確標記 | 通過（`null` + `missing_fields` + CSV「未提供」） |
| 資料來源可追溯 | 通過（每項政見皆有原始網址與日期） |
| 重複執行擷取程式正常 | 通過（`--use-cache` 與即時擷取皆可） |
| 單一候選人失敗不影響其他 | 通過（`tests/test_isolation.py`） |

## 資料品質與已知限制

- **來源單一。** 本資料集以台灣選舉懶人包為主要來源，尚未逐筆比對候選人競選總部、政黨官網或公報原文。
- **政見僅摘要。** 23 項政見都是來源網站的短篇整理，不能當作完整政策白皮書。
- **學經歷從缺。** 來源網站未提供，需人工向候選人辦公室、政黨或選舉公報查證。
- **官方 PDF 未解析。** 中央選舉委員會登記彙總表僅記錄連結與來源頁標示的日期，未重新下載解析。
- **資格狀態未確認。** `qualification_status` 是來源網站的註記，不是本專案的查證結論。
- **網站可能改版。** 若來源 HTML 結構變更，解析器可能需要調整；`tests/test_live.py` 可協助偵測。

## 授權與引用

- **程式碼**：MIT License，見 [`LICENSE`](LICENSE)。
- **資料集**：由本專案整理之事實欄位與結構，以 CC BY 4.0 釋出；引用時請保留本專案名稱、來源網站與日期。
- **來源內容**：政見摘要、新聞標題與其他文字之權利屬原權利人（台灣選舉懶人包、各新聞媒體、政黨）。本專案僅作合理引用並附上原始連結，不主張著作權。
- **照片**：本專案不重製任何候選人照片。

建議引用格式：

```text
QiuGavintw（2026）。2026 澎湖縣長候選人公開資料集。
https://github.com/QiuGavintw/penghu-magistrate-candidates
資料來源：台灣選舉懶人包，https://taiwanpoliticalzoo.com/other-cities/penghu/
```
