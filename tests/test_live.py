"""即時來源測試（預設跳過）。

執行方式：
    RUN_LIVE_TESTS=1 python -m pytest tests/test_live.py
"""

from __future__ import annotations

import os

import pytest

from scraper import config
from scraper.fetch import Fetcher
from scraper.parse import parse_index, parse_policy_detail

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.getenv("RUN_LIVE_TESTS") != "1",
        reason="需要網路；設定 RUN_LIVE_TESTS=1 才執行",
    ),
]


def test_live_index_still_lists_six_candidates():
    html = Fetcher(cache_dir=None).get(config.INDEX_URL)
    result = parse_index(html)
    assert result["declared_candidate_count"] == 6
    assert len(result["candidates"]) == 6
    assert all(c["name"] and c["number"] for c in result["candidates"])


def test_live_policy_page_still_has_source():
    fetcher = Fetcher(cache_dir=None)
    html = fetcher.get(config.INDEX_URL)
    card = parse_index(html)["candidates"][0]
    policies_html = fetcher.get(card["policies_url"])
    assert "policy-summary-card" in policies_html
    detail = parse_policy_detail(
        fetcher.get(f"{config.BASE_URL}/policies/26d00000-0000-4000-8000-000000004795/")
    )
    assert detail["title"]
    assert detail["content"]
    assert detail["source"]["url"].startswith("http")
