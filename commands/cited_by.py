import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from core.crossref_api import (load_cite_by_cache, load_doi_title_cache,
                               refresh_cited_by, save_cite_by_cache,
                               save_doi_title_cache)
from core.doi import PATTERN_DOI, get_main_doi, process_doi
from core.frontmatter import (
    build_doi_set, cited_by_fresh, dump_frontmatter,
    parse_frontmatter_str,
)
from core.obsidian_path import resolve_input_path
from core.refs import wikilink_doi


def _extract_main_doi(fm: dict, body: str) -> Optional[str]:
    if doi := get_main_doi(fm, body):
        return doi
    refs = fm.get('reference', [])
    if not (refs and isinstance(refs[0], str)):
        return None
    if doi := wikilink_doi(refs[0]):
        return doi
    m = PATTERN_DOI.search(refs[0].split('|', 1)[-1])
    return process_doi(m.group(0))[0] if m else None


def _process_cited_file(md_file: Path, cite_by_cache: dict, doi_title_cache: dict,
                       existing: set, max_rows: int, lock: threading.Lock) -> None:
    try:
        content = md_file.read_text(encoding='utf-8')
    except Exception as e:
        print(f'[ERR] 读取 {md_file.name}: {e}')
        return

    fm, body = parse_frontmatter_str(content)
    main_doi = _extract_main_doi(fm, body)
    if not main_doi:
        print(f'[SKIP] {md_file.name}: 未提取到主DOI')
        return
    if cited_by_fresh(fm):
        print(f'[SKIP] {md_file.name}: cited_by_date={fm.get("cited_by_date")} (距今<1个月)')
        return

    with lock:
        citing_dois = refresh_cited_by(fm, main_doi, cite_by_cache,
                                       doi_title_cache, existing, max_rows) or []
        existing.update(d.lower() for d in citing_dois)
    print(f'[OK] {md_file.name}: cited_by_date={fm["cited_by_date"]}  新增 {len(citing_dois)} 篇')

    md_file.write_text(dump_frontmatter(fm, body), encoding='utf-8')


def run_cited_by(path: str, max_rows: int = 10) -> None:
    resolved = resolve_input_path(path, fallback_search=True)
    if resolved is None:
        print(f'无法解析Obsidian路径: {path}')
        return
    if not resolved.exists():
        print(f'路径不存在: {resolved}')
        return

    if resolved.is_dir() and resolved.name != 'Clippings' and (resolved / 'Clippings').is_dir():
        resolved = resolved / 'Clippings'
    md_files = [resolved] if resolved.is_file() else sorted(resolved.rglob('*.md'))
    cite_by_cache = load_cite_by_cache()
    doi_title_cache = load_doi_title_cache()
    existing = build_doi_set(resolved if resolved.is_dir() else resolved.parent, include_refs=True)
    lock = threading.Lock()

    with ThreadPoolExecutor() as ex:
        futures = {ex.submit(_process_cited_file, f, cite_by_cache, doi_title_cache,
                             existing, max_rows, lock): f
                   for f in md_files}
        for fut in as_completed(futures):
            fut.result()

    save_cite_by_cache(cite_by_cache)
    save_doi_title_cache(doi_title_cache)


def run_cited_by_interactive() -> None:
    print('=== PubMed Cited-by 查询 ===')
    while True:
        try:
            path = input('请输入 .md 路径或目录: ').strip()
            if path:
                run_cited_by(path)
                print('\n--- 完成 ---\n')
        except KeyboardInterrupt:
            print('\n退出')
            break
        except Exception:
            import traceback
            traceback.print_exc()
