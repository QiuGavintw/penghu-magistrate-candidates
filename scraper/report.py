"""產生 sources.md：把資料集中每一筆來源寫成人類可讀的查證紀錄。"""

from __future__ import annotations

from typing import Any

from . import config


def _cell(value: Any) -> str:
    text = config.UNPROVIDED_LABEL if value in (None, "", []) else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def render_sources_md(dataset: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# 資料來源與查證紀錄")
    lines.append("")
    lines.append(
        "> 本檔案由 `python -m scraper` 依 `candidates.json` 自動產生；"
        f"最後產生時間：{dataset['scraped_at']}。"
    )
    lines.append("")
    lines.append("## 1. 主要來源")
    lines.append("")
    lines.append(f"- 網站：{dataset['source_site']}")
    lines.append(f"- 澎湖縣總覽頁：{dataset['source']}")
    lines.append(f"- 來源頁標示之最後更新：{dataset.get('source_last_modified') or config.UNPROVIDED_LABEL}")
    lines.append(f"- robots.txt：{config.ROBOTS_URL}")
    lines.append("  - 內容：`User-agent: *` / `Allow: /`，僅禁止 `/admin`、`/workspace`、`/my`、`/auth`、`/login`。")
    lines.append(f"- 使用條款：{config.TERMS_URL}")
    lines.append(
        "  - 摘要：本站提供公開資訊整理；引用請保留來源與日期；"
        "完整原文及素材權利屬原權利人。"
    )
    lines.append("")
    lines.append("## 2. 官方查證來源")
    lines.append("")
    lines.append(
        f"- 中央選舉委員會「115年縣市長選舉候選人登記彙總表」：{config.CEC_REGISTRATION_PDF}"
    )
    lines.append("  - 由來源網站列為登記資料依據；本專案未重新解析 PDF 內容。")
    lines.append(
        f"- 澎湖縣選舉委員會抽籤號次頁：{config.CEC_BALLOT_PAGE}"
    )
    lines.append("")
    lines.append("## 3. 各候選人來源")
    lines.append("")

    for candidate in dataset["candidates"]:
        lines.append(f"### {candidate['number']}. {candidate['name']}（{candidate['party']}）")
        lines.append("")
        lines.append(
            f"- 登記日期：{_cell(candidate.get('registration_date'))}"
            f"｜最後查證：{_cell(candidate.get('verified_at'))}"
        )
        lines.append(f"- 資格狀態註記：{_cell(candidate.get('qualification_status'))}")
        lines.append("")
        lines.append("| 類型 | 標題 | 網址 | 發布日期 | 查閱日期 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for source in candidate["sources"]:
            lines.append(
                "| {type} | {title} | {url} | {published} | {checked} |".format(
                    type=_cell(source.get("type")),
                    title=_cell(source.get("title")),
                    url=_cell(source.get("url")),
                    published=_cell(source.get("published_date")),
                    checked=_cell(source.get("checked_date")),
                )
            )
        lines.append("")
        lines.append("**政見原始來源**")
        lines.append("")
        lines.append("| # | 政見 | 分類 | 內容類型 | 原始來源 | 發布日期 | 查閱日期 | 網址 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for platform in candidate["platforms"]:
            source = platform.get("source") or {}
            lines.append(
                "| {order} | {title} | {category} | {ctype} | {publisher} | {published} | {checked} | {url} |".format(
                    order=_cell(platform.get("order")),
                    title=_cell(platform.get("title")),
                    category=_cell(platform.get("category")),
                    ctype=_cell(platform.get("content_type")),
                    publisher=_cell(source.get("publisher")),
                    published=_cell(source.get("published_date")),
                    checked=_cell(source.get("checked_date")),
                    url=_cell(source.get("url")),
                )
            )
        lines.append("")

    lines.append("## 4. 擷取限制與倫理")
    lines.append("")
    lines.append("- 僅以 GET 存取公開頁面，未登入、未繞過任何存取控制。")
    lines.append("- 請求間隔至少 1.2 秒，並在失敗時有限次重試。")
    lines.append("- 不重製候選人照片；不轉載完整新聞報導。")
    lines.append("- 政見內容為來源網站的短篇摘要，已標記 `is_full_platform: false`。")
    lines.append("- 缺漏欄位一律標記 `null`／「未提供」，不以推論補值。")
    lines.append("")
    return "\n".join(lines)
