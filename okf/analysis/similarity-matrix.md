---
type: Similarity Analysis
title: 政見相似度矩陣
description: 6 位澎湖縣長候選人整體政見的 TF-IDF bigram cosine 相似度矩陣。
tags: [澎湖, 相似度分析, TF-IDF, cosine-similarity]
status: stable
generated: { by: process:tfidf-similarity, at: 2026-11-14T00:00:00Z }
stale_after: 2026-11-28T00:00:00Z
sources:
  - id: twp-penghu
    resource: https://taiwanpoliticalzoo.com/other-cities/penghu/
    title: 台灣選舉懶人包 - 澎湖縣 2026 縣長
    last_modified: 2026-11-02T00:00:00Z
---

# 方法論

以各候選人所有政見文字合併為單一文檔，對每個政見進行中文字 bigram 分詞，計算 TF-IDF 向量後以 cosine similarity 計算候選人兩兩之間的整體相似度。

* 分詞：中文字 bigram
* 向量：TF-IDF（smooth IDF）
* 相似度：cosine similarity（0 = 完全不重疊，1 = 完全相同）

# 相似度矩陣

| | 許智富(1) | 周倪安(2) | 葉竹林(3) | 吳淑瑾(4) | 陳振中(5) | 陳盡川(6) |
|---|---|---|---|---|---|---|
| **許智富(1)** | 1.00 | 0.056 | 0.043 | 0.057 | 0.046 | 0.062 |
| **周倪安(2)** | 0.056 | 1.00 | 0.127 | 0.085 | 0.099 | 0.146 |
| **葉竹林(3)** | 0.043 | 0.127 | 1.00 | 0.141 | 0.188 | 0.102 |
| **吳淑瑾(4)** | 0.057 | 0.085 | 0.141 | 1.00 | 0.204 | 0.073 |
| **陳振中(5)** | 0.046 | 0.099 | 0.188 | 0.204 | 1.00 | 0.125 |
| **陳盡川(6)** | 0.062 | 0.146 | 0.102 | 0.073 | 0.125 | 1.00 |

# 解讀

* **最高相似度**：吳淑瑾(4) ↔ 陳振中(5) = **0.20**，兩人都主打醫療、交通、航空議題，政策語言重疊度最高。
* **次高**：葉竹林(3) ↔ 陳振中(5) = **0.19**，交通、漁業、觀光、青年返鄉方向相近。
* **許智富(1)** 與所有候選人相似度皆低於 0.07，政策語言獨特性最高，主打道路與選制改革，與其他候選人的社會福利、醫療、交通議題較少重疊。
* **周倪安(2) ↔ 陳盡川(6)** = 0.15，兩人都以漁業與農業為核心，但周倪安偏向政策工具（代管辦法、農經學院），陳盡川偏向保育願景。

# 各候選人概念連結

* [許智富](/candidates/hsu-chih-fu.md)
* [周倪安](/candidates/chou-ni-an.md)
* [葉竹林](/candidates/ye-chu-lin.md)
* [吳淑瑾](/candidates/wu-shu-jin.md)
* [陳振中](/candidates/chen-chin-chung.md)
* [陳盡川](/candidates/chen-jin-chuan.md)
