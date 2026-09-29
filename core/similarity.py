"""共享模糊匹配工具：SequenceMatcher 长度上界预剪枝。

ratio ≤ quick_ratio ≤ 2·min(a,b)/(a+b)，长度越界的候选必低于阈值，
无需构造 SequenceMatcher 即可跳过（跨 title_cache / obsidian_path / match 复用）。

长度分桶：候选按 长度//BUCKET_WIDTH 分桶，检索时只遍历能通过 ratio_gate
的桶区间，大候选集下候选数降至 ~1/10（bucket_candidates 产出超集，调用方仍按 gate 精确过滤）。
"""

import math

BUCKET_WIDTH = 10


def ratio_gate_passes(la: int, lb: int, threshold: float) -> bool:
    """2·min(la,lb) ≥ threshold·(la+lb) 时候选长度才可能达到阈值。"""
    return 2.0 * min(la, lb) >= threshold * (la + lb)


def bucket_index(items, len_of):
    """items → {长度//BUCKET_WIDTH: [item, ...]} 长度分桶索引（一次构建，检索复用）。"""
    buckets = {}
    for it in items:
        buckets.setdefault(len_of(it) // BUCKET_WIDTH, []).append(it)
    return buckets


def bucket_candidates(buckets, la: int, threshold: float):
    """遍历可能与长度 la 候选通过 ratio_gate 的桶区间。

    通过 gate 的候选长度 lb 必落在 [t·la/(2-t), la·(2-t)/t]，其所在桶
    必在对应桶号区间内；区间外候选由调用方再次按 ratio_gate_passes 精确过滤。
    """
    lo = math.floor(threshold * la / (2.0 - threshold) / BUCKET_WIDTH - 1e-9)
    hi = math.floor(la * (2.0 - threshold) / threshold / BUCKET_WIDTH + 1e-9)
    for b in range(lo, hi + 1):
        yield from buckets.get(b, ())
