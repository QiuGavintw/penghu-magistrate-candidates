"""HTTP 擷取層：重試、速率限制、可選的本機快取。

設計原則：
- 只發送 GET，不登入、不繞過任何存取控制。
- 遇到 4xx（429 除外）不重試，避免對來源網站造成無謂負擔。
- 快取僅供重複執行與離線除錯，不寫入公開資料集。
"""

from __future__ import annotations

import time
from pathlib import Path

import requests

from . import config


class FetchError(RuntimeError):
    """表示某個 URL 無法取得；由上層決定是否隔離該筆資料。"""


def _cache_name(url: str) -> str:
    """把 URL 轉成安全、可讀的檔名。"""
    name = url.split("://", 1)[-1]
    for ch in '<>:"/\\|?*#':
        name = name.replace(ch, "_")
    name = name.rstrip("_")
    if not name.endswith(".html"):
        name += ".html"
    return name[:180]


class Fetcher:
    def __init__(
        self,
        cache_dir: Path | None = None,
        delay: float = config.REQUEST_DELAY_SECONDS,
        timeout: int = config.REQUEST_TIMEOUT,
        retries: int = config.MAX_RETRIES,
        session: requests.Session | None = None,
    ) -> None:
        self.cache_dir = cache_dir
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": config.USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            }
        )
        self._last_request_at = 0.0
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    # -- 對外 API ---------------------------------------------------------
    def get(self, url: str, use_cache: bool = False) -> str:
        """取得 HTML 字串。use_cache=True 時優先讀取本機快取。"""
        cache_path = None
        if self.cache_dir is not None:
            cache_path = self.cache_dir / _cache_name(url)

        if use_cache and cache_path is not None and cache_path.exists():
            return cache_path.read_text(encoding="utf-8", errors="replace")

        html = self._download(url)

        if cache_path is not None:
            cache_path.write_text(html, encoding="utf-8")
        return html

    # -- 內部實作 ---------------------------------------------------------
    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request_at = time.monotonic()

    def _download(self, url: str) -> str:
        last_error: Exception | None = None

        for attempt in range(1, self.retries + 1):
            self._throttle()
            try:
                response = self.session.get(url, timeout=self.timeout)
            except requests.RequestException as exc:  # 連線錯誤可重試
                last_error = exc
            else:
                if response.status_code == 200:
                    # 來源頁面宣告 UTF-8；明確解碼避免 requests 誤判 latin-1。
                    return response.content.decode("utf-8", errors="replace")
                if response.status_code == 429 or response.status_code >= 500:
                    last_error = FetchError(f"HTTP {response.status_code}: {url}")
                else:
                    raise FetchError(f"HTTP {response.status_code}: {url}")

            if attempt < self.retries:
                time.sleep(config.RETRY_BACKOFF_SECONDS * attempt)

        raise FetchError(f"取得失敗（重試 {self.retries} 次）：{url}｜{last_error}")
