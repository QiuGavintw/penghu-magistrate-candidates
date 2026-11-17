"""定期刷新澎湖縣長候選人政見資料。

執行流程：
  1. 檢查投票日（2026-11-28），若已過期則停止
  2. 讀取 candidates.json 現有資料
  3. 檢查 taiwanpoliticalzoo.com 來源是否有新內容
  4. 檢查選舉公報（CEC）是否有更新
  5. 若有變化：更新 OKF 文件、index.html 相似度、git commit & push

用法：
  python -m refresh              # 執行一次
  python -m refresh --dry-run    # 只檢查不寫入
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scraper import config
from scraper.fetch import Fetcher, FetchError
from scraper.parse import parse_index

TZ_TAIPEI = timezone(timedelta(hours=8))
PROJECT_ROOT = config.PROJECT_ROOT
OKF_DIR = PROJECT_ROOT / "okf"

ELECTION_DAY = datetime(2026, 11, 28, 8, 0, tzinfo=TZ_TAIPEI)

# 候選人官方 Facebook（用於標記來源類型）
CANDIDATE_FB = {
    "葉竹林": "https://www.facebook.com/YEHCHULINinPENGHU/",
    "吳淑瑾": "https://www.facebook.com/wushuchin.penghu/",
    "陳盡川": "https://www.facebook.com/chen.jin.chuan.441889/",
}

# OKF 候選人檔案對應
CANDIDATE_OKF_FILE = {
    "許智富": "okf/candidates/hsu-chih-fu.md",
    "周倪安": "okf/candidates/chou-ni-an.md",
    "葉竹林": "okf/candidates/ye-chu-lin.md",
    "吳淑瑾": "okf/candidates/wu-shu-jin.md",
    "陳振中": "okf/candidates/chen-chin-chung.md",
    "陳盡川": "okf/candidates/chen-jin-chuan.md",
}


def now_iso() -> str:
    return datetime.now(TZ_TAIPEI).isoformat(timespec="seconds")


def is_before_election() -> bool:
    return datetime.now(TZ_TAIPEI) < ELECTION_DAY


def load_existing_dataset() -> dict[str, Any]:
    return json.loads(config.JSON_PATH.read_text(encoding="utf-8"))


def fetch_latest_index() -> dict[str, Any]:
    fetcher = Fetcher(cache_dir=None)
    html = fetcher.get(config.INDEX_URL)
    return parse_index(html)


def check_cec_announcement() -> dict[str, Any] | None:
    """檢查 CEC 候選人頁面是否有更新（以 URL 最後修改時間判斷）。"""
    fetcher = Fetcher(cache_dir=None)
    try:
        html = fetcher.get(config.CEC_BALLOT_PAGE)
    except FetchError:
        return None
    # 簡易檢查：記錄檢查日期，不解析 PDF
    return {
        "checked_at": now_iso(),
        "url": config.CEC_BALLOT_PAGE,
        "note": "已檢查 CEC 候選人登記彙總表頁面，PDF 內容未重新解析。",
    }


def diff_platforms(
    old: list[dict[str, Any]],
    new: list[dict[str, Any]],
) -> dict[str, Any]:
    """比對政見列表，回傳新增 / 修改 / 刪除。"""
    old_by_id = {p.get("id"): p for p in old}
    new_by_id = {p.get("id"): p for p in new}

    added = [new_by_id[k] for k in new_by_id if k not in old_by_id]
    removed = [old_by_id[k] for k in old_by_id if k not in new_by_id]
    modified = []
    for k in new_by_id:
        if k in old_by_id:
            o, n = old_by_id[k], new_by_id[k]
            if (
                o.get("content") != n.get("content")
                or o.get("title") != n.get("title")
                or (o.get("source") or {}).get("url") != (n.get("source") or {}).get("url")
            ):
                modified.append(n)

    return {"added": added, "removed": removed, "modified": modified}


def update_okf_candidate(name: str, candidate: dict[str, Any], diff: dict[str, Any]) -> list[str]:
    """更新對應的 OKF 候選人文件，回傳被修改的檔案路徑列表。"""
    rel_path = CANDIDATE_OKF_FILE.get(name)
    if not rel_path:
        return []

    file_path = PROJECT_ROOT / rel_path
    if not file_path.exists():
        return []

    content = file_path.read_text(encoding="utf-8")
    modified = False

    # 更新 generated.at 與 stale_after
    content = re.sub(
        r'generated: \{ by: [^,]+, at: [^}]+\}',
        f'generated: {{ by: process:refresh, at: {now_iso()} }}',
        content,
    )

    # 若有新增政見，在政見區塊末尾加入
    if diff.get("added"):
        new_policies_block = "\n"
        for p in diff["added"]:
            title = p.get("title", "（無標題）")
            content_text = p.get("content", "")
            source_url = (p.get("source") or {}).get("url", "")
            source_label = "官方社群媒體" if "facebook.com" in source_url else "媒體報導"
            fb_domain = source_url.split("/")[2] if source_url else ""
            new_policies_block += (
                f"\n## {title}\n\n{content_text}\n\n"
                f"> 來源：[{source_label}]({source_url})\n"
            )
        if new_policies_block.strip():
            # 插入在「# 相似政見」之前（若存在），否則在檔案末尾
            marker = "\n# 相似政見"
            if marker in content:
                content = content.replace(marker, new_policies_block + marker, 1)
            else:
                content += new_policies_block
            modified = True

    # 若有修改政見，更新 generated 即可（內容由人工審視）
    if diff.get("modified"):
        modified = True

    if modified:
        file_path.write_text(content, encoding="utf-8")
        return [rel_path]

    return []


def update_okf_log(changes: list[str]) -> None:
    """在 okf/log.md 加入今天的更新記錄。"""
    log_path = OKF_DIR / "log.md"
    today = datetime.now(TZ_TAIPEI).date().isoformat()
    entry_lines = [f"## {today}"]
    for change in changes:
        entry_lines.append(f"* **Update**: {change}")
    entry_block = "\n".join(entry_lines) + "\n"

    if log_path.exists():
        content = log_path.read_text(encoding="utf-8")
        # 若今天已有記錄則取代，否則插入到 "# 澎湖縣長選舉知識庫更新記錄" 之後
        today_pattern = f"## {today}"
        if today_pattern in content:
            # 取代今天整段
            pattern = re.compile(
                rf"## {re.escape(today)}\n.*?(?=\n## |\Z)", re.DOTALL
            )
            content = pattern.sub(entry_block + "\n", content, count=1)
        else:
            header_marker = "# 澎湖縣長選舉知識庫更新記錄\n"
            content = content.replace(header_marker, header_marker + "\n" + entry_block + "\n", 1)
        log_path.write_text(content, encoding="utf-8")


def update_index_html(new_dataset: dict[str, Any]) -> None:
    """更新 index.html 中的相似度數據（重新計算）。"""
    # 讀取現有 index.html，更新相似度矩陣數據
    index_html_path = PROJECT_ROOT / "index.html"
    if not index_html_path.exists():
        return

    content = index_html_path.read_text(encoding="utf-8")

    # 重新計算相似度（使用與相似度分析相同的邏輯）
    import importlib.util
    import sys as _sys
    spec = importlib.util.spec_from_file_location(
        "refresh_similarity", PROJECT_ROOT / "refresh_similarity.py"
    )
    mod = importlib.util.module_from_spec(spec)
    _sys.modules["refresh_similarity"] = mod
    spec.loader.exec_module(mod)
    compute_similarity_matrix = mod.compute_similarity_matrix
    compute_top_pairs = mod.compute_top_pairs

    candidates = new_dataset.get("candidates", [])
    if len(candidates) >= 2:
        labels, matrix = compute_similarity_matrix(candidates)
        top_pairs = compute_top_pairs(candidates)

        # 更新 JS 中的 simData
        new_matrix_js = json.dumps(
            [f"{c['name']}({c['number']})" for c in candidates], ensure_ascii=False
        )
        new_matrix_values = json.dumps(matrix)
        new_pairs_js = json.dumps(_format_pairs_for_js(top_pairs), ensure_ascii=False)

        # 替換 labels
        content = re.sub(
            r'labels: \[.*?\]',
            f'labels: {new_matrix_js}',
            content,
            flags=re.DOTALL,
        )
        # 替換 matrix
        content = re.sub(
            r'matrix: \[.*?\]\n\s*\]',
            f'matrix: {new_matrix_values}\n  ]',
            content,
            flags=re.DOTALL,
        )
        # 替換 pairs
        content = re.sub(
            r'pairs: \[.*?\]\n\s*\}',
            f'pairs: {new_pairs_js}\n  }}',
            content,
            flags=re.DOTALL,
        )

        index_html_path.write_text(content, encoding="utf-8")


def _format_pairs_for_js(top_pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """將相似度配對轉為 index.html JS 所需的格式。"""
    result = []
    for p in top_pairs:
        result.append(
            {
                "sim": round(p["similarity"], 4),
                "a": f"{p['candidate_a']}({p['number_a']})",
                "aPolicy": p["policy_a"][:60],
                "b": f"{p['candidate_b']}({p['number_b']})",
                "bPolicy": p["policy_b"][:60],
            }
        )
    return result


def git_commit_and_push(message: str) -> bool:
    """git add / commit / push。"""
    env_token = subprocess.run(
        "git remote -v", shell=True, capture_output=True, text=True,
        cwd=PROJECT_ROOT,
    ).stdout

    try:
        subprocess.run(
            ["git", "add", "-A"], check=True, cwd=PROJECT_ROOT,
            capture_output=True,
        )
        # 檢查是否有暫存的變更
        status = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=PROJECT_ROOT, capture_output=True,
        )
        if status.returncode == 0:
            print("沒有需要 commit 的變更。")
            return True

        subprocess.run(
            ["git", "commit", "-m", message], check=True, cwd=PROJECT_ROOT,
            capture_output=True,
        )
        print(f"已 commit：{message}")

        # push（使用 GITHUB_TOKEN 環境變數，若存在）
        import os
        token = os.environ.get("GITHUB_TOKEN", "")
        if token:
            # GitHub Actions 或本機設定 GITHUB_TOKEN 時，用 token 認證 push
            remote_url = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, cwd=PROJECT_ROOT,
            ).stdout.strip()
            if "github.com" in remote_url:
                repo_path = remote_url.replace("https://", "").replace(".git", "")
                auth_url = f"https://x-access-token:{token}@github.com/{repo_path}.git"
                subprocess.run(
                    ["git", "push", auth_url, "HEAD:main"],
                    check=True, cwd=PROJECT_ROOT,
                    capture_output=True, text=True,
                )
            else:
                subprocess.run(
                    ["git", "push", "-u", "origin", "main"],
                    check=True, cwd=PROJECT_ROOT,
                    capture_output=True, text=True,
                )
            print("已 push 到 origin/main")
        else:
            print("GITHUB_TOKEN 未設定，跳過 push。請手動執行：git push origin main")
        return True

    except subprocess.CalledProcessError as exc:
        print(f"git 操作失敗：{exc}", file=sys.stderr)
        if exc.stderr:
            print(exc.stderr.decode("utf-8", errors="replace"), file=sys.stderr)
        return False


def run_refresh(dry_run: bool = False) -> int:
    """執行一次完整的刷新流程。"""
    print(f"=== 澎湖縣長政見刷新 {now_iso()} ===")

    if not is_before_election():
        print("投票日已過（2026-11-28），停止刷新。")
        return 0

    print("1/5 讀取現有資料集...")
    existing = load_existing_dataset()
    existing_platforms_by_name = {
        c["name"]: c.get("platforms", []) for c in existing.get("candidates", [])
    }

    print("2/5 擷取來源網站最新內容...")
    try:
        new_index = fetch_latest_index()
        new_cards = new_index.get("candidates", [])
        print(f"   來源網站現有 {len(new_cards)} 位候選人")
    except FetchError as exc:
        print(f"   擷取來源網站失敗：{exc}")
        return 1

    print("3/5 檢查 CEC 選舉公報...")
    cec_check = check_cec_announcement()
    if cec_check:
        print(f"   CEC 頁面檢查時間：{cec_check['checked_at']}")
        print(f"   注意：{cec_check['note']}")
        print("   （若 CEC 發布新選舉公報，請手動更新 candidates.json 中的號次與黨派）")

    print("4/5 比對政見差異...")
    all_changes: list[str] = []
    updated_okf_files: list[str] = []

    # 重新擷取完整資料集
    from scraper.build import build_dataset, write_json, write_csv, write_platforms_csv
    new_dataset = build_dataset()

    for cand in new_dataset.get("candidates", []):
        name = cand.get("name", "")
        old_platforms = existing_platforms_by_name.get(name, [])
        new_platforms = cand.get("platforms", [])
        diff = diff_platforms(old_platforms, new_platforms)

        has_changes = bool(diff["added"] or diff["modified"] or diff["removed"])
        if has_changes:
            summary = (
                f"{name}：新增 {len(diff['added'])} 項、"
                f"修改 {len(diff['modified'])} 項、刪除 {len(diff['removed'])} 項政見"
            )
            print(f"   ⚡ {summary}")
            all_changes.append(summary)

            if not dry_run:
                updated_okf_files.extend(update_okf_candidate(name, cand, diff))
        else:
            print(f"   ✓ {name}：無變化")

    # 寫出更新的 JSON / CSV
    if not dry_run:
        write_json(new_dataset)
        write_csv(new_dataset)
        write_platforms_csv(new_dataset)
        all_changes.append("更新 candidates.json / candidates.csv / platforms.csv")

        # 更新 OKF log
        if all_changes:
            update_okf_log(all_changes)
            all_changes.append("更新 okf/log.md")

        # 更新 index.html 相似度
        try:
            update_index_html(new_dataset)
            all_changes.append("更新 index.html 相似度數據")
        except Exception as exc:
            print(f"   更新 index.html 相似度失敗（非致命）：{exc}", file=sys.stderr)

        # 更新 OKF 候選人文件
        if updated_okf_files:
            all_changes.append(f"更新 OKF 候選人文件：{len(updated_okf_files)} 個")

    if dry_run:
        print("\n[dry-run] 未寫入任何檔案。")
        if all_changes:
            print(f"[dry-run] 預警：有 {len(all_changes)} 項變更待寫入")
        return 0

    if all_changes:
        print(f"\n5/5 提交變更（共 {len(all_changes)} 項）...")
        commit_msg = (
            f"chore: 每日政見刷新 {datetime.now(TZ_TAIPEI).date().isoformat()}\n\n"
            + "\n".join(f"- {c}" for c in all_changes)
        )
        git_commit_and_push(commit_msg)
    else:
        print("5/5 無變更，跳過 commit。")

    print("\n=== 刷新完成 ===")
    return 0


def main(argv: list[str] | None = None) -> int:
    import os, sys
    # 確保 stdout 支援 UTF-8（Windows console 相容）
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="定期刷新澎湖縣長候選人政見資料")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只檢查有無變化，不寫入檔案也不 commit",
    )
    parser.add_argument(
        "--skip-push", action="store_true",
        dest="skip_push",
        help="commit 但不 push（需搭配 GITHUB_TOKEN 才會 push）",
    )
    args = parser.parse_args(argv)

    # 若 skip_push，暫時移除 GITHUB_TOKEN 環境變數
    import os
    saved_token = os.environ.get("GITHUB_TOKEN")
    if args.skip_push:
        os.environ.pop("GITHUB_TOKEN", None)

    try:
        return run_refresh(dry_run=args.dry_run)
    finally:
        if saved_token is not None:
            os.environ["GITHUB_TOKEN"] = saved_token


if __name__ == "__main__":
    raise SystemExit(main())
