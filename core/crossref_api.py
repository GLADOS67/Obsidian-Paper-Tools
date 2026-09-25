import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from core.cache import load_cache, save_cache
from core.doi import TITLE_NORM_TABLE, is_plausible_doi, process_doi
from core.frontmatter import apply_cited_by, cited_by_fresh
from core.http import get_session, polite_sleep

from config import CPU_CORES, CITE_BY_CACHE, CROSSREF_MAILTO, DOI_TITLE_CACHE
CROSSREF_API_BASE = 'https://api.crossref.org/works'

_LOCK = threading.Lock()
_TITLE_REVERSE: Dict[str, str] = {}
_TITLE_LENS: Dict[str, int] = {}  # 与 _TITLE_REVERSE 同步维护，用于模糊匹配长度上界预剪枝
_FUZZY_THRESHOLD = 0.95

_http = get_session()

_PUBDATE_RE = re.compile(r'(\d{4})/(\d{2})/(\d{2})')


def load_doi_title_cache() -> Dict:
    cache = load_cache(DOI_TITLE_CACHE)
    _rebuild_title_reverse(cache)
    return cache


def save_doi_title_cache(cache: dict) -> None:
    save_cache(DOI_TITLE_CACHE, cache)


def load_cite_by_cache() -> Dict:
    return load_cache(CITE_BY_CACHE)


def save_cite_by_cache(cache: dict) -> None:
    save_cache(CITE_BY_CACHE, cache)


def _norm_title(text: str) -> str:
    """标题规范化：PDF伪影清理 + Unicode引号/破折号统一 + 小写 + 空格/下划线折叠 + 去尾标点。"""
    return re.sub(r'\s+', ' ', text.translate(TITLE_NORM_TABLE)
                  .lower().replace('_', ' ')).strip().rstrip(' .;:')


def _index_title(key: str, doi: str) -> None:
    """setdefault 语义写入标题→DOI 索引，同步记录长度（不覆盖已有项）。"""
    if key not in _TITLE_REVERSE:
        _TITLE_REVERSE[key] = doi
        _TITLE_LENS[key] = len(key)


def _rebuild_title_reverse(cache: dict) -> None:
    _TITLE_REVERSE.clear()
    _TITLE_LENS.clear()
    for doi, val in cache.items():
        if isinstance(val, list) and val:
            title = val[0] if isinstance(val[0], str) else ''
            norm = val[1] if len(val) >= 2 and isinstance(val[1], str) else ''
        elif isinstance(val, str):
            title, norm = val, ''
        else:
            continue
        if title:
            _index_title(norm or _norm_title(title), doi)
            _index_title(title.lower(), doi)


def put_doi_title(cache: dict, doi: str, title: str, lock: threading.Lock = None) -> None:
    """幂等写入 doi → [title, 规范化title]。已存在非空 title 不覆盖，空 title 占位可被填充。

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
    with lock or _LOCK:
        val = cache.get(doi)
        if isinstance(val, list) and val:
            old = val[0] if isinstance(val[0], str) else ''
            if not old and title:
                val[0] = title
                if len(val) >= 2:
                    val[1] = _norm_title(title)
                else:
                    val.append(_norm_title(title))
        elif isinstance(val, str):
            old = val.strip()
            cache[doi] = [old or title, _norm_title(old or title)]
        else:
            cache[doi] = [title, _norm_title(title)] if title else ['', '']
        cur = cache[doi]
        t = cur[0] if isinstance(cur, list) and cur else ''
        if t:
            n = cur[1] if isinstance(cur, list) and len(cur) >= 2 and isinstance(cur[1], str) else ''
            _index_title(n or _norm_title(t), doi)
            _index_title(t.lower(), doi)


def lookup_doi_by_title(title: str, cache: dict = None,
                        lock: threading.Lock = None) -> Optional[str]:
    """仅查 Doi_Title_cache：规范化精确命中 → 长标题模糊(≥0.95)，不发 API。"""
    if not title:
        return None
    norm = _norm_title(title)
    if len(norm) < 4:
        return None
    with lock or _LOCK:
        if hit := _TITLE_REVERSE.get(norm):
            return hit
        if len(norm) >= 20:
            # ratio ≤ quick_ratio ≤ 2·min(a,b)/(a+b)，长度越界候选必低于阈值，直接跳过
            ln, t = len(norm), _FUZZY_THRESHOLD
            lo, hi = ln * t / (2.0 - t), ln * (2.0 - t) / t
            best, best_score = None, 0.0
            for cand, doi in _TITLE_REVERSE.items():
                lc = _TITLE_LENS[cand]
                if lc < 10 or lc < lo or lc > hi:
                    continue
                sm = SequenceMatcher(None, norm, cand)
                if sm.quick_ratio() < t:
                    continue
                score = sm.ratio()
                if score > best_score:
                    best, best_score = doi, score
            if best and best_score >= _FUZZY_THRESHOLD:
                return best
    return None


def _api_get(url: str, params: dict = None, timeout: int = 10) -> Optional[dict]:
    try:
        resp = _http.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def get_doi_from_citation(citation_text: str, cache: dict = None,
                          lock: threading.Lock = None) -> Optional[Tuple[str, str]]:
    """标题/引用文本 → DOI。先查 Doi_Title_cache（精确→模糊0.95），miss 才请求 Crossref。"""
    cache = cache or {}
    cached_doi = lookup_doi_by_title(citation_text, cache, lock)
    if cached_doi:
        with lock or _LOCK:
            val = cache.get(cached_doi)
        title = val[0] if isinstance(val, list) and val and isinstance(val[0], str) else ''
        print(f'缓存命中标题→DOI: {cached_doi}')
        return cached_doi, title
    data = _api_get(CROSSREF_API_BASE, params={
        'rows': 1, 'mailto': CROSSREF_MAILTO, 'query': citation_text,
    })
    polite_sleep()
    if data is None:
        print(f'Crossref API请求失败: {citation_text[:80]}')
        return None
    items = data.get('message', {}).get('items', [])
    if not items:
        print(f'Crossref无匹配结果: {citation_text[:80]}')
        return None
    doi = items[0].get('DOI')
    title = (items[0].get('title') or [''])[0]
    if not doi:
        print(f'Crossref结果无DOI: {title[:80]}')
        return None
    put_doi_title(cache, doi, title, lock)
    return doi, title


def _ref_entry(ref: dict, doi: str) -> Dict:
    return {'text': ref.get('unstructured', ''),
            'doi': process_doi(doi)[0],
            'title': ref.get('article-title') or ref.get('volume-title', '')}


def fetch_references(doi: str, cache: dict = None) -> Tuple[List[Dict], Optional[int]]:
    """拉取Crossref参考文献，每条 ref 的 doi:title 贡献进 Doi_Title_cache。

    返回 (refs, year)：year 来自消息 issued.date-parts[0][0]（无则 None）；refs 不缓存。
    """
    cache = cache or {}
    print(f'正在从Crossref拉取数据: {doi}')
    data = _api_get(f'{CROSSREF_API_BASE}/{doi}', timeout=100)
    if not data:
        return [], None
    msg = data.get('message', {})
    try:
        year = msg.get('issued', {}).get('date-parts', [[None]])[0][0]
    except Exception:
        year = None

    refs_with_doi = []
    refs_missing = []
    for ref in msg.get('reference', []):
        if ref_doi := ref.get('DOI'):
            refs_with_doi.append(_ref_entry(ref, ref_doi))
        elif ref.get('unstructured'):
            refs_missing.append(ref)

    for r in refs_with_doi:
        put_doi_title(cache, r['doi'], r['title'], _LOCK)

    if refs_missing:
        print(f'并行补全 {len(refs_missing)} 个缺失DOI...')
        with ThreadPoolExecutor(max_workers=min(CPU_CORES * 2, 4)) as ex:
            futures = {ex.submit(get_doi_from_citation, r['unstructured'], cache, _LOCK): r
                       for r in refs_missing}
            for fut in as_completed(futures):
                ref = futures[fut]
                if result := fut.result():
                    print(f'补全成功: {result[0]}')
                    refs_with_doi.append(_ref_entry(ref, result[0]))

    print(f'拉取到 {len(refs_with_doi)} 条参考文献')
    return refs_with_doi, year


def get_cited_by_pubmed(doi: str, cite_by_cache: dict = None,
                        doi_title_cache: dict = None,
                        existing_dois: set = None, max_rows: int = 10) -> Tuple[int, List[str]]:
    """PubMed近5年施引查询。Cite_By_cache 存全量列表（无计数），读取时过滤/截断；
    esummary 返回的 citing 论文 doi:title 贡献进 Doi_Title_cache。"""
    cite_by_cache = cite_by_cache or {}
    doi_title_cache = doi_title_cache or {}
    existing_dois = existing_dois or set()

    with _LOCK:
        cached = cite_by_cache.get(doi)
    if cached is not None:
        return len(cached), [d for d in cached if d.lower() not in existing_dois][:max_rows]

    def _finalize(all_dois: List[str]) -> Tuple[int, List[str]]:
        with _LOCK:
            cite_by_cache[doi] = all_dois
        return len(all_dois), [d for d in all_dois if d.lower() not in existing_dois][:max_rows]

    base = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils'
    data = _api_get(f'{base}/esearch.fcgi',
                    params={'db': 'pubmed', 'term': f'{doi}[doi]', 'retmode': 'json'})
    if data is None:
        return 0, []
    pmids = data.get('esearchresult', {}).get('idlist', [])
    if not pmids:
        return _finalize([])
    polite_sleep()

    data = _api_get(f'{base}/elink.fcgi',
                    params={'dbfrom': 'pubmed', 'id': pmids[0],
                            'linkname': 'pubmed_pubmed_citedin', 'retmode': 'json'})
    if data is None:
        return _finalize([])
    linksets = data.get('linksets', [])
    links = [l for db in (linksets and linksets[0].get('linksetdbs', []) or []) for l in db.get('links', [])]
    if not links:
        return _finalize([])

    cutoff = datetime.now() - timedelta(days=5 * 365)
    citing = []
    for i in range(0, len(links), 100):
        batch = links[i:i + 100]
        polite_sleep()
        results = _api_get(f'{base}/esummary.fcgi',
                           params={'db': 'pubmed', 'id': ','.join(batch), 'retmode': 'json'})
        if results is None:
            continue
        results = results.get('result', {})
        for pmid_id in batch:
            item = results.get(str(pmid_id))
            if not item:
                continue
            m = _PUBDATE_RE.match(item.get('sortpubdate', ''))
            if not m:
                continue
            try:
                pubdate = datetime(*map(int, m.groups()))
            except ValueError:
                continue
            if pubdate < cutoff:
                continue
            doi_val = next((aid.get('value') for aid in item.get('articleids', [])
                            if aid.get('idtype') == 'doi'), None)
            if doi_val:
                put_doi_title(doi_title_cache, doi_val, item.get('title') or '', _LOCK)
                citing.append((pubdate, process_doi(doi_val)[0]))
    citing.sort(key=lambda x: x[0], reverse=True)
    return _finalize([d for _, d in citing])


def refresh_cited_by(fm: dict, main_doi: str, cite_by_cache: dict,
                     doi_title_cache: dict, existing_dois: set = None,
                     max_rows: int = 10) -> Optional[List[str]]:
    """cited_by_date 未过期则跳过（返回 None）；否则查 PubMed 并写回 fm，返回新增 DOI 列表。

    合并 cited_by.py / pdf2md.py 中重复的「新鲜度检查 → 查询 → apply_cited_by」逻辑。
    """
    if not main_doi or cited_by_fresh(fm):
        return None
    _, citing_dois = get_cited_by_pubmed(main_doi, cite_by_cache, doi_title_cache,
                                         existing_dois, max_rows)
    apply_cited_by(fm, citing_dois)
    return citing_dois
