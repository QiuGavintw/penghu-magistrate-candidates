"""Facebook 政見擷取模組（無需 FB API token）。

方式：
  1. 已知候選人官方 FB 頁面 URL（hardcoded）
  2. 以這些 URL 為基礎，爬取主流媒體政治版頁面
     找出媒體報導中引用 FB 貼文的段落
  3. 整理出「FB 來源」的政見條目

來源優先順序：
  1. 選舉公報（CEC PDF，手動）
  2. 候選人官方 Facebook（本模組）
  3. 主流媒體報導
  4. 台灣選舉懶人包

不需要 FB_PAGE_TOKEN，不需要 API key。

用法：
  python -m fetch_fb
  python -m fetch_fb --dry-run
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

# --- 候選人官方 FB 頁面（已知 URL）-------------------------------------------
CANDIDATE_FB_PAGES: dict[str, dict[str, str]] = {
    "葉竹林": {
        "page_url": "https://www.facebook.com/YEHCHULINinPENGHU/",
        "known_posts": [
            "https://www.facebook.com/YEHCHULINinPENGHU/posts/1705173708280367/",
            "https://www.facebook.com/YEHCHULINinPENGHU/posts/1667354252062313/",
        ],
        "search_terms": ["葉竹林 澎湖 縣長 政見", "葉竹林 澎湖 消費券"],
    },
    "吳淑瑾": {
        "page_url": "https://www.facebook.com/wushuchin.penghu/",
        "known_posts": [
            "https://www.facebook.com/groups/2504517542962730/permalink/28514330674888061/",
        ],
        "search_terms": ["吳淑瑾 澎湖 縣長 政見", "吳淑瑾 澎湖 醫療 機票"],
    },
    "陳盡川": {
        "page_url": "https://www.facebook.com/chen.jin.chuan.441889/",
        "known_posts": [
            "https://www.facebook.com/chen.jin.chuan.441889/posts/4536071869942401/",
        ],
        "search_terms": ["陳盡川 牛哥 澎湖 海洋 政見", "陳盡川 澎湖 縣長 漁業"],
    },
}

# 媒體政治版頁面（直接爬取，找 FB 連結）
MEDIA_POLITICS_PAGES = [
    ("自由時報", "https://news.ltn.com.tw/list/breakingnews/politics", "ltn.com.tw"),
    ("聯合新聞網", "https://udn.com/news/jsp/16707.jsp", "udn.com"),
    ("讀點 ReadMore", "https://www.moredetailnews.com/%e6%96%b0%e8%81%9e/%e6%94%bf%e6%b2%bb/", "moredetailnews.com"),
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
REQUEST_TIMEOUT = 20

# 政見關鍵詞
POLICY_KEYWORDS = [
    "政見", "政策", "參選", "競選", "澎湖",
    "醫療", "交通", "觀光", "漁業", "垃圾", "環境",
    "青年", "教育", "養老", "托育", "經濟", "消費",
    "禮金", "補貼", "補助", "焚化", "航空", "機票",
    "離島", "軍公教", "振興", "安居", "返鄉",
]


def _has_policy_content(text: str) -> bool:
    """判斷文字是否含政見關鍵詞。"""
    lower = text.lower()
    return any(kw.lower() in lower for kw in POLICY_KEYWORDS)


def _fetch_fb_referenced_from_media() -> dict[str, list[dict[str, Any]]]:
    """爬取媒體政治版頁面，找出引用 FB 貼文的報導。

    回傳 {candidate_name: [article_data]}
    """
    results: dict[str, list[dict[str, Any]]] = {
        name: [] for name in CANDIDATE_FB_PAGES
    }

    for media_name, url, domain in MEDIA_POLITICS_PAGES:
        print(f"   爬取 {media_name} 政治版...")
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code != 200:
                print(f"     HTTP {resp.status_code}，跳過")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # 找所有 FB 連結
            for a in soup.select("a[href*='facebook.com']"):
                href = a.get("href", "")
                text = a.get_text(strip=True)
                if not _has_policy_content(text):
                    continue

                # 判斷是哪位候選人
                matched_candidate = None
                for name, info in CANDIDATE_FB_PAGES.items():
                    if name in text or info["page_url"].split("/")[-2] in href:
                        matched_candidate = name
                        break

                if not matched_candidate:
                    continue

                entry = {
                    "candidate": matched_candidate,
                    "source": "facebook_via_media",
                    "media": media_name,
                    "title": text[:100],
                    "url": href,
                    "is_policy": True,
                }
                # 去重
                existing_urls = {e["url"] for e in results[matched_candidate]}
                if entry["url"] not in existing_urls:
                    results[matched_candidate].append(entry)

            print(f"     找到 {sum(len(v) for v in results.values())} 篇 FB 引用報導（累計）")
            time.sleep(2)

        except requests.RequestException as exc:
            print(f"     擷取失敗：{exc}")

    return results


def _fetch_known_fb_posts() -> dict[str, list[dict[str, Any]]]:
    """以已知 FB 貼文 URL 建立來源清單（不需擷取 FB 內容，只記錄來源）。"""
    results: dict[str, list[dict[str, Any]]] = {
        name: [] for name in CANDIDATE_FB_PAGES
    }
    for name, info in CANDIDATE_FB_PAGES.items():
        for post_url in info.get("known_posts", []):
            results[name].append(
                {
                    "candidate": name,
                    "source": "facebook",
                    "url": post_url,
                    "note": "已知官方 FB 政見貼文（內容需手動查證或透過 FB API 擷取）",
                }
            )
    return results


def fetch_all() -> dict[str, Any]:
    """執行完整擷取流程。"""
    print("   A) 收集已知 FB 貼文 URL...")
    known = _fetch_known_fb_posts()
    for name, posts in known.items():
        if posts:
            print(f"     {name}: {len(posts)} 篇已知 FB 貼文")

    print("   B) 爬取媒體頁面找 FB 引用...")
    media_refs = _fetch_fb_referenced_from_media()
    for name, refs in media_refs.items():
        if refs:
            print(f"     {name}: {len(refs)} 篇媒體引用 FB 報導")

    # 合併
    merged: dict[str, list[dict[str, Any]]] = {}
    for name in CANDIDATE_FB_PAGES:
        seen: set[str] = set()
        combined: list[dict[str, Any]] = []
        for item in known.get(name, []) + media_refs.get(name, []):
            if item["url"] not in seen:
                seen.add(item["url"])
                combined.append(item)
        merged[name] = combined

    return merged


def write_cache(data: dict[str, list[dict[str, Any]]], cache_dir: Path) -> None:
    fb_dir = cache_dir / "fb"
    fb_dir.mkdir(parents=True, exist_ok=True)
    for name, posts in data.items():
        path = fb_dir / f"{name}.json"
        path.write_text(
            json.dumps(
                {"fetched_at": datetime.now(TZ_TAIPEI).isoformat(timespec="seconds"), "posts": posts},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def main(argv: list[str] | None = None) -> int:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="擷取候選人官方 Facebook 政見來源")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    from scraper import config
    cache_dir = config.CACHE_DIR

    print(f"=== Facebook 政見來源擷取 {datetime.now(TZ_TAIPEI).isoformat()} ===")
    data = fetch_all()

    total = sum(len(v) for v in data.values())

    if args.dry_run:
        for name, posts in data.items():
            for p in posts:
                src = p.get("source", "?")
                print(f"  [{name}] ({src}) {p.get('title', p.get('url', ''))[:70]}")
        print(f"\n[dry-run] 共 {total} 條，未寫入快取。")
        return 0

    if total:
        write_cache(data, cache_dir)
        print(f"\n已寫入 {cache_dir / 'fb'} /（共 {total} 條）")
    else:
        print("\n未擷取到任何 FB 來源。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
