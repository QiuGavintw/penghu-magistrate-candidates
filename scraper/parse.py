"""HTML 解析層。

所有解析器只讀取頁面上已公開呈現的文字，不推論、不補寫。
若 selector 找不到資料，回傳 None 或空清單，由上層標記為「未提供」。
"""

from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup

from . import config

_WS_RE = re.compile(r"\s+")


def _clean(value: str | None) -> str:
    return _WS_RE.sub(" ", (value or "")).strip()


def _after_colon(text: str) -> str | None:
    """'登記黨派：無黨籍' -> '無黨籍'；沒有冒號則回傳 None。"""
    if "：" not in text:
        return None
    return _clean(text.split("：", 1)[1]) or None


def _parse_source_block(block: Any) -> dict[str, Any] | None:
    """解析 <div class="source"> 的連結、段落與發布／查閱日期。"""
    if block is None:
        return None
    link = block.find("a")
    small = block.find("small")
    small_text = _clean(small.get_text(" ", strip=True)) if small else ""

    parts = [p.strip() for p in small_text.split("｜") if p.strip()]
    section = parts[0] if parts else None
    published = None
    checked = None
    for part in parts[1:]:
        m = re.search(r"發布：\s*(\d{4}-\d{2}-\d{2})", part)
        if m:
            published = m.group(1)
        m = re.search(r"查閱：\s*(\d{4}-\d{2}-\d{2})", part)
        if m:
            checked = m.group(1)

    return {
        "title": _clean(link.get_text(" ", strip=True)) if link else None,
        "url": link.get("href") if link else None,
        "section": section,
        "published_date": published,
        "checked_date": checked,
        "raw_note": small_text or None,
    }


def _parse_policy_cards(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """解析政見摘要卡（候選人頁與 /policies 頁共用相同結構）。"""
    cards: list[dict[str, Any]] = []
    for article in soup.select("article.policy-summary-card"):
        link = article.select_one("a.policy-summary-link")
        title_el = article.select_one(".policy-summary-body h3")
        summary_el = article.select_one(".policy-summary-body p")
        evidence_el = article.select_one(".policy-summary-evidence")
        number_el = article.select_one(".policy-summary-number")
        if link is None or title_el is None:
            continue
        cards.append(
            {
                "id": (article.get("id") or "").removeprefix("policy-") or None,
                "number": _clean(number_el.get_text()) if number_el else None,
                "title": _clean(title_el.get_text()),
                "category": _clean(article.get("data-topic")) or None,
                "summary": _clean(summary_el.get_text()) if summary_el else None,
                "evidence_type": _clean(evidence_el.get_text()) if evidence_el else None,
                "url": link.get("href"),
            }
        )
    return cards


def parse_index(html: str) -> dict[str, Any]:
    """解析澎湖縣總覽頁：候選人清單與官方來源。"""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup

    candidates: list[dict[str, Any]] = []
    for article in main.select("article.person-card"):
        heading = article.select_one("h3.candidate-number-heading")
        if heading is None:
            continue
        anchors = heading.find_all("a")
        if not anchors:
            continue
        name_anchor = anchors[-1]
        ballot = heading.select_one("a.candidate-ballot")

        number = None
        if ballot is not None:
            number_el = ballot.find("b")
            if number_el is not None:
                digits = re.sub(r"\D", "", number_el.get_text())
                number = int(digits) if digits else None

        paragraphs = [_clean(p.get_text(" ", strip=True)) for p in article.find_all("p")]
        party = next(
            (_after_colon(t) for t in paragraphs if t.startswith("登記黨派")),
            None,
        )

        smalls = [_clean(s.get_text(" ", strip=True)) for s in article.find_all("small")]
        registration_date = next(
            (_after_colon(t) for t in smalls if t.startswith("登記日期")),
            None,
        )

        summary_anchor = next(
            (a for a in article.find_all("a") if "政見摘要" in _clean(a.get_text())),
            None,
        )
        summary_count = None
        if summary_anchor is not None:
            m = re.match(r"(\d+)", _clean(summary_anchor.get_text()))
            if m:
                summary_count = int(m.group(1))

        candidate_id = article.get("data-mayor-case-person")
        candidates.append(
            {
                "id": candidate_id,
                "name": _clean(name_anchor.get_text()),
                "number": number,
                "party": party,
                "registration_date": registration_date,
                "policy_summary_count": summary_count,
                "profile_url": f"{config.BASE_URL}/candidates/{candidate_id}/" if candidate_id else None,
                "policies_url": (
                    f"{config.BASE_URL}/candidates/{candidate_id}/policies"
                    if candidate_id
                    else None
                ),
                "ballot_source_url": ballot.get("href") if ballot else None,
                "ballot_source_note": ballot.get("title") if ballot else None,
            }
        )

    official_source = _parse_source_block(main.select_one("div.source"))

    site_modified = None
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            payload = json.loads(script.string or "")
        except (TypeError, ValueError):
            continue
        for node in payload.get("@graph", []):
            if node.get("@type") == "CollectionPage" and node.get("dateModified"):
                site_modified = node["dateModified"]
                break

    declared_count = None
    for p in main.find_all("p"):
        m = re.search(r"(\d+)\s*位登記參選人", _clean(p.get_text(" ", strip=True)))
        if m:
            declared_count = int(m.group(1))
            break

    return {
        "candidates": candidates,
        "official_source": official_source,
        "site_modified": site_modified,
        "declared_candidate_count": declared_count,
    }


def parse_candidate_page(html: str) -> dict[str, Any]:
    """解析候選人個人頁（基本資料、登記資料、政見摘要卡）。"""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup

    name_el = main.find("h1")
    party = None
    for p in main.find_all("p"):
        text = _clean(p.get_text(" ", strip=True))
        if text.startswith("登記黨派"):
            party = _after_colon(text)
            break

    birth_el = main.select_one("details.birthday-evidence time[datetime]")
    zodiac_el = main.select_one("span.person-zodiac")

    registration_date = None
    registration_note = None
    official_sources: list[dict[str, Any]] = []
    for section in main.select("section.panel"):
        heading = section.find(["h2", "h3"])
        if heading is None or "登記資料" not in _clean(heading.get_text()):
            continue
        for p in section.find_all("p"):
            text = _clean(p.get_text(" ", strip=True))
            if text.startswith("登記日期"):
                registration_date = _after_colon(text)
            elif text and not text.startswith("登記日期"):
                registration_note = text
        for block in section.select("div.source"):
            parsed = _parse_source_block(block)
            if parsed:
                official_sources.append(parsed)
        break

    return {
        "name": _clean(name_el.get_text()) if name_el else None,
        "party": party,
        "birth_date": birth_el.get("datetime") if birth_el else None,
        "zodiac": re.sub(r"[^\u4e00-\u9fff]", "", _clean(zodiac_el.get_text())) or None
        if zodiac_el
        else None,
        "registration_date": registration_date,
        "registration_note": registration_note,
        "official_sources": official_sources,
        "policy_cards": _parse_policy_cards(main),
        # 來源網站未提供以下欄位；保留 None，不自行編寫。
        "education": None,
        "experience": None,
        "biography": None,
    }


def parse_policies_page(html: str) -> dict[str, Any]:
    """解析 /policies 頁：政見摘要卡與宣告的政見數。"""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup

    declared_count = None
    for paragraph in main.select(".policy-catalog-heading p"):
        m = re.search(r"(\d+)\s*項已收錄主張", _clean(paragraph.get_text(" ", strip=True)))
        if m:
            declared_count = int(m.group(1))
            break

    cards = _parse_policy_cards(main)

    vision_titles = [
        _clean(a.get_text())
        for a in main.select(".candidate-vision-list h4 a")
    ]

    return {
        "declared_platform_count": declared_count,
        "policy_cards": cards,
        "vision_titles": vision_titles,
    }


def parse_policy_detail(html: str) -> dict[str, Any]:
    """解析單一政見頁：標題、分類、公開內容、限制說明與原始來源。"""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup

    heading = main.select_one("div.heading")
    title = None
    category = None
    if heading is not None:
        title_el = heading.find("h1")
        title = _clean(title_el.get_text()) if title_el else None
        meta = heading.find_all("p")
        if len(meta) >= 2:
            bits = [b.strip() for b in _clean(meta[-1].get_text()).split("·")]
            if len(bits) >= 3:
                category = bits[-1]

    article = main.select_one("article.policy")
    content = None
    caveats: list[str] = []
    source = None
    if article is not None:
        h3 = article.find("h3")
        if h3 is not None:
            title = _clean(h3.get_text()) or title
        tag = article.select_one("span.tag")
        if tag is not None:
            category = _clean(tag.get_text()) or category
        for p in article.find_all("p", recursive=False):
            text = _clean(p.get_text(" ", strip=True))
            if not text:
                continue
            if "caveat" in (p.get("class") or []):
                caveats.append(text)
            elif content is None:
                content = text
        source = _parse_source_block(article.select_one("div.source"))

    return {
        "title": title,
        "category": category,
        "content": content,
        "caveats": caveats,
        "source": source,
    }
