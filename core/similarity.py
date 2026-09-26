"""共享模糊匹配工具：SequenceMatcher 长度上界预剪枝。

ratio ≤ quick_ratio ≤ 2·min(a,b)/(a+b)，长度越界的候选必低于阈值，
无需构造 SequenceMatcher 即可跳过（跨 crossref_api / obsidian_path / match 复用）。
"""


def ratio_gate_passes(la: int, lb: int, threshold: float) -> bool:
    """2·min(la,lb) ≥ threshold·(la+lb) 时候选长度才可能达到阈值。"""
    return 2.0 * min(la, lb) >= threshold * (la + lb)
