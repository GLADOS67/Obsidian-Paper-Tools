"""/s: Crossref REST API (api.crossref.org) & PubMed Entrez E-utilities (eutils.ncbi.nlm.nih.gov).
- fetch_references: GET /works/{doi} → extract references with DOI + text.
- get_doi_from_citation: GET /works?query= → resolve citation text to DOI.
- get_cited_by_pubmed: esearch → elink (pubmed_pubmed_citedin) → esummary → citing DOIs.
All calls cached as JSON (crossref_cache.json) to minimize API traffic.
"""
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from core.doi import process_doi

CACHE_FILE = Path(r'D:\ResearchFront\DATA\API\crossref_cache.json')
CROSSREF_API_BASE = 'https://api.crossref.org/works'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0'

_http = requests.Session()
_http.headers.update({'User-Agent': USER_AGENT})


def load_cache() -> Dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def save_cache(cache: dict) -> None:
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass


def _api_get(url: str, params: dict = None, timeout: int = 10) -> Optional[dict]:
    try:
        resp = _http.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _valid_citation_cache(val: Any) -> Optional[Tuple[str, str]]:
    if val is None:
        return None
    if isinstance(val, (tuple, list)) and len(val) == 2:
        return (val[0], val[1])
    return None


def get_doi_from_citation(citation_text: str, cache: Optional[dict] = None) -> Optional[Tuple[str, str]]:
    if cache is None:
        cache = globals().get('_cite_cache', {})
    key = f'cite:{citation_text.strip()}'
    if key in cache:
        cached = _valid_citation_cache(cache[key])
        if cached is not None or cache[key] is None:
            return cached
    data = _api_get(CROSSREF_API_BASE, params={
        'rows': 1, 'mailto': 'lik1453529@wmu.edu.cn', 'query': citation_text,
    })
    items = (data or {}).get('message', {}).get('items', [])
    if not items:
        cache[key] = None
        return None
    doi = items[0].get('DOI')
    title = (items[0].get('title') or [''])[0]
    if doi:
        time.sleep(1)
    result = (doi, title) if doi else None
    cache[key] = result
    return result


def fetch_references(doi: str, cache: Optional[dict] = None) -> List[Dict]:
    if cache is None:
        cache = {}
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
    cited_by = msg.get('is-referenced-by-count', 0)
    refs = []
    for ref in msg.get('reference', []):
        ref_text = ref.get('unstructured', '')
        ref_doi = ref.get('DOI')
        if not ref_doi and ref_text:
            print(f'补全缺失DOI: {ref_text[:50]}...')
            result = get_doi_from_citation(ref_text, cache)
            ref_doi = result[0] if result else None
            if ref_doi:
                print(f'补全成功: {ref_doi}')
        if ref_doi:
            display_doi, _ = process_doi(ref_doi)
            ref_title = ref.get('article-title') or ref.get('volume-title', '')
            refs.append({'text': ref_text, 'doi': display_doi, 'title': ref_title})
    print(f'拉取到 {len(refs)} 条参考文献')
    cache[refs_key] = refs
    cache[citedby_key] = cited_by
    return refs


def get_cited_by_pubmed(doi: str, cache: Optional[dict] = None,
                        existing_dois: set = None, max_rows: int = 10) -> Tuple[int, List[str]]:
    if cache is None:
        cache = {}
    if existing_dois is None:
        existing_dois = set()
    count_key = f'pm_citedby:{doi}'
    list_key = f'pm_citedby_list:{doi}'

    def _finalize(total: int, all_dois: List[str]) -> Tuple[int, List[str]]:
        cache[count_key] = total
        cache[list_key] = all_dois
        return total, [d for d in all_dois if d.lower() not in existing_dois][:max_rows]

    if count_key in cache and list_key in cache:
        return _finalize(cache[count_key], cache[list_key])

    base = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils'
    try:
        resp = _http.get(f'{base}/esearch.fcgi', params={'db': 'pubmed', 'term': f'{doi}[doi]', 'retmode': 'json'}, timeout=10)
        resp.raise_for_status()
        pmids = resp.json().get('esearchresult', {}).get('idlist', [])
    except Exception:
        return 0, []
    if not pmids:
        return _finalize(0, [])
    time.sleep(0.5)

    try:
        resp = _http.get(f'{base}/elink.fcgi', params={'dbfrom': 'pubmed', 'id': pmids[0], 'linkname': 'pubmed_pubmed_citedin', 'retmode': 'json'}, timeout=10)
        resp.raise_for_status()
        linksets = resp.json().get('linksets', [])
    except Exception:
        return _finalize(0, [])
    links = [link for db in (linksets[0].get('linksetdbs', []) if linksets else [])
             for link in db.get('links', [])]
    time.sleep(0.5)
    if not links:
        return _finalize(0, [])

    cutoff = datetime.now() - timedelta(days=5 * 365)
    citing = []
    for i in range(0, len(links), 100):
        batch = links[i:i + 100]
        try:
            resp = _http.get(f'{base}/esummary.fcgi', params={'db': 'pubmed', 'id': ','.join(batch), 'retmode': 'json'}, timeout=10)
            resp.raise_for_status()
            results = resp.json().get('result', {})
        except Exception:
            time.sleep(0.5)
            continue
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
        time.sleep(0.5)
    citing.sort(key=lambda x: x[0], reverse=True)
    return _finalize(len(links), [d for _, d in citing])
