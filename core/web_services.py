"""远程网络服务：Crossref works API + PubMed E-utilities（施引查询）。

线上服务层：
  - Crossref：标题→DOI（get_doi_from_citation）、DOI→参考文献（fetch_references）
  - PubMed：DOI→近5年施引（get_cited_by_pubmed）、frontmatter 新鲜度+写回（refresh_cited_by）
  - Cite_By_cache 读写（施引缓存，独立于 title_cache）
标题缓存（Doi_Title_cache）在 core.title_cache，此处写标题缓存统一传 TITLE_LOCK；
施引缓存由本模块 _CITE_LOCK 保护；两锁无嵌套获取，并发语义与原单一锁等价。
"""

import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from core.cache import load_cache, save_cache
from core.doi import norm_title, process_doi
from core.frontmatter import apply_cited_by, cited_by_fresh
from core.http import get_session, polite_sleep
from core.similarity import ratio_gate_passes
from core.title_cache import TITLE_LOCK, lookup_doi_by_title, put_doi_title

from config import CPU_CORES, CITE_BY_CACHE, CROSSREF_MAILTO
CROSSREF_API_BASE = 'https://api.crossref.org/works'

_CITE_LOCK = threading.Lock()
_CROSSREF_SIM = 0.5   # Crossref 返回标题 vs 引用文本的最低相似度（与 pmce _TITLE_SIM 一致）

_http = get_session()

_PUBDATE_RE = re.compile(r'(\d{4})/(\d{2})/(\d{2})')


def load_cite_by_cache() -> Dict:
    return load_cache(CITE_BY_CACHE)


def save_cite_by_cache(cache: dict) -> None:
    save_cache(CITE_BY_CACHE, cache)


def _api_get(url: str, params: dict = None, timeout: int = 10) -> Optional[dict]:
    try:
        resp = _http.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def get_doi_from_citation(citation_text: str, cache: dict = None,
                          lock: threading.Lock = None) -> Optional[Tuple[str, str]]:
    """标题/引用文本 → DOI。先查 Doi_Title_cache（精确→模糊0.95），miss 才请求 Crossref。

    Crossref 返回结果经相似度门控（≥_CROSSREF_SIM 或子串命中）才接受，
    防止 query.title 误匹配把类似标题挂到错误 DOI 上（污染源头）。
    """
    cache = cache or {}
    cached_doi = lookup_doi_by_title(citation_text, cache, lock)
    if cached_doi:
        with lock or TITLE_LOCK:
            val = cache.get(cached_doi)
        title = val[0] if isinstance(val, list) and val and isinstance(val[0], str) else ''
        print(f'缓存命中标题→DOI: {cached_doi}')
        return cached_doi, title
    norm_cit = norm_title(citation_text)
    if len(norm_cit) < 4:
        return None
    data = _api_get(CROSSREF_API_BASE, params={
        'rows': 3, 'mailto': CROSSREF_MAILTO, 'query.title': citation_text,
    })
    polite_sleep()
    if data is None:
        print(f'Crossref API请求失败: {citation_text[:80]}')
        return None
    best = None
    for item in data.get('message', {}).get('items', []):
        ct = (item.get('title') or [''])[0]
        if not ct:
            continue
        norm_ct = norm_title(ct)
        if not ratio_gate_passes(len(norm_cit), len(norm_ct), _CROSSREF_SIM):
            continue
        if SequenceMatcher(None, norm_cit, norm_ct).ratio() >= _CROSSREF_SIM \
                or norm_ct in norm_cit or norm_cit in norm_ct:
            best = item
            break
    if best is None:
        print(f'Crossref 无高置信匹配（门控拒绝，防误配）: {citation_text[:80]}')
        return None
    doi = best.get('DOI')
    title = (best.get('title') or [''])[0]
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
        put_doi_title(cache, r['doi'], r['title'], TITLE_LOCK)

    if refs_missing:
        print(f'并行补全 {len(refs_missing)} 个缺失DOI...')
        with ThreadPoolExecutor(max_workers=min(CPU_CORES * 2, 4)) as ex:
            futures = {ex.submit(get_doi_from_citation, r['unstructured'], cache, TITLE_LOCK): r
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

    with _CITE_LOCK:
        cached = cite_by_cache.get(doi)
    if cached is not None:
        return len(cached), [d for d in cached if d.lower() not in existing_dois][:max_rows]

    def _finalize(all_dois: List[str]) -> Tuple[int, List[str]]:
        with _CITE_LOCK:
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
                put_doi_title(doi_title_cache, doi_val, item.get('title') or '', TITLE_LOCK)
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
