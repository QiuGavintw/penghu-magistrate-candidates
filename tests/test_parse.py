"""解析器單元測試：使用自製的最小 HTML  fixture，不依賴網路。"""

from pathlib import Path

from scraper.parse import (
    parse_candidate_page,
    parse_index,
    parse_policies_page,
    parse_policy_detail,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_index_extracts_candidates_and_official_source():
    result = parse_index(_read("index_sample.html"))

    assert result["declared_candidate_count"] == 2
    assert result["site_modified"] == "2026-11-02"

    first, second = result["candidates"]
    assert first["id"] == "cand-1"
    assert first["name"] == "王小明"
    assert first["number"] == 1
    assert first["party"] == "無黨籍"
    assert first["registration_date"] == "2026-09-03"
    assert first["policy_summary_count"] == 2
    assert first["profile_url"].endswith("/candidates/cand-1/")
    assert first["ballot_source_url"].endswith("/phec/article/65367")

    assert second["name"] == "陳大華"
    assert second["party"] == "民主進步黨"

    official = result["official_source"]
    assert official["published_date"] == "2026-09-07"
    assert official["checked_date"] == "2026-10-16"
    assert official["url"].endswith("sample.pdf")


def test_parse_candidate_page_keeps_missing_fields_as_none():
    result = parse_candidate_page(_read("candidate_sample.html"))

    assert result["name"] == "王小明"
    assert result["party"] == "無黨籍"
    assert result["birth_date"] == "1979-10-02"
    assert result["zodiac"] == "天秤座"
    assert result["registration_date"] == "2026-09-03"
    assert "資格審定" in result["registration_note"]
    # 來源網站未提供學歷／經歷／個人介紹，不得自行補寫。
    assert result["education"] is None
    assert result["experience"] is None
    assert result["biography"] is None
    assert len(result["policy_cards"]) == 2
    assert result["official_sources"][0]["checked_date"] == "2026-10-16"


def test_parse_policies_page_reads_cards_and_declared_count():
    result = parse_policies_page(_read("policies_sample.html"))

    assert result["declared_platform_count"] == 2
    assert [c["title"] for c in result["policy_cards"]] == ["離島醫療強化", "垃圾處理"]
    assert result["policy_cards"][0]["category"] == "長照醫療"
    assert result["policy_cards"][0]["evidence_type"] == "新聞彙整摘要"
    assert result["vision_titles"] == ["離島醫療強化", "垃圾處理"]


def test_parse_policy_detail_extracts_content_caveat_and_source():
    result = parse_policy_detail(_read("policy_sample.html"))

    assert result["title"] == "離島醫療強化"
    assert result["category"] == "長照醫療"
    assert result["content"].startswith("提出離島急重症醫療強化計畫")
    assert result["caveats"] == ["原報導未列確切設備採購清單或醫院核定升級。"]
    assert result["source"]["url"] == "https://example.com/news/1"
    assert result["source"]["published_date"] == "2026-03-06"
    assert result["source"]["checked_date"] == "2026-10-16"
    assert result["source"]["section"] == "施政藍圖段落"
