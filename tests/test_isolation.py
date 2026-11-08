"""隔離性測試：單一候選人／單一政見失敗時，其他資料仍須完整產出。"""

from __future__ import annotations

from pathlib import Path

from scraper import config
from scraper.build import build_dataset
from scraper.fetch import FetchError

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeFetcher:
    """以本機 fixture 模擬來源網站，可指定要失敗的 URL。"""

    def __init__(self, fail_urls: set[str] | None = None) -> None:
        self.fail_urls = fail_urls or set()

    def get(self, url: str, use_cache: bool = False) -> str:
        if url in self.fail_urls:
            raise FetchError(f"模擬失敗：{url}")
        if url == config.INDEX_URL:
            return _fixture("index_sample.html")
        if url.endswith("/policies"):
            return _fixture("policies_sample.html")
        if "/candidates/" in url:
            return _fixture("candidate_sample.html")
        if "/policies/" in url:
            return _fixture("policy_sample.html")
        raise FetchError(f"未預期的 URL：{url}")


def test_profile_failure_does_not_block_other_candidates():
    failing = f"{config.BASE_URL}/candidates/cand-1/"
    dataset = build_dataset(fetcher=FakeFetcher({failing}))

    assert len(dataset["candidates"]) == 2
    first, second = dataset["candidates"]

    assert first["name"] == "王小明"  # 仍可由總覽頁取得
    assert first["partial"] is True
    assert first["platform_count"] == 2  # 仍可由政見列表頁取得
    assert second["partial"] is False
    assert second["platform_count"] == 2

    assert any(e["stage"] == "profile" for e in dataset["errors"])


def test_single_policy_failure_keeps_other_platforms():
    failing = f"{config.BASE_URL}/policies/policy-2/"
    dataset = build_dataset(fetcher=FakeFetcher({failing}))

    assert len(dataset["candidates"]) == 2
    for candidate in dataset["candidates"]:
        assert candidate["platform_count"] == 2
        failed = next(p for p in candidate["platforms"] if p["id"] == "policy-2")
        # 明細頁失敗時，退回列表頁摘要，且不得謊稱是完整政見。
        assert failed["content"] == "主張改善垃圾處理。"
        assert failed["is_full_platform"] is False

    assert sum(1 for e in dataset["errors"] if e["stage"] == "policy_detail") == 2


def test_entire_candidate_failure_still_produces_dataset():
    failing = {
        f"{config.BASE_URL}/candidates/cand-1/",
        f"{config.BASE_URL}/candidates/cand-1/policies",
    }
    dataset = build_dataset(fetcher=FakeFetcher(failing))

    assert dataset["candidate_count"] == 2
    assert dataset["candidates"][0]["name"] == "王小明"
    assert dataset["candidates"][0]["platform_count"] == 0
    assert dataset["candidates"][1]["platform_count"] == 2
    stages = {e["stage"] for e in dataset["errors"]}
    assert {"profile", "policies_page"} <= stages
