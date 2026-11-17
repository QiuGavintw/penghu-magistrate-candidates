"""新聞來源爬蟲模組。

從主要台灣媒體直接擷取澎湖縣長選舉相關報導，
作為次要來源（選舉公報 > 官方 FB > 媒體報導 > 台灣選舉懶人包）。

來源：
  - 自由時報政治版（ltn.com.tw）
  - 中央社政治（cna.com.tw）
  - 聯合新聞網政治（udn.com）
  - NOWnews 政治（nownews.com）
  - 新頭條政治（newtalk.tw）
  - 讀點 ReadMore（moredetailnews.com）

以頁面 HTML 爬取 + 澎湖關鍵字過濾方式擷取，不需 API key。

用法：
  python -m fetch_news
  python -m fetch_news --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

TZ_TAIPEI = timezone(timedelta(hours=8))

# --- 候選人姓名 -------------------------------------------------------------
CANDIDATE_NAMES = [
    "許智富", "周倪安", "葉竹林", "吳淑瑾", "陳振中", "陳盡川",
]

# --- 媒體清單 ---------------------------------------------------------------
MEDIA_SOURCES = [
    {
        "name": "自由時報",
        "domain": "ltn.com.tw",
        "politics_url": "https://news.ltn.com.tw/list/breakingnews/politics",
    },
    {
        "name": "中央社",
        "domain": "cna.com.tw",
        "politics_url": "https://www.cna.com.tw/news/pol/asp",
    },
    {
        "name": "聯合新聞網",
        "domain": "udn.com",
        "politics_url": "https://udn.com/news/jsp/16707.jsp?from=home_news_titlelist",
    },
    {
        "name": "NOWnews",
        "domain": "nownews.com",
        "politics_url": "https://www.nownews.com/channel/4",
    },
    {
        "name": "新頭條",
        "domain": "newtalk.tw",
        "politics_url": "https://newtalk.tw/channel/politics",
    },
    {
        "name": "讀點 ReadMore",
        "domain": "moredetailnews.com",
        "politics_url": "https://www.moredetailnews.com/%e6%96%b0%e8%81%9e/%e6%94%bf%e6%b2%bb/",
    },
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
REQUEST_TIMEOUT = 20


def _extract_articles(
    html: str,
    source_name: str,
    domain: str,
) -> list[dict[str, Any]]:
    """從媒體頁面 HTML 提取澎湖相關文章。"""
    soup = BeautifulSoup(html, "html.parser")
    articles: list[dict[str, Any]] = []

    # 一般模式：<a> 含澎湖 + 標題
    for a in soup.select("a"):
        text = a.get_text(strip=True)
        href = a.get("href", "")

        # 必須含澎湖，且有標題（不短於 8 字）
        if "澎湖" not in text and "澎湖" not in href:
            continue
        if len(text) < 8:
            continue

        # 正規化 URL
        if href.startswith("/"):
            href = f"https://{domain}{href}"
        if not href.startswith("http"):
            continue

        # 排除非文章連結
        if any(x in href for x in ["javascript:", "#", ".css", ".js"]):
            continue

        matched = [n for n in CANDIDATE_NAMES if n in text]
        articles.append(
            {
                "source": source_name,
                "title": text[:100],
                "url": href,
                "candidates": matched,
                "is_relevant": bool(matched) or "澎湖" in text,
            }
        )

    # 去重
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for a in articles:
        if a["url"] not in seen:
            seen.add(a["url"])
            unique.append(a)
    return unique


def fetch_all() -> dict[str, Any]:
    """擷取所有媒體來源，回傳結構化結果。"""
    all_articles: list[dict[str, Any]] = []
    errors: list[str] = []

    for source in MEDIA_SOURCES:
        name = source["name"]
        url = source["politics_url"]
        print(f"   擷取 {name}...")

        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code != 200:
                print(f"     HTTP {resp.status_code}，跳過")
                errors.append(f"{name}: HTTP {resp.status_code}")
                continue

            articles = _extract_articles(resp.text, name, source["domain"])
            relevant = [a for a in articles if a.get("candidates")]
            all_articles.extend(relevant)
            print(f"     取得 {len(relevant)} 篇澎湖候選人相關報導")

        except requests.RequestException as exc:
            print(f"     擷取失敗：{exc}")
            errors.append(f"{name}: {exc}")

        time.sleep(2)  # 禮貌性延遲

    fb_count = sum(1 for a in all_articles if "facebook.com" in a["url"])
    return {
        "fetched_at": datetime.now(TZ_TAIPEI).isoformat(timespec="seconds"),
        "total": len(all_articles),
        "facebook_count": fb_count,
        "news_count": len(all_articles) - fb_count,
        "candidate_matched": len(all_articles),
        "articles": all_articles,
        "errors": errors,
    }


def write_cache(data: dict[str, Any], cache_dir: Path) -> None:
    """寫入 .cache/news/ 目錄。"""
    news_dir = cache_dir / "news"
    news_dir.mkdir(parents=True, exist_ok=True)
    path = news_dir / "latest.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="擷取澎湖縣長選舉相關媒體報導")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    from scraper import config
    cache_dir = config.CACHE_DIR

    print(f"=== 媒體新聞擷取 {datetime.now(TZ_TAIPEI).isoformat()} ===")
    data = fetch_all()

    if args.dry_run:
        print(f"\n   共 {data['total']} 篇（FB {data['facebook_count']}、媒體 {data['news_count']}）")
        for a in data["articles"][:10]:
            candidates = "、".join(a.get("candidates", [])) or "未匹配"
            print(f"  [{a['source']}] {a['title'][:50]} ({candidates})")
        print("[dry-run] 未寫入快取。")
        return 0

    if data["articles"]:
        write_cache(data, cache_dir)
        print(f"\n已寫入 {cache_dir / 'news' / 'latest.json'}（{data['total']} 篇）")
    else:
        print("\n未擷取到任何相關報導。")

    if data.get("errors"):
        print(f"\n錯誤 {len(data['errors'])} 筆：")
        for e in data["errors"]:
            print(f"  {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
