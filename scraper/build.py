"""建立資料集：擷取 → 解析 → 正規化 → 輸出 JSON / CSV。

隔離原則：任何單一候選人或單一政見頁失敗時，只記錄錯誤，
其餘資料仍會完整輸出（見 tests/test_isolation.py）。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin

from . import config
from .fetch import Fetcher, FetchError
from .parse import (
    parse_candidate_page,
    parse_index,
    parse_policies_page,
    parse_policy_detail,
)
from .report import render_sources_md

TZ_TAIPEI = timezone(timedelta(hours=8))


# --- 小工具 -----------------------------------------------------------------
def _absolute(path_or_url: str | None) -> str | None:
    if not path_or_url:
        return None
    url = urljoin(config.BASE_URL + "/", path_or_url)
    # 來源網站的 canonical URL 以 "/" 結尾；統一格式方便比對。
    if "?" not in url and "#" not in url and not url.endswith("/"):
        url += "/"
    return url


def _split_publisher(title: str | None) -> tuple[str | None, str | None]:
    """'鳴新聞 · 澎湖縣長寶座…' -> ('鳴新聞', '澎湖縣長寶座…')。"""
    if not title:
        return None, None
    if "·" in title:
        publisher, rest = title.split("·", 1)
        return publisher.strip() or None, rest.strip() or None
    return None, title


def _blank(value: Any) -> bool:
    return value is None or value == "" or value == []


def _completeness(candidate: dict[str, Any]) -> dict[str, Any]:
    expected = ["number", "party", "registration_date", "education", "experience", "biography"]
    provided = [field for field in expected if not _blank(candidate.get(field))]
    platforms = candidate.get("platforms", [])
    return {
        "fields_expected": len(expected),
        "fields_provided": len(provided),
        "field_ratio": round(len(provided) / len(expected), 3),
        "platforms_total": len(platforms),
        "platforms_with_content": sum(1 for p in platforms if p.get("content")),
        "platforms_with_source_url": sum(
            1 for p in platforms if (p.get("source") or {}).get("url")
        ),
        "platforms_with_full_text": sum(1 for p in platforms if p.get("is_full_platform")),
    }


# --- 主要流程 ---------------------------------------------------------------
def _build_platforms(
    cards: list[dict[str, Any]],
    fetcher: Fetcher,
    use_cache: bool,
    errors: list[dict[str, Any]],
    candidate_label: str,
) -> list[dict[str, Any]]:
    platforms: list[dict[str, Any]] = []
    for index, card in enumerate(cards, start=1):
        url = _absolute(card.get("url"))
        detail: dict[str, Any] = {}
        if url:
            try:
                detail = parse_policy_detail(fetcher.get(url, use_cache=use_cache))
            except FetchError as exc:
                errors.append(
                    {
                        "candidate": candidate_label,
                        "stage": "policy_detail",
                        "url": url,
                        "error": str(exc),
                    }
                )
        else:
            errors.append(
                {
                    "candidate": candidate_label,
                    "stage": "policy_detail",
                    "url": None,
                    "error": "政見卡片缺少連結",
                }
            )

        source = detail.get("source") or {}
        publisher, article_title = _split_publisher(source.get("title"))
        order = card.get("number")
        try:
            order = int(order) if order is not None else index
        except (TypeError, ValueError):
            order = index

        platforms.append(
            {
                "order": order,
                "id": card.get("id"),
                "title": detail.get("title") or card.get("title"),
                "category": detail.get("category") or card.get("category"),
                "content": detail.get("content") or card.get("summary"),
                "content_type": card.get("evidence_type") or "新聞彙整摘要",
                "is_full_platform": False,  # 來源僅提供摘要，非完整政見全文
                "caveats": detail.get("caveats", []),
                "source": {
                    "publisher": publisher,
                    "title": article_title or source.get("title"),
                    "url": source.get("url"),
                    "section": source.get("section"),
                    "published_date": source.get("published_date"),
                    "checked_date": source.get("checked_date"),
                },
                "url": url,
            }
        )
    return platforms


def build_dataset(
    fetcher: Fetcher | None = None,
    use_cache: bool = False,
    scraped_at: datetime | None = None,
) -> dict[str, Any]:
    fetcher = fetcher or Fetcher(cache_dir=config.CACHE_DIR)
    scraped_at = scraped_at or datetime.now(TZ_TAIPEI)

    errors: list[dict[str, Any]] = []

    index_html = fetcher.get(config.INDEX_URL, use_cache=use_cache)
    index = parse_index(index_html)
    cards = index["candidates"]

    if index["declared_candidate_count"] is not None and len(cards) != index["declared_candidate_count"]:
        errors.append(
            {
                "candidate": None,
                "stage": "index",
                "url": config.INDEX_URL,
                "error": (
                    f"頁面宣告 {index['declared_candidate_count']} 位，實際解析 {len(cards)} 位"
                ),
            }
        )

    candidates: list[dict[str, Any]] = []
    for card in cards:
        label = card.get("name") or card.get("id") or "未知候選人"
        profile: dict[str, Any] = {}
        policy_page: dict[str, Any] = {}

        try:
            profile = parse_candidate_page(fetcher.get(card["profile_url"], use_cache=use_cache))
        except (FetchError, KeyError) as exc:
            errors.append(
                {
                    "candidate": label,
                    "stage": "profile",
                    "url": card.get("profile_url"),
                    "error": str(exc),
                }
            )

        try:
            policy_page = parse_policies_page(
                fetcher.get(card["policies_url"], use_cache=use_cache)
            )
        except (FetchError, KeyError) as exc:
            errors.append(
                {
                    "candidate": label,
                    "stage": "policies_page",
                    "url": card.get("policies_url"),
                    "error": str(exc),
                }
            )

        policy_cards = policy_page.get("policy_cards") or profile.get("policy_cards") or []
        platforms = _build_platforms(policy_cards, fetcher, use_cache, errors, label)

        official = (profile.get("official_sources") or [None])[0] or {}
        if not official and index.get("official_source"):
            official = index["official_source"]

        sources = [
            {
                "type": "來源網站・縣市總覽",
                "publisher": config.SITE_NAME,
                "url": config.INDEX_URL,
                "published_date": index.get("site_modified"),
                "checked_date": scraped_at.date().isoformat(),
            },
            {
                "type": "來源網站・候選人頁",
                "publisher": config.SITE_NAME,
                "url": _absolute(card.get("profile_url")),
                "published_date": index.get("site_modified"),
                "checked_date": scraped_at.date().isoformat(),
            },
            {
                "type": "來源網站・政見列表",
                "publisher": config.SITE_NAME,
                "url": _absolute(card.get("policies_url")),
                "published_date": index.get("site_modified"),
                "checked_date": scraped_at.date().isoformat(),
            },
            {
                "type": "中央選舉委員會・候選人登記彙總表",
                "publisher": "中央選舉委員會",
                "title": official.get("title"),
                "url": official.get("url") or config.CEC_REGISTRATION_PDF,
                "section": official.get("section"),
                "published_date": official.get("published_date"),
                "checked_date": official.get("checked_date"),
                "note": "官方登記資料；本專案未重新解析 PDF，僅記錄來源頁所載資訊與連結。",
            },
            {
                "type": "澎湖縣選舉委員會・抽籤號次",
                "publisher": "澎湖縣選舉委員會",
                "url": card.get("ballot_source_url") or config.CEC_BALLOT_PAGE,
                "note": card.get("ballot_source_note"),
                "checked_date": scraped_at.date().isoformat(),
            },
        ]
        sources = [s for s in sources if s.get("url")]

        verified_dates = [
            s.get("checked_date")
            for s in sources
            if s.get("type", "").startswith("中央選舉委員會") and s.get("checked_date")
        ]
        verified_at = max(verified_dates) if verified_dates else None

        candidate = {
            "id": card.get("id"),
            "name": profile.get("name") or card.get("name"),
            "number": card.get("number"),
            "party": profile.get("party") or card.get("party"),
            "registration_date": profile.get("registration_date") or card.get("registration_date"),
            "birth_date": profile.get("birth_date"),
            "zodiac": profile.get("zodiac"),
            "education": profile.get("education"),
            "experience": profile.get("experience"),
            "biography": profile.get("biography"),
            "platform_count": len(platforms),
            "platforms": platforms,
            "sources": sources,
            "verified_at": verified_at,
            "qualification_status": profile.get("registration_note"),
            "data_origin": {
                "basic_profile": "台灣選舉懶人包・候選人頁（來源網站自行整理）",
                "registration": "台灣選舉懶人包轉載中央選舉委員會登記彙總表",
                "platforms": "台灣選舉懶人包・政見頁（新聞彙整摘要，非完整政見全文）",
            },
            "partial": not bool(profile),
        }
        candidate["missing_fields"] = [
            field
            for field in ("education", "experience", "biography")
            if _blank(candidate.get(field))
        ]
        candidate["completeness"] = _completeness(candidate)
        candidates.append(candidate)

    total_platforms = sum(c["platform_count"] for c in candidates)

    return {
        "election": config.ELECTION_NAME,
        "county": config.COUNTY,
        "source": config.INDEX_URL,
        "source_site": config.SITE_NAME,
        "source_last_modified": index.get("site_modified"),
        "last_updated": scraped_at.date().isoformat(),
        "scraped_at": scraped_at.isoformat(timespec="seconds"),
        "candidate_count": len(candidates),
        "platform_count": total_platforms,
        "data_scope_notes": [
            "本資料集只重製來源網站已公開的短篇摘要與事實欄位，並保留來源連結與日期；照片、全文報導與其他素材權利屬原權利人。",
            "來源網站未提供學歷、經歷、個人介紹；相關欄位以 null 表示，不自行補寫。",
            "政見內容為來源網站的『新聞彙整摘要』，不是候選人完整政見全文，已以 is_full_platform=false 標記。",
            "登記號次、黨派、登記日期為來源網站轉載之中央選舉委員會／澎湖縣選舉委員會資料；官方 PDF 未經本專案重新解析。",
            "資料缺漏不代表候選人沒有相關政策或經歷。",
        ],
        "errors": errors,
        "candidates": candidates,
    }


# --- 輸出 -------------------------------------------------------------------
def write_json(dataset: dict[str, Any], path=config.JSON_PATH) -> None:
    path.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _label(value: Any) -> str:
    if _blank(value):
        return config.UNPROVIDED_LABEL
    if isinstance(value, (list, tuple)):
        return "；".join(str(v) for v in value)
    return str(value)


def write_csv(dataset: dict[str, Any], path=config.CSV_PATH) -> None:
    columns = [
        ("number", "號次"),
        ("name", "姓名"),
        ("party", "政黨"),
        ("registration_date", "登記日期"),
        ("birth_date", "出生日期"),
        ("education", "學歷"),
        ("experience", "經歷"),
        ("biography", "個人介紹"),
        ("platform_count", "政見數"),
        ("platform_titles", "政見標題"),
        ("field_completeness", "欄位完整度"),
        ("profile_url", "網站個人頁"),
        ("policies_url", "政見列表頁"),
        ("official_url", "官方查證網址"),
        ("verified_at", "最後查證日期"),
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([label for _, label in columns])
        for candidate in dataset["candidates"]:
            completeness = candidate["completeness"]
            official_url = next(
                (
                    s.get("url")
                    for s in candidate["sources"]
                    if s.get("type", "").startswith("中央選舉委員會")
                ),
                None,
            )
            row = {
                **candidate,
                "platform_titles": [p.get("title") for p in candidate["platforms"]],
                "field_completeness": (
                    f"{completeness['fields_provided']}/{completeness['fields_expected']}"
                ),
                "profile_url": next(
                    (
                        s.get("url")
                        for s in candidate["sources"]
                        if s.get("type") == "來源網站・候選人頁"
                    ),
                    None,
                ),
                "policies_url": next(
                    (
                        s.get("url")
                        for s in candidate["sources"]
                        if s.get("type") == "來源網站・政見列表"
                    ),
                    None,
                ),
                "official_url": official_url,
            }
            writer.writerow([_label(row.get(key)) for key, _ in columns])


def write_platforms_csv(dataset: dict[str, Any], path=config.PLATFORMS_CSV_PATH) -> None:
    columns = [
        "號次",
        "姓名",
        "政見序號",
        "政見標題",
        "政見分類",
        "內容類型",
        "是否完整政見",
        "政見內容",
        "限制說明",
        "政見頁網址",
        "原始來源標題",
        "原始來源網址",
        "來源發布日期",
        "來源查閱日期",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for candidate in dataset["candidates"]:
            for platform in candidate["platforms"]:
                source = platform.get("source") or {}
                writer.writerow(
                    [
                        _label(candidate.get("number")),
                        _label(candidate.get("name")),
                        _label(platform.get("order")),
                        _label(platform.get("title")),
                        _label(platform.get("category")),
                        _label(platform.get("content_type")),
                        "是" if platform.get("is_full_platform") else "否（僅摘要）",
                        _label(platform.get("content")),
                        _label(platform.get("caveats")),
                        _label(platform.get("url")),
                        _label(source.get("title")),
                        _label(source.get("url")),
                        _label(source.get("published_date")),
                        _label(source.get("checked_date")),
                    ]
                )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="建立 2026 澎湖縣長候選人資料集")
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="優先使用 .cache/raw 的本機快取（離線除錯用）",
    )
    parser.add_argument("--quiet", action="store_true", help="只輸出錯誤摘要")
    args = parser.parse_args(argv)

    dataset = build_dataset(use_cache=args.use_cache)
    write_json(dataset)
    write_csv(dataset)
    write_platforms_csv(dataset)
    config.SOURCES_MD_PATH.write_text(render_sources_md(dataset), encoding="utf-8")

    if not args.quiet:
        print(f"候選人：{dataset['candidate_count']} 位")
        print(f"政見：{dataset['platform_count']} 項")
        for candidate in dataset["candidates"]:
            completeness = candidate["completeness"]
            print(
                f"  {candidate['number']}. {candidate['name']}"
                f"（{candidate['party']}）"
                f" 政見 {candidate['platform_count']} 項"
                f" 欄位 {completeness['fields_provided']}/{completeness['fields_expected']}"
            )
        print(f"輸出：{config.JSON_PATH.name} / {config.CSV_PATH.name} / {config.PLATFORMS_CSV_PATH.name}")

    if dataset["errors"]:
        print(f"\n錯誤 {len(dataset['errors'])} 筆：", file=sys.stderr)
        for error in dataset["errors"]:
            print(
                f"  [{error['stage']}] {error.get('candidate') or '-'}：{error['error']}",
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
