"""/s: Crossref REST API (api.crossref.org) & PubMed Entrez E-utilities (eutils.ncbi.nlm.nih.gov).
All calls cached as JSON (crossref_cache.json) to minimize API traffic.
"""
import json
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from core.doi import process_doi

# 【勿改】强制硬编码路径，禁止软链接到 config
CROSSREF_CACHE = Path(r'D:\ResearchFront\DATA\API\crossref_cache.json')
CROSSREF_API_BASE = 'https://api.crossref.org/works'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0'

_http = requests.Session()
_http.headers.update({'User-Agent': USER_AGENT})


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


def get_doi_from_citation(citation_text: str, cache: dict = None) -> Optional[Tuple[str, str]]:
    cache = {} if cache is None else cache
    key = f'cite:{citation_text.strip()}'
    if key in cache:
        val = cache[key]
        if val is None:
            return None
        if isinstance(val, (tuple, list)) and len(val) == 2:
            return (val[0], val[1])
    data = _api_get(CROSSREF_API_BASE, params={
        'rows': 1, 'mailto': 'lik1453529@wmu.edu.cn', 'query': citation_text,
    })
    time.sleep(random.uniform(1.0, 2.0))
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
    cache[key] = result
    return result


def _extract_issued_year(msg: dict) -> Optional[int]:
    # 从Crossref message中提取首发年份: issued.date-parts = [[年, 月, 日]]
    try:
        return msg.get('issued', {}).get('date-parts', [[None]])[0][0]
    except Exception:
        return None


def get_issued_year(doi: str, cache: dict = None) -> Optional[int]:
    # 查询论文首发年份, 优先命中缓存(issued:{doi}), 查不到时缓存None避免重复请求
    cache = {} if cache is None else cache
    key = f'issued:{doi}'
    if key in cache:
        return cache[key]
    data = _api_get(f'{CROSSREF_API_BASE}/{doi}', timeout=30)
    year = _extract_issued_year(data.get('message', {})) if data else None
    cache[key] = year
    return year


def fetch_references(doi: str, cache: dict = None) -> List[Dict]:
    cache = {} if cache is None else cache
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
    # 复用本次请求顺带缓存首发年份, 供get_issued_year免二次请求
    cache[f'issued:{doi}'] = _extract_issued_year(msg)
    refs = []
    for ref in msg.get('reference', []):
        ref_doi = ref.get('DOI')
        ref_text = ref.get('unstructured', '')
        if not ref_doi and ref_text:
            print(f'补全缺失DOI: {ref_text[:50]}...')
            result = get_doi_from_citation(ref_text, cache)
            ref_doi = result[0] if result else None
            if ref_doi:
                print(f'补全成功: {ref_doi}')
        if ref_doi:
            refs.append({
                'text': ref_text,
                'doi': process_doi(ref_doi)[0],
                'title': ref.get('article-title') or ref.get('volume-title', ''),
            })
    print(f'拉取到 {len(refs)} 条参考文献')
    cache[refs_key] = refs
    return refs


def get_cited_by_pubmed(doi: str, cache: dict = None,
                        existing_dois: set = None, max_rows: int = 10) -> Tuple[int, List[str]]:
    cache = {} if cache is None else cache
    existing_dois = set() if existing_dois is None else existing_dois
    count_key, list_key = f'pm_citedby:{doi}', f'pm_citedby_list:{doi}'

    def _finalize(total: int, all_dois: List[str]) -> Tuple[int, List[str]]:
        cache[count_key] = total
        cache[list_key] = all_dois
        new_dois = [d for d in all_dois if d.lower() not in existing_dois]
        return total, new_dois[:max_rows]

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
    time.sleep(random.uniform(1.0, 2.0))

    try:
        resp = _http.get(f'{base}/elink.fcgi', params={'dbfrom': 'pubmed', 'id': pmids[0], 'linkname': 'pubmed_pubmed_citedin', 'retmode': 'json'}, timeout=10)
        resp.raise_for_status()
        linksets = resp.json().get('linksets', [])
    except Exception:
        return _finalize(0, [])
    links = []
    if linksets:
        for db in linksets[0].get('linksetdbs', []):
            links.extend(db.get('links', []))
    if not links:
        return _finalize(0, [])

    cutoff = datetime.now() - timedelta(days=5 * 365)
    citing = []
    for i in range(0, len(links), 100):
        batch = links[i:i + 100]
        time.sleep(random.uniform(1.0, 2.0))
        try:
            resp = _http.get(f'{base}/esummary.fcgi', params={'db': 'pubmed', 'id': ','.join(batch), 'retmode': 'json'}, timeout=10)
            resp.raise_for_status()
            results = resp.json().get('result', {})
        except Exception:
            time.sleep(random.uniform(1.0, 2.0))
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
    citing.sort(key=lambda x: x[0], reverse=True)
    return _finalize(len(links), [d for _, d in citing])
