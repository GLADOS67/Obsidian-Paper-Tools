"""/s: PubMed E-utilities cited-by query for Obsidian notes.
Uses NCBI Entrez esearch/elink/esummary to find papers citing a given DOI,
writes citing DOIs as wikilinks into Obsidian frontmatter cited_by field.
"""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from core.crossref_api import get_cited_by_pubmed, load_cache, save_cache
from core.doi import PATTERN_DOI, process_doi, repair_doi_text
from core.frontmatter import dump_frontmatter, parse_frontmatter_str
from core.obsidian_path import resolve_input_path


def _fm_main_doi(fm: dict) -> Optional[str]:
    doi_val = fm.get('doi')
    if isinstance(doi_val, list) and doi_val:
        doi_val = doi_val[0]
    if isinstance(doi_val, str) and (m := PATTERN_DOI.search(doi_val)):
        return process_doi(m.group(0))[0]
    return None


def _wikilink_doi(ref) -> Optional[str]:
    if not (isinstance(ref, str) and ref.startswith('[[') and ref.endswith(']]') and '|' in ref):
        return None
    d = ref[2:-2].split('|', 1)[1].strip()
    return process_doi(m.group(0))[0] if (m := PATTERN_DOI.search(d)) else None


def _get_main_doi_from_md(fm: dict, body: str) -> Optional[str]:
    if main := _fm_main_doi(fm):
        return main
    refs = fm.get('reference', [])
    if refs and isinstance(refs[0], str):
        first = refs[0]
        inner = first[2:-2] if first.startswith('[[') and first.endswith(']]') else first
        doi_part = inner.split('|', 1)[-1] if '|' in inner else inner
        if m := PATTERN_DOI.search(doi_part):
            return process_doi(m.group(0))[0]
    if m := PATTERN_DOI.search(repair_doi_text(body)):
        return process_doi(m.group(0))[0]
    for line in body.splitlines():
        if line.strip().lower().startswith('doi:') and (m := PATTERN_DOI.search(line)):
            return process_doi(m.group(0))[0]
    return None


def _collect_existing_dois(md_dir: Path) -> set:
    existing = set()
    for md_file in md_dir.glob('*.md'):
        try:
            fm, _ = parse_frontmatter_str(md_file.read_text(encoding='utf-8'))
        except Exception:
            continue
        if main := _fm_main_doi(fm):
            existing.add(main.lower())
        for key in ('reference', 'cited_by'):
            existing.update(d.lower() for ref in fm.get(key, []) if (d := _wikilink_doi(ref)))
    return existing


def run_cited_by(path: str, max_rows: int = 10) -> None:
    resolved = resolve_input_path(path) or resolve_input_path(path, fallback_search=True)
    if resolved is None:
        print(f'无法解析Obsidian路径: {path}')
        return
    if resolved.is_file():
        md_files = [resolved]
    elif resolved.is_dir():
        md_files = sorted(resolved.glob('*.md'))
    else:
        print(f'路径不存在: {resolved}')
        return

    cache = load_cache()
    parent_dir = resolved if resolved.is_dir() else resolved.parent
    existing_dois = _collect_existing_dois(parent_dir)

    for md_file in md_files:
        try:
            content = md_file.read_text(encoding='utf-8')
        except Exception as e:
            print(f'[ERR] 读取 {md_file.name}: {e}')
            continue

        fm, body = parse_frontmatter_str(content)
        main_doi = _get_main_doi_from_md(fm, body)
        if not main_doi:
            print(f'[SKIP] {md_file.name}: 未提取到主DOI')
            continue

        cited_by_date = fm.get('cited_by_date')
        if cited_by_date:
            try:
                last = datetime.strptime(str(cited_by_date)[:10], '%Y-%m-%d')
                if (datetime.now() - last).days < 30:
                    print(f'[SKIP] {md_file.name}: cited_by_date={cited_by_date} (距今<1个月)')
                    continue
            except ValueError:
                pass

        count, citing_dois = get_cited_by_pubmed(main_doi, cache, existing_dois, max_rows)
        fm.pop('cited_by_count', None)
        fm['cited_by_date'] = datetime.now().strftime('%Y-%m-%d')
        if citing_dois:
            refs = []
            for d in citing_dois:
                display, safe = process_doi(d)
                refs.append(f'[[{safe}|{display}]]')
                existing_dois.add(d.lower())
            fm['cited_by'] = refs
            print(f'[OK] {md_file.name}: cited_by_date={fm["cited_by_date"]}  新增 {len(citing_dois)} 篇')
        else:
            fm.pop('cited_by', None)
            print(f'[OK] {md_file.name}: cited_by_date={fm["cited_by_date"]}  无新增')

        md_file.write_text(dump_frontmatter(fm, body), encoding='utf-8')

    save_cache(cache)


def run_cited_by_interactive() -> None:
    print('=== PubMed Cited-by 查询 ===')
    while True:
        try:
            path = input('请输入 .md 路径或目录: ').strip()
            if not path:
                continue
            run_cited_by(path)
            print('\n--- 完成 ---\n')
        except KeyboardInterrupt:
            print('\n退出')
            break
        except Exception as e:
            import traceback
            traceback.print_exc()
