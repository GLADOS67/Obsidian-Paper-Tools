"""/s: Crossref API + PubMed E-utilities client for DOI references and cited-by."""

import json
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import nullcontext
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from core.doi import process_doi

from config import CROSSREF_CACHE, CROSSREF_MAILTO, USER_AGENT
CROSSREF_API_BASE = 'https://api.crossref.org/works'

_http = requests.Session()
_http.headers.update({'User-Agent': USER_AGENT})


def _polite_sleep(lo: float = 1.0, hi: float = 2.0) -> None:
    time.sleep(random.uniform(lo, hi))


def load_cache() -> Dict:
    try:
        return json.loads(CROSSREF_CACHE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def save_cache(cache: dict) -> None:
    try:
        CROSSREF_CACHE.parent.mkdir(parents=True, exist_ok=True)
        CROSSREF_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass


def _api_get(url: str, params: dict = None, timeout: int = 10) -> Optional[dict]:
    try:
        resp = _http.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _lookup_cache(key: str, cache: dict, lock: threading.Lock = None):
    with lock or nullcontext():
        val = cache.get(key)
    return (val[0], val[1]) if isinstance(val, (tuple, list)) and len(val) == 2 else None


def _set_cache(key: str, value, cache: dict, lock: threading.Lock = None):
    with lock or nullcontext():
        cache[key] = value


def get_doi_from_citation(citation_text: str, cache: dict = None,
                         lock: threading.Lock = None) -> Optional[Tuple[str, str]]:
    cache = cache or {}
    key = f'cite:{citation_text.strip()}'
    cached = _lookup_cache(key, cache, lock)
    if cached is not None:
        return cached
    data = _api_get(CROSSREF_API_BASE, params={
        'rows': 1, 'mailto': CROSSREF_MAILTO, 'query': citation_text,
    })
    _polite_sleep()
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
    result = (doi, title) if doi else None
    _set_cache(key, result, cache, lock)
    return result


def _extract_issued_year(msg: dict) -> Optional[int]:
    # 从Crossref message中提取首发年份: issued.date-parts = [[年, 月, 日]]
    try:
        return msg.get('issued', {}).get('date-parts', [[None]])[0][0]
    except Exception:
        return None


def get_issued_year(doi: str, cache: dict = None) -> Optional[int]:
    cache = cache or {}
    key = f'issued:{doi}'
    if key in cache:
        return cache[key]
    data = _api_get(f'{CROSSREF_API_BASE}/{doi}', timeout=30)
    year = _extract_issued_year(data.get('message', {})) if data else None
    cache[key] = year
    return year


def _ref_entry(ref: dict, doi: str) -> Dict:
    return {'text': ref.get('unstructured', ''),
            'doi': process_doi(doi)[0],
            'title': ref.get('article-title') or ref.get('volume-title', '')}


def fetch_references(doi: str, cache: dict = None) -> List[Dict]:
    cache = cache or {}
    refs_key, citedby_key = doi, f'citedby:{doi}'
    cached_refs = cache.get(refs_key)
    if cached_refs is not None and citedby_key in cache:
        print(f'使用缓存的参考文献: {doi}')
        return cached_refs
    print(f'正在从Crossref拉取数据: {doi}')
    data = _api_get(f'{CROSSREF_API_BASE}/{doi}', timeout=100)
    if not data:
        return []
    msg = data.get('message', {})
    cache[citedby_key] = msg.get('is-referenced-by-count', 0)
    cache[f'issued:{doi}'] = _extract_issued_year(msg)

    refs_with_doi = []
    refs_missing = []
    for ref in msg.get('reference', []):
        if ref_doi := ref.get('DOI'):
            refs_with_doi.append(_ref_entry(ref, ref_doi))
        elif ref.get('unstructured'):
            refs_missing.append(ref)

    if refs_missing:
        lock = threading.Lock()
        print(f'并行补全 {len(refs_missing)} 个缺失DOI...')
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(get_doi_from_citation, r['unstructured'], cache, lock): r
                       for r in refs_missing}
            for fut in as_completed(futures):
                ref = futures[fut]
                if result := fut.result():
                    print(f'补全成功: {result[0]}')
                    refs_with_doi.append(_ref_entry(ref, result[0]))

    print(f'拉取到 {len(refs_with_doi)} 条参考文献')
    cache[refs_key] = refs_with_doi
    return refs_with_doi


def get_cited_by_pubmed(doi: str, cache: dict = None,
                        existing_dois: set = None, max_rows: int = 10) -> Tuple[int, List[str]]:
    cache = cache or {}
    existing_dois = existing_dois or set()
    count_key, list_key = f'pm_citedby:{doi}', f'pm_citedby_list:{doi}'

    def _fresh(all_dois: List[str]) -> List[str]:
        return [d for d in all_dois if d.lower() not in existing_dois][:max_rows]

    if count_key in cache and list_key in cache:
        return cache[count_key], _fresh(cache[list_key])

    def _finalize(total: int, all_dois: List[str]) -> Tuple[int, List[str]]:
        cache[count_key], cache[list_key] = total, all_dois
        return total, _fresh(all_dois)

    base = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils'
    data = _api_get(f'{base}/esearch.fcgi',
                    params={'db': 'pubmed', 'term': f'{doi}[doi]', 'retmode': 'json'})
    if data is None:
        return 0, []
    pmids = data.get('esearchresult', {}).get('idlist', [])
    if not pmids:
        return _finalize(0, [])
    _polite_sleep()

    data = _api_get(f'{base}/elink.fcgi',
                    params={'dbfrom': 'pubmed', 'id': pmids[0],
                            'linkname': 'pubmed_pubmed_citedin', 'retmode': 'json'})
    if data is None:
        return _finalize(0, [])
    linksets = data.get('linksets', [])
    links = [l for db in (linksets and linksets[0].get('linksetdbs', []) or []) for l in db.get('links', [])]
    if not links:
        return _finalize(0, [])

    cutoff = datetime.now() - timedelta(days=5 * 365)
    citing = []
    for i in range(0, len(links), 100):
        batch = links[i:i + 100]
        _polite_sleep()
        results = _api_get(f'{base}/esummary.fcgi',
                           params={'db': 'pubmed', 'id': ','.join(batch), 'retmode': 'json'})
        if results is None:
            continue
        results = results.get('result', {})
        for pmid_id in batch:
            item = results.get(str(pmid_id))
            if not item:
                continue
            try:
                pubdate = datetime.strptime(item.get('sortpubdate', '')[:10], '%Y/%m/%d')
            except Exception:
                continue
            if pubdate < cutoff:
                continue
            doi_val = next((aid.get('value') for aid in item.get('articleids', [])
                            if aid.get('idtype') == 'doi'), None)
            if doi_val:
                citing.append((pubdate, process_doi(doi_val)[0]))
    citing.sort(key=lambda x: x[0], reverse=True)
    return _finalize(len(links), [d for _, d in citing])
