"""Doi_Title_cache 本地缓存：DOI→标题 持久化 + 内存标题反向索引（精确/模糊查询，不发 API）。

纯缓存层；标题锁 TITLE_LOCK 供跨模块显式传入
（put_doi_title / lookup_doi_by_title 的 lock 参数为 None 时用内部锁）。
"""

import threading
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from core.cache import load_cache, save_cache
from core.doi import is_plausible_doi, norm_title, process_doi
from core.similarity import BUCKET_WIDTH, bucket_candidates, ratio_gate_passes

from config import DOI_TITLE_CACHE

TITLE_LOCK = threading.Lock()
_TITLE_REVERSE: Dict[str, Tuple[str, int]] = {}  # 规范化标题 → (doi, 标题长度)，长度用于模糊匹配上界预剪枝
_TITLE_BUCKETS: Dict[int, List[str]] = {}  # len(key)//BUCKET_WIDTH → 标题键（模糊匹配桶预筛，与 _TITLE_REVERSE 同步维护）
_FUZZY_THRESHOLD = 0.95
_EXACT_SIM = 0.9  # lookup 精确命中后 title/norm 一致性下限（防畸形条目）


def load_doi_title_cache() -> Dict:
    cache = load_cache(DOI_TITLE_CACHE)
    _rebuild_title_reverse(cache)
    return cache


def save_doi_title_cache(cache: dict) -> None:
    save_cache(DOI_TITLE_CACHE, cache)


def _index_title(key: str, doi: str) -> None:
    """setdefault 语义写入标题→(DOI,长度) 索引（不覆盖已有项），同步维护长度分桶。"""
    if key not in _TITLE_REVERSE:
        _TITLE_REVERSE[key] = (doi, len(key))
        _TITLE_BUCKETS.setdefault(len(key) // BUCKET_WIDTH, []).append(key)


def _rebuild_title_reverse(cache: dict) -> None:
    _TITLE_REVERSE.clear()
    _TITLE_BUCKETS.clear()
    for doi, val in cache.items():
        if isinstance(val, list) and val:
            title = val[0] if isinstance(val[0], str) else ''
            norm = val[1] if len(val) >= 2 and isinstance(val[1], str) else ''
        elif isinstance(val, str):
            title, norm = val, ''
        else:
            continue
        if title:
            _index_title(norm or norm_title(title), doi)
            _index_title(title.lower(), doi)


def put_doi_title(cache: dict, doi: str, title: str, lock: threading.Lock = None,
                  force: bool = False) -> None:
    """幂等写入 doi → [title, 规范化title]。已存在非空 title 默认不覆盖，空 title 占位可被填充；
    force=True（PMCE 高可信源）允许覆盖已有非空标题。

    写入前统一审核：is_plausible_doi 不通过则拒绝（防截断/拼接错误DOI混入缓存）。
    """
    if not doi:
        return
    doi = process_doi(doi)[0]
    if not is_plausible_doi(doi):
        print(f'⚠️ 拒绝写入可疑DOI: {doi} {title[:40]}')
        return
    title = (title or '').strip()
    # 标题含 wikilink 包裹（[[...]]）是历史遗留格式，非真实标题，拒绝写入缓存
    if '[' in title or ']' in title:
        print(f'⚠️ 拒绝写入wikilink格式标题: {doi} {title[:40]}')
        return
    with lock or TITLE_LOCK:
        val = cache.get(doi)
        if isinstance(val, list) and val:
            old = val[0] if isinstance(val[0], str) else ''
            if (force and title) or (not old and title):
                val[0] = title
                if len(val) >= 2:
                    val[1] = norm_title(title)
                else:
                    val.append(norm_title(title))
        elif isinstance(val, str):
            old = val.strip()
            cache[doi] = [old or title, norm_title(old or title)]
        else:
            cache[doi] = [title, norm_title(title)] if title else ['', '']
        cur = cache[doi]
        t = cur[0] if isinstance(cur, list) and cur else ''
        if t:
            n = cur[1] if isinstance(cur, list) and len(cur) >= 2 and isinstance(cur[1], str) else ''
            _index_title(n or norm_title(t), doi)
            _index_title(t.lower(), doi)


def lookup_doi_by_title(title: str, cache: dict = None,
                        lock: threading.Lock = None) -> Optional[str]:
    """仅查 Doi_Title_cache：规范化精确命中 → 长标题模糊(≥0.95)，不发 API。"""
    if not title:
        return None
    norm = norm_title(title)
    if len(norm) < 4:
        return None
    with lock or TITLE_LOCK:
        if hit := _TITLE_REVERSE.get(norm):
            hit_doi = hit[0]
            val = cache.get(hit_doi) if cache is not None else None
            cached_title = (val[0] if isinstance(val, list) and val and isinstance(val[0], str) else
                            val if isinstance(val, str) else '')
            if cached_title and SequenceMatcher(None, norm, norm_title(cached_title)).ratio() >= _EXACT_SIM:
                return hit_doi
            # title/norm 不一致（畸形条目）→ 视为可疑，落入模糊匹配
        if len(norm) >= 20:
            # 长度分桶预筛（候选降至 ~1/10），命中桶内仍按原门控逐条过滤，结果与全量扫描一致
            best, best_score = None, 0.0
            for cand in bucket_candidates(_TITLE_BUCKETS, len(norm), _FUZZY_THRESHOLD):
                doi, clen = _TITLE_REVERSE[cand]
                if clen < 10 or not ratio_gate_passes(len(norm), clen, _FUZZY_THRESHOLD):
                    continue
                sm = SequenceMatcher(None, norm, cand)
                if sm.quick_ratio() < _FUZZY_THRESHOLD:
                    continue
                score = sm.ratio()
                if score > best_score:
                    best, best_score = doi, score
            if best and best_score >= _FUZZY_THRESHOLD:
                return best
    return None
