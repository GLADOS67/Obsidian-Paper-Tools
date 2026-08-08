"""/s: PubMed E-utilities cited-by query for Obsidian notes.
"""
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.crossref_api import get_cited_by_pubmed, load_cache, save_cache
from core.doi import (PATTERN_DOI, doi_from_doi_line, extract_doi_from_frontmatter,
                       get_main_doi, make_wikilink, process_doi, repair_doi_text)
from core.frontmatter import cited_by_fresh, dump_frontmatter, parse_frontmatter_str
from core.obsidian_path import resolve_input_path
from core.refs import wikilink_doi


def _get_main_doi_from_md(fm: dict, body: str) -> Optional[str]:
    main = extract_doi_from_frontmatter(fm)
    if main:
        return main
    refs = fm.get('reference', [])
    if refs and isinstance(refs[0], str):
        doi = wikilink_doi(refs[0])
        if doi:
            return doi
        m = PATTERN_DOI.search(refs[0].split('|', 1)[-1])
        if m:
            return process_doi(m.group(0))[0]
    m = PATTERN_DOI.search(repair_doi_text(body))
    return process_doi(m.group(0))[0] if m else doi_from_doi_line(body)


def _collect_existing(md_dir: Path) -> set:
    existing = set()
    for md_file in md_dir.glob('*.md'):
        try:
            fm, _ = parse_frontmatter_str(md_file.read_text(encoding='utf-8'))
        except Exception:
            continue
        if main := extract_doi_from_frontmatter(fm):
            existing.add(main.lower())
        existing.update(
            d.lower() for key in ('reference', 'cited_by')
            for ref in fm.get(key, []) if (d := wikilink_doi(ref))
        )
    return existing


def run_cited_by(path: str, max_rows: int = 10) -> None:
    resolved = resolve_input_path(path) or resolve_input_path(path, fallback_search=True)
    if resolved is None:
        print(f'无法解析Obsidian路径: {path}')
        return
    if not resolved.exists():
        print(f'路径不存在: {resolved}')
        return

    md_files = [resolved] if resolved.is_file() else sorted(resolved.glob('*.md'))
    cache = load_cache()
    existing = _collect_existing(resolved if resolved.is_dir() else resolved.parent)

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

        if cited_by_fresh(fm):
            print(f'[SKIP] {md_file.name}: cited_by_date={fm.get("cited_by_date")} (距今<1个月)')
            continue

        count, citing_dois = get_cited_by_pubmed(main_doi, cache, existing, max_rows)
        fm.pop('cited_by_count', None)
        fm['cited_by_date'] = datetime.now().strftime('%Y-%m-%d')
        if citing_dois:
            fm['cited_by'] = [make_wikilink(process_doi(d)[0]) for d in citing_dois]
            existing.update(d.lower() for d in citing_dois)
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
