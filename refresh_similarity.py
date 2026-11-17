"""相似度計算模組，供 refresh.py 與獨立使用。

以 TF-IDF bigram 計算候選人整體與個別政見的 cosine similarity。
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any


def tokenize(text: str) -> list[str]:
    """中文字 bigram 分詞。"""
    text = re.sub(r"[，。、；！？（）「」『』【】\[\]{}《》]", "", text)
    text = re.sub(r"\d+", "", text)
    chars = [ch for ch in text if ch.isalpha() and "\u4e00" <= ch <= "\u9fff"]
    bigrams = [chars[i : i + 2] for i in range(len(chars) - 1)]
    return chars + bigrams


def _build_idf(corpus: list[list[str]]) -> dict[str, float]:
    num_docs = len(corpus)
    doc_freq: Counter[str] = Counter()
    for tokens in corpus:
        for t in set(tokens):
            doc_freq[t] += 1
    return {
        t: math.log((1 + num_docs) / (1 + df)) + 1
        for t, df in doc_freq.items()
    }


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf = Counter(tokens)
    total = len(tokens) if tokens else 1
    return {t: (count / total) * idf.get(t, 0) for t, count in tf.items()}


def _cosine(v1: dict[str, float], v2: dict[str, float]) -> float:
    dot = sum(v1[t] * v2[t] for t in set(v1) & set(v2))
    mag1 = math.sqrt(sum(x * x for x in v1.values()))
    mag2 = math.sqrt(sum(x * x for x in v2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


def compute_similarity_matrix(
    candidates: list[dict[str, Any]],
) -> tuple[list[str], list[list[float]]]:
    """計算 6 位候選人整體政見的 TF-IDF cosine 相似度矩陣。

    回傳 (labels, matrix)。
    """
    # 收集所有政見文字
    all_texts: list[tuple[str, list[str]]] = []
    for cand in candidates:
        text = " ".join(p.get("content", "") for p in cand.get("platforms", []))
        all_texts.append((cand["name"], tokenize(text)))

    # 建立 IDF
    idf = _build_idf([tokens for _, tokens in all_texts])

    # 建立候選人向量
    cand_vectors = [
        _tfidf_vector(tokens, idf) for _, tokens in all_texts
    ]

    labels = [f"{name}" for name, _ in all_texts]
    n = len(labels)
    matrix: list[list[float]] = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                matrix[i][j] = 1.0
            elif j > i:
                val = _cosine(cand_vectors[i], cand_vectors[j])
                matrix[i][j] = matrix[j][i] = val

    return labels, matrix


def compute_top_pairs(
    candidates: list[dict[str, Any]],
    top_n: int = 12,
    min_similarity: float = 0.15,
) -> list[dict[str, Any]]:
    """計算跨候選人個別政見的最相似配對。

    回傳排序後的配對列表，每項包含：
      similarity, candidate_a, number_a, policy_a, candidate_b, number_b, policy_b
    """
    # 收集所有政見
    policy_texts: list[str] = []
    policy_meta: list[dict[str, Any]] = []
    for cand in candidates:
        for p in cand.get("platforms", []):
            policy_texts.append(p.get("content", ""))
            policy_meta.append(
                {
                    "candidate_a": cand["name"],
                    "number_a": cand.get("number"),
                    "policy_a": p.get("title", p.get("content", ""))[:80],
                }
            )

    # 建立 IDF（跨所有政見）
    tokenized = [tokenize(t) for t in policy_texts]
    idf = _build_idf(tokenized)
    vectors = [_tfidf_vector(tokens, idf) for tokens in tokenized]

    # 計算所有跨候選人配對
    pairs: list[tuple[float, int, int]] = []
    for i in range(len(vectors)):
        for j in range(i + 1, len(vectors)):
            if policy_meta[i]["number_a"] != policy_meta[j]["number_a"]:
                sim = _cosine(vectors[i], vectors[j])
                if sim >= min_similarity:
                    pairs.append((sim, i, j))

    pairs.sort(key=lambda x: -x[0])

    result: list[dict[str, Any]] = []
    for sim, i, j in pairs[:top_n]:
        a, b = policy_meta[i], policy_meta[j]
        result.append(
            {
                "similarity": round(sim, 4),
                "candidate_a": a["candidate_a"],
                "number_a": a["number_a"],
                "policy_a": a["policy_a"],
                "candidate_b": b["candidate_a"],
                "number_b": b["number_a"],
                "policy_b": b["policy_a"],
            }
        )

    return result
