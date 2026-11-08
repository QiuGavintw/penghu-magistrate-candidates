"""資料集驗收測試：檢查已產出的 candidates.json / CSV 是否符合規則。"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "candidates.json"
CSV_PATH = ROOT / "candidates.csv"
PLATFORMS_CSV_PATH = ROOT / "platforms.csv"

EXPECTED_NAMES = ["許智富", "周倪安", "葉竹林", "吳淑瑾", "陳振中", "陳盡川"]


@pytest.fixture(scope="module")
def dataset():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def test_files_exist():
    for path in (JSON_PATH, CSV_PATH, PLATFORMS_CSV_PATH):
        assert path.exists(), f"缺少 {path.name}"


def test_json_top_level_fields(dataset):
    assert dataset["election"] == "2026 澎湖縣長選舉"
    assert dataset["county"] == "澎湖縣"
    assert dataset["source"] == "https://taiwanpoliticalzoo.com/other-cities/penghu/"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", dataset["last_updated"])
    assert dataset["errors"] == []


def test_candidate_count_matches_source(dataset):
    assert dataset["candidate_count"] == 6
    assert len(dataset["candidates"]) == 6
    assert [c["name"] for c in dataset["candidates"]] == EXPECTED_NAMES


def test_numbers_are_unique_and_sequential(dataset):
    numbers = [c["number"] for c in dataset["candidates"]]
    assert numbers == [1, 2, 3, 4, 5, 6]


def test_registration_fields_present(dataset):
    for candidate in dataset["candidates"]:
        assert candidate["party"]
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate["registration_date"])
        assert candidate["verified_at"] == "2026-10-16"
        assert candidate["qualification_status"]


def test_missing_fields_are_explicit(dataset):
    for candidate in dataset["candidates"]:
        for field in ("education", "experience", "biography"):
            assert candidate[field] is None
            assert field in candidate["missing_fields"]


def test_platforms_are_traceable_and_marked_as_summaries(dataset):
    total = 0
    for candidate in dataset["candidates"]:
        assert candidate["platform_count"] == len(candidate["platforms"]) > 0
        for platform in candidate["platforms"]:
            total += 1
            assert platform["title"]
            assert platform["content"]
            assert platform["content_type"] in {"新聞彙整摘要", "候選人公開自述"}
            assert platform["is_full_platform"] is False
            assert platform["url"].startswith("https://taiwanpoliticalzoo.com/policies/")
            assert platform["source"]["url"].startswith("http")
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", platform["source"]["published_date"])
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", platform["source"]["checked_date"])
    assert total == 23
    assert dataset["platform_count"] == total


def test_sources_distinguish_site_and_official(dataset):
    for candidate in dataset["candidates"]:
        types = {source["type"] for source in candidate["sources"]}
        assert "來源網站・候選人頁" in types
        assert "來源網站・政見列表" in types
        assert "中央選舉委員會・候選人登記彙總表" in types
        official = next(
            s for s in candidate["sources"] if s["type"].startswith("中央選舉委員會")
        )
        assert official["url"].startswith("https://web.cec.gov.tw/")


def test_json_is_utf8_and_has_no_replacement_characters():
    raw = JSON_PATH.read_bytes()
    text = raw.decode("utf-8")
    assert "\ufffd" not in text
    assert "澎湖縣" in text


def test_candidates_csv_opens_with_utf8_sig():
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    assert len(rows) == 7  # 表頭 + 6 位候選人
    assert rows[0][:4] == ["號次", "姓名", "政黨", "登記日期"]
    assert [row[1] for row in rows[1:]] == EXPECTED_NAMES
    # 缺漏欄位以「未提供」標記
    assert rows[1][5] == "未提供"  # 學歷
    assert rows[1][6] == "未提供"  # 經歷


def test_platforms_csv_row_count():
    with PLATFORMS_CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    assert len(rows) == 24  # 表頭 + 23 項政見
    assert rows[0][0] == "號次"
    assert all(row[6] == "否（僅摘要）" for row in rows[1:])


def test_sources_md_covers_every_candidate(dataset):
    text = (ROOT / "sources.md").read_text(encoding="utf-8")
    assert "robots.txt" in text
    assert "中央選舉委員會" in text
    for candidate in dataset["candidates"]:
        assert f"### {candidate['number']}. {candidate['name']}" in text
    assert text.count("**政見原始來源**") == 6


def test_completeness_is_consistent(dataset):
    for candidate in dataset["candidates"]:
        completeness = candidate["completeness"]
        assert completeness["fields_provided"] == 3  # 號次、政黨、登記日期
        assert completeness["fields_expected"] == 6
        assert completeness["platforms_total"] == candidate["platform_count"]
        assert completeness["platforms_with_content"] == candidate["platform_count"]
        assert completeness["platforms_with_full_text"] == 0
