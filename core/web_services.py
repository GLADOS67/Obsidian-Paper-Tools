"""远程网络服务：Crossref works API + PubMed E-utilities（施引查询）+ OpenAlex DOI 元数据。

线上服务层：
  - Crossref：标题→DOI（get_doi_from_citation）、DOI→参考文献（fetch_references）
  - PubMed：DOI→近5年施引（get_cited_by_pubmed）、frontmatter 新鲜度+写回（refresh_cited_by）
  - OpenAlex：DOI→work 元数据（get_work_by_doi，免费 singleton，0成本/次；verify_work_title 在线验证）
  - Cite_By_cache 读写（施引缓存，独立于 title_cache）
标题缓存（Doi_Title_cache）在 core.title_cache，此处写标题缓存统一传 TITLE_LOCK；
施引缓存由本模块 _CITE_LOCK 保护；两锁无嵌套获取，并发语义与原单一锁等价。
"""

import re
import threading
import time
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from itertools import repeat
from typing import Dict, List, Optional, Tuple

from core.cache import load_cache, map_parallel, save_cache
from core.doi import norm_title, process_doi
from core.frontmatter import apply_cited_by, cited_by_fresh
from core.http import get_session, polite_sleep
from core.similarity import ratio_gate_passes
from core.title_cache import TITLE_LOCK, lookup_doi_by_title, put_doi_title

from config import CITE_BY_CACHE, CROSSREF_MAILTO
CROSSREF_API_BASE = 'https://api.crossref.org/works'
OPENALEX_API_BASE = 'https://api.openalex.org'
_OPENALEX_SIM = 0.9   # OpenAlex 在线验证标题最低相似度（与 title_cache verify_doi_title 门控一致）

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


def _openalex_get(path: str, params: dict = None, retries: int = 3) -> Optional[dict]:
    """OpenAlex singleton GET（0成本/次）：429/5xx 指数退避，失败返回 None，永不 raise。"""
    for attempt in range(retries):
        try:
            resp = _http.get(f'{OPENALEX_API_BASE}{path}', params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code not in (429, 500, 502, 503, 504):
                return None
        except Exception:
            pass
        time.sleep(2 ** attempt)
    return None


def get_work_by_doi(doi: str) -> Optional[dict]:
    """OpenAlex 免费 singleton：DOI→work 元数据（0成本/次），失败返回 None。

    纯查询层，不写任何缓存；select 限字段控制响应体积；mailto 提示 OpenAlex 礼貌池。
    """
    if not doi:
        return None
    doi = process_doi(doi)[0]
    return _openalex_get(f'/works/https://doi.org/{doi}', params={
        'select': 'id,doi,title,publication_date,ids,open_access',
        'mailto': CROSSREF_MAILTO,
    })


def verify_work_title(doi: str, title: str) -> bool:
    """OpenAlex 在线交叉验证：DOI 返回标题与给定标题规范化相似度≥0.9（与缓存 verify_doi_title 同门控）。

    缓存验证 miss 时的在线兜底（pdf2md 主DOI定级）；不发缓存、不发其他端点。
    """
    if not doi or not title:
        return False
    work = get_work_by_doi(doi)
    wtitle = (work or {}).get('title')
    if not wtitle:
        return False
    return SequenceMatcher(None, norm_title(title),
                           norm_title(wtitle)).ratio() >= _OPENALEX_SIM


def get_doi_from_citation(citation_text: str, cache: dict = None,
                          lock: threading.Lock = None) -> Optional[Tuple[str, str, str]]:
    """标题/引用文本 → DOI。先查 Doi_Title_cache（精确→模糊0.95），miss 才请求 Crossref。

    返回 (doi, title, source)，source ∈ {'缓存', '联网'}（缓存命中或 Crossref 联网获取）。
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
        return cached_doi, title, '缓存'
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
    return doi, title, '联网'


def lookup_dois_parallel(texts: List[str], cache: dict = None,
                         lock: threading.Lock = None) -> Dict[int, Tuple[str, str, str]]:
    """并行 标题→DOI 补全（共享线程池 map 保序）；返回 {原文索引: (doi,title,source)}，未命中项缺失。

    公共实现（fetch_references / crossref 原各有一份自建 ThreadPoolExecutor 的补全循环，
    复用 core.cache 共享池免每轮重建线程）。
    """
    return {i: r for i, r in enumerate(map_parallel(
        lambda t: get_doi_from_citation(t, cache, lock), texts)) if r}


def _ref_entry(ref: dict, doi: str) -> Dict:
    return {'text': ref.get('unstructured', ''),
            'doi': process_doi(doi)[0],
            'title': ref.get('article-title') or ref.get('volume-title', '')}


def fetch_references(doi: str, cache: dict = None) -> Tuple[List[Dict], Optional[int]]:
    """拉取Crossref参考文献，每条 ref 的 doi:title 贡献进 Doi_Title_cache。

    返回 (refs, year)：year 来自消息 issued.date-parts[0][0]（无则 None）；refs 不缓存。
    """
    cache = cache or {}
    data = _api_get(f'{CROSSREF_API_BASE}/{doi}', timeout=100)
    if not data:
        print(f'Crossref获取失败: {doi}')
        return [], None
    msg = data.get('message', {})
    ctitle = (msg.get('title') or [''])[0] or '(无标题)'
    print(f'从 {ctitle} 获取doi: {doi}')
    try:
        year = msg.get('issued', {}).get('date-parts', [[None]])[0][0]
    except Exception:
        year = None

    refs_with_doi = []
    refs_missing = []
    for ref in msg.get('reference', []):
        if ref_doi := ref.get('DOI'):
            entry = _ref_entry(ref, ref_doi)
            put_doi_title(cache, entry['doi'], entry['title'], TITLE_LOCK)
            refs_with_doi.append(entry)
        elif ref.get('unstructured'):
            refs_missing.append(ref)

    if refs_missing:
        print(f'并行补全 {len(refs_missing)} 个缺失DOI...')
        found = lookup_dois_parallel([r['unstructured'] for r in refs_missing], cache, TITLE_LOCK)
        for i, ref in enumerate(refs_missing):
            if result := found.get(i):
                print(f'补全成功[{result[2]}]: {result[0]}')
                refs_with_doi.append(_ref_entry(ref, result[0]))

    print(f'拉取到 {len(refs_with_doi)} 条参考文献')
    return refs_with_doi, year


def _esummary_batch(base: str, batch: List[str], cutoff: datetime,
                    doi_title_cache: dict) -> List[Tuple[datetime, str]]:
    """单批 esummary 查询 → (pubdate, doi) 列表；标题缓存写入由 TITLE_LOCK 保护。"""
    data = _api_get(f'{base}/esummary.fcgi',
                    params={'db': 'pubmed', 'id': ','.join(batch), 'retmode': 'json'})
    if data is None:
        return []
    results = data.get('result', {})
    citing = []
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
    return citing


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
    batches = [links[i:i + 100] for i in range(0, len(links), 100)]
    polite_sleep()  # 批次查询并行化：批间礼貌延迟合并为一次（结果与串行一致）
    citing = []
    for part in map_parallel(_esummary_batch, repeat(base), batches,
                             repeat(cutoff), repeat(doi_title_cache)):
        citing.extend(part)
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
