"""/s: Crossref cache (crossref_cache.json) cleaner for Obsidian-Paper-Tools.
Removes cite:null entries, normalizes DOI keys via process_doi, deduplicates merged
keys (citedby:, pm_citedby:, DOI references). Works with core/doi.py and core/crossref_api.py.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.doi import process_doi, is_plausible_doi
from core.crossref_api import CROSSREF_CACHE, load_cache, save_cache


def _clean_doi_key(raw: str):
    display, safe = process_doi(raw)
    return display


def _should_keep_doi(doi: str) -> bool:
    return bool(doi) and is_plausible_doi(doi)


DOI_PREFIX_RE = r'^(10\.\d{4,9}/)'

CITEDBY_PREFIX = 'citedby:'
PM_CITEDBY_PREFIX = 'pm_citedby:'
PM_CITEDBY_LIST_PREFIX = 'pm_citedby_list:'


def clean_cache(cache: dict) -> dict:
    cleaned = {}
    merge_log = []
    removed_log = []

    for key, value in cache.items():
        if key.startswith('cite:'):
            if value is None:
                removed_log.append(('cite:null', key))
                continue
            if isinstance(value, list) and len(value) >= 1:
                raw_doi = value[0]
                clean_doi = _clean_doi_key(raw_doi) if isinstance(raw_doi, str) else None
                if clean_doi and clean_doi != raw_doi:
                    value = [clean_doi] + list(value[1:])
            cleaned[key] = value
            continue

        if key.startswith(PM_CITEDBY_LIST_PREFIX):
            doi_part = key[len(PM_CITEDBY_LIST_PREFIX):]
            clean_doi = _clean_doi_key(doi_part)
            new_key = f'{PM_CITEDBY_LIST_PREFIX}{clean_doi}'
            if isinstance(value, list):
                value = [_clean_doi_key(d) for d in value if isinstance(d, str)]
        elif key.startswith(PM_CITEDBY_PREFIX):
            doi_part = key[len(PM_CITEDBY_PREFIX):]
            clean_doi = _clean_doi_key(doi_part)
            new_key = f'{PM_CITEDBY_PREFIX}{clean_doi}'
        elif key.startswith(CITEDBY_PREFIX):
            doi_part = key[len(CITEDBY_PREFIX):]
            clean_doi = _clean_doi_key(doi_part)
            new_key = f'{CITEDBY_PREFIX}{clean_doi}'
        elif key.startswith('10.'):
            clean_doi = _clean_doi_key(key)
            new_key = clean_doi
            if isinstance(value, list):
                for ref in value:
                    if isinstance(ref, dict) and 'doi' in ref and isinstance(ref['doi'], str):
                        ref['doi'] = _clean_doi_key(ref['doi'])
        else:
            cleaned[key] = value
            continue

        if new_key != key:
            merge_log.append((key, new_key))

        if new_key in cleaned:
            existing = cleaned[new_key]
            if isinstance(existing, list) and isinstance(value, list):
                seen = {r.get('doi', '') for r in existing if isinstance(r, dict)}
                for ref in value:
                    if isinstance(ref, dict) and ref.get('doi', '') not in seen:
                        existing.append(ref)
                        seen.add(ref.get('doi', ''))
            elif isinstance(existing, str) and isinstance(value, list):
                pass
            elif isinstance(existing, int) and isinstance(value, int):
                cleaned[new_key] = max(existing, value)
            elif isinstance(existing, list) and isinstance(value, list) and all(isinstance(v, str) for v in existing):
                cleaned[new_key] = sorted(set(existing + value))
            else:
                cleaned[new_key] = value
        else:
            cleaned[new_key] = value

    print(f'移除 cite:null: {len([r for r in removed_log if r[0] == "cite:null"])} 条')
    print(f'归一化 DOI key: {len(merge_log)} 条')
    for old, new in merge_log:
        print(f'  {old}\n  → {new}')
    return cleaned


def main():
    print(f'加载缓存: {CROSSREF_CACHE}')
    cache = load_cache()
    print(f'原始条目数: {len(cache)}')

    cleaned = clean_cache(cache)
    print(f'清洗后条目数: {len(cleaned)}')

    bak = CROSSREF_CACHE.with_suffix('.json.bak')
    print(f'备份至: {bak}')
    import shutil
    shutil.copy2(CROSSREF_CACHE, bak)

    cleaned_json = json.dumps(cleaned, ensure_ascii=False, indent=2)
    CROSSREF_CACHE.write_text(cleaned_json, encoding='utf-8')
    print('写入完成')


if __name__ == '__main__':
    main()
