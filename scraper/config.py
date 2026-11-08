"""專案設定：來源網址、請求參數與輸出路徑。"""

from __future__ import annotations

from pathlib import Path

# --- 來源網站 ---------------------------------------------------------------
BASE_URL = "https://taiwanpoliticalzoo.com"
INDEX_URL = f"{BASE_URL}/other-cities/penghu/"
SITE_NAME = "台灣選舉懶人包（taiwanpoliticalzoo.com）"

# 網站 robots.txt 允許一般頁面擷取，僅禁止 /admin、/workspace、/my、/auth、/login。
ROBOTS_URL = f"{BASE_URL}/robots.txt"
TERMS_URL = f"{BASE_URL}/terms"

# 官方查證來源（由來源頁列出的中央選舉委員會登記彙總表）
CEC_REGISTRATION_PDF = (
    "https://web.cec.gov.tw/api/file/370f3bbf-6408-4fdc-b8d8-9b9214913f74.pdf"
)
CEC_BALLOT_PAGE = "https://www.cec.gov.tw/phec/article/65367"

# --- 請求行為 ---------------------------------------------------------------
USER_AGENT = (
    "penghu-magistrate-candidates/1.0 "
    "(public-interest election data archive; contact via GitHub QiuGavintw)"
)
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2.0
# 對來源網站保持禮貌的最低請求間隔（秒）
REQUEST_DELAY_SECONDS = 1.2

# --- 路徑 -------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / ".cache" / "raw"
JSON_PATH = PROJECT_ROOT / "candidates.json"
CSV_PATH = PROJECT_ROOT / "candidates.csv"
PLATFORMS_CSV_PATH = PROJECT_ROOT / "platforms.csv"
SOURCES_MD_PATH = PROJECT_ROOT / "sources.md"

ELECTION_NAME = "2026 澎湖縣長選舉"
COUNTY = "澎湖縣"

# 來源網站未提供、且本專案不自行補寫的欄位
UNPROVIDED_FIELDS = ("education", "experience", "biography")
UNPROVIDED_LABEL = "未提供"
