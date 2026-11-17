"""Facebook 頁面爬蟲模組。

透過 Meta Graph API（Page Public Content Access）讀取候選人官方
Facebook 公開頁面貼文，不需登入。需設定 FB_APP_ID 與 FB_APP_SECRET
環境變數（或 FB_PAGE_TOKEN）。

來源優先順序：
  1. 選舉公報（CEC PDF，手動更新）
  2. 候選人官方 Facebook（本模組）
  3. 主流媒體報導（fetch_news.py）
  4. 台灣選舉懶人包（scraper/ 現有流程）

環境變數：
  FB_PAGE_TOKEN  - 長期有效的 Page Access Token（建議），或
  FB_APP_ID + FB_APP_SECRET - 用於自動取得 Page Token

用法：
  python -m fetch_fb            # 執行一次，輸出 JSON 到 .cache/fb/
  python -m fetch_fb --dry-run  # 只檢查，不寫入
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

TZ_TAIPEI = timezone(timedelta(hours=8))

# --- 候選人 Facebook 頁面 ---------------------------------------------------
# 格式：name -> (page_username_or_id, page_id)
# page_id 若不知道，可用 page_username 透過 Graph API 查詢。
CANDIDATE_FB_PAGES: dict[str, dict[str, str]] = {
    "葉竹林": {
        "page": "YEHCHULINinPENGHU",
        "label": "葉竹林 澎湖縣長候選人 官方粉絲團",
    },
    "吳淑瑾": {
        "page": "wushuchin.penghu",
        "label": "吳淑瑾 官方粉絲團",
    },
    "陳盡川": {
        "page": "chen.jin.chuan.441889",
        "label": "陳盡川（牛哥）個人帳號",
    },
}

# 政見關鍵詞（用於篩選與政見相關的貼文）
POLICY_KEYWORDS = [
    "政見", "政策", "參選", "競選", "澎湖", "縣長",
    "醫療", "交通", "觀光", "漁業", "垃圾", "環境",
    "青年", "教育", "養老", "托育", "農", "漁",
    "經濟", "消費", "禮金", "補貼", "補助", "焚化",
    "航空", "機票", "船", "離島", "軍公教",
]

# 排除關鍵詞（廣告、個人生活）
EXCLUDE_KEYWORDS = [
    "抽獎", "转发", "分享連結", "影片", "直播",
]

GRAPH_API_BASE = "https://graph.facebook.com/v23.0"


def _get_page_token() -> str:
    """從環境變數取得 Page Access Token。"""
    token = os.environ.get("FB_PAGE_TOKEN", "")
    if token:
        return token

    app_id = os.environ.get("FB_APP_ID", "")
    app_secret = os.environ.get("FB_APP_SECRET", "")
    if not app_id or not app_secret:
        return ""

    # 用 app_id|app_secret 換短期 token（只可讀 public 資料）
    url = f"{GRAPH_API_BASE}/oauth/access_token"
    params = {"client_id": app_id, "client_secret": app_secret, "grant_type": "client_credentials"}
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("access_token", "")
    except requests.RequestException:
        return ""


def _resolve_page_id(page_username: str, token: str) -> str | None:
    """以 page username 查詢 page ID。"""
    url = f"{GRAPH_API_BASE}/{page_username}"
    params = {"fields": "id,name,fan_count", "access_token": token}
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json().get("id")
    except requests.RequestException:
        pass
    return None


def _fetch_posts(page_id: str, token: str, limit: int = 50) -> list[dict[str, Any]]:
    """擷取頁面最近貼文。"""
    url = f"{GRAPH_API_BASE}/{page_id}/posts"
    params = {
        "fields": "message,created_time,link,permalink_url,shares{count},reactions.summary(true){summary_count},comments.limit(5){data,text,from{name},created_time}",
        "limit": min(limit, 50),
        "access_token": token,
    }
    posts: list[dict[str, Any]] = []
    try:
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code != 200:
            print(f"   FB API 回傳 {resp.status_code}：{resp.text[:200]}")
            return posts
        data = resp.json()
        for item in data.get("data", []):
            posts.append(item)
    except requests.RequestException as exc:
        print(f"   FB API 擷取失敗：{exc}")
    return posts


def _is_policy_post(post: dict[str, Any]) -> bool:
    """判斷貼文是否與政見相關。"""
    text = (post.get("message") or "").lower()
    if not text:
        return False
    for kw in EXCLUDE_KEYWORDS:
        if kw.lower() in text:
            return False
    return any(kw.lower() in text for kw in POLICY_KEYWORDS)


def _extract_post_data(post: dict[str, Any], candidate: str) -> dict[str, Any] | None:
    """從 FB 貼文中提取結構化資料。"""
    message = (post.get("message") or "").strip()
    if not message or not _is_policy_post(post):
        return None

    created = post.get("created_time", "")
    permalink = post.get("permalink_url") or f"https://www.facebook.com/{post.get('id', '')}"

    return {
        "candidate": candidate,
        "source": "facebook",
        "source_label": "官方社群媒體（Facebook）",
        "url": permalink,
        "post_id": post.get("id", ""),
        "created_time": created,
        "content": message[:500],
        "has_link": bool(post.get("link")),
        "link": post.get("link"),
    }


def fetch_all(candidate_names: list[str] | None = None) -> dict[str, list[dict[str, Any]]]:
    """擷取所有候選人 FB 貼文，回傳 {candidate_name: [post_data]}。"""
    token = _get_page_token()
    if not token:
        print("   FB_PAGE_TOKEN / FB_APP_ID + FB_APP_SECRET 未設定，跳過 Facebook 擷取。")
        print("   請設定環境變數後重試。")
        return {}

    targets = candidate_names or list(CANDIDATE_FB_PAGES.keys())
    results: dict[str, list[dict[str, Any]]] = {}

    for name in targets:
        page_info = CANDIDATE_FB_PAGES.get(name)
        if not page_info:
            continue

        print(f"   擷取 {name} 的 Facebook 貼文...")
        page_id = _resolve_page_id(page_info["page"], token)
        if not page_id:
            print(f"     找不到 page ID，跳過。")
            continue

        raw_posts = _fetch_posts(page_id, token, limit=30)
        posts = []
        for post in raw_posts:
            data = _extract_post_data(post, name)
            if data:
                posts.append(data)

        results[name] = posts
        print(f"     取得 {len(posts)} 篇政見相關貼文")
        time.sleep(1)  # 禮貌性延遲

    return results


def write_cache(data: dict[str, list[dict[str, Any]]], cache_dir: Path) -> None:
    """寫入 .cache/fb/ 目錄。"""
    fb_dir = cache_dir / "fb"
    fb_dir.mkdir(parents=True, exist_ok=True)
    for name, posts in data.items():
        path = fb_dir / f"{name}.json"
        path.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="擷取候選人官方 Facebook 政見貼文")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    from scraper import config
    cache_dir = config.CACHE_DIR

    print(f"=== Facebook 政見擷取 {datetime.now(TZ_TAIPEI).isoformat()} ===")
    data = fetch_all()

    if args.dry_run:
        for name, posts in data.items():
            for p in posts:
                print(f"  [{name}] {p['content'][:60]}... ({p['created_time']})")
        print("[dry-run] 未寫入快取。")
        return 0

    if data:
        write_cache(data, cache_dir)
        print(f"已寫入 {cache_dir / 'fb'} /")
    else:
        print("未擷取到任何貼文。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
