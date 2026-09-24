import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.cache import read_text_auto
from core.crossref_api import (load_cite_by_cache, load_doi_title_cache,
                               lookup_doi_by_title, put_doi_title,
                               save_cite_by_cache, save_doi_title_cache)
from core.doi import (PATTERN_DOI, PATTERN_SAFE_DOI, find_plausible_dois,
                      is_plausible_doi, normalize_unicode_dashes, process_doi,
                      repair_doi_text)
from core.frontmatter import (dump_frontmatter, parse_frontmatter_batch,
                              parse_frontmatter_str)
from core.markdown_utils import H1_RE, clean_markdown_body
from core.refs import split_wikilink, wikilink_doi

DoiEntry = List  # [[ref_spec, ref_stems_dict], [cb_spec, cb_stems_dict]]


def _shared_spec(entry: Optional[DoiEntry]) -> Optional[str]:
    return (entry[0][0] or entry[1][0]) if entry else None


def _parse_cited_by_entry(cb_item) -> Optional[Tuple[str, str]]:
    if not isinstance(cb_item, str):
        return None
    parsed = split_wikilink(cb_item.strip())
    name_part = parsed[0] if parsed else ''
    doi = wikilink_doi(cb_item)
    return (name_part, doi) if doi else None


def _update_doi_map(display_doi: str, name_part: str,
                    unique_map: Dict[str, DoiEntry],
                    citing_stem: str, slot: int = 0) -> DoiEntry:
    is_special = not PATTERN_SAFE_DOI.match(name_part)
    key = display_doi.lower()
    entry = unique_map.get(key)
    if entry is None:
        entry = unique_map[key] = [[None, {}], [None, {}]]
    if not entry[slot][0]:
        entry[slot][0] = name_part if is_special else None
    entry[slot][1][citing_stem] = None
    return entry


def _rebuild_reference_list(refs: List, unique_map: Dict[str, DoiEntry],
                            citing_stem: Optional[str] = None,
                            is_existing: bool = True) -> Tuple[List[str], int]:
    if not refs:
        return [], 0
    special_count, seen, result = 0, set(), []
    for item in refs:
        if is_existing:
            ref = item.strip()
            if not ref:
                continue
            parsed = split_wikilink(ref)
            if parsed is None:
                key = ref.lower()
                if key not in seen:
                    seen.add(key)
                    result.append(ref)
                continue
            display_doi, name_part = process_doi(parsed[1])[0], parsed[0]
        else:
            display_doi, name_part = item
        if not is_plausible_doi(display_doi):
            continue
        dedup_key = display_doi.lower()
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        is_safe = bool(PATTERN_SAFE_DOI.match(name_part))
        if citing_stem is not None:
            entry = _update_doi_map(display_doi, name_part, unique_map, citing_stem)
            used_name = entry[0][0] or entry[1][0] or process_doi(display_doi)[1]
        else:
            entry_spec = _shared_spec(unique_map.get(dedup_key))
            used_name = entry_spec or (process_doi(display_doi)[1] if is_safe else name_part)
        special_count += int(not is_safe)
        result.append(f'[[{used_name}|{display_doi}]]')
    return result, special_count


def _resolve_cited_by(cited: List, unique_map: Dict[str, DoiEntry]) -> List[str]:
    if not cited:
        return []
    parsed_items = [(p[1], process_doi(p[1])[1]) for item in cited
                    if (p := _parse_cited_by_entry(item))]
    return _rebuild_reference_list(parsed_items, unique_map, is_existing=False)[0]


def _resolve_self_doi(file_stem: str, refs: List[str],
                      doi_title_cache=None) -> Optional[str]:
    if not refs:
        return None
    for ref in refs:
        if (p := split_wikilink(ref)) and p[0].strip() == file_stem:
            if m := PATTERN_DOI.search(p[1]):
                return process_doi(m.group(0))[0]
    first = refs[0]
    inner = first[2:-2] if first.startswith('[[') and first.endswith(']]') else first
    doi_part = inner.partition('|')[2] or inner
    m = PATTERN_DOI.search(doi_part)
    if m:
        return process_doi(m.group(0))[0]
    if doi_title_cache and (doi := lookup_doi_by_title(file_stem, doi_title_cache)):
        return process_doi(doi)[0]
    return None


def _process_one_file(file: Path, unique_map: Dict[str, DoiEntry],
                      cited_by_map: Dict[str, Tuple[str, List[str]]], lock: threading.Lock):
    try:
        content = normalize_unicode_dashes(read_text_auto(file))
    except Exception as e:
        print(f'  警告：读取文件 {file.name} 失败，跳过 → {str(e)}')
        return None
    fm, rest = parse_frontmatter_str(content)
    if not isinstance(fm, dict):
        print(f'    ⚠️  {file.name} 的 frontmatter 非字典类型，已重置为空字典')
        fm = {}
    # 纯计算部分（cited_by 解析、全文DOI提取、body清洗）在锁外完成，锁仅保护共享map写入
    cb_parsed = [p for item in fm.get('cited_by', []) if (p := _parse_cited_by_entry(item))]
    unhandled = 'aliases' not in fm and 'reference' not in fm
    doi_refs = None
    if unhandled:
        rest = clean_markdown_body(rest)
        unique_dois = {doi.lower(): doi for doi in find_plausible_dois(repair_doi_text(content))}
        doi_refs = [process_doi(doi) for doi in unique_dois.values()]
    with lock:
        for name, disp in cb_parsed:
            dl = disp.lower()
            cited_by_map.setdefault(dl, (disp, []))
            if file.stem not in cited_by_map[dl][1]:
                cited_by_map[dl][1].append(file.stem)
            _update_doi_map(disp, name, unique_map, file.stem, slot=1)
        if unhandled:
            print(f'处理未处理文件：{file.name}')
            removed = [k for k in ('author', 'published') if fm.pop(k, None) is not None]
            if removed:
                print(f'    🗑️  删除 {file.name} 字段：{",".join(removed)}')
            refs, special_count = _rebuild_reference_list(doi_refs, unique_map, file.stem, is_existing=False)
            if refs:
                fm['reference'] = refs
                print(f'    ✅ 添加 {len(refs)} 个DOI')
            fm['aliases'] = []
            fm['特殊引用数'] = special_count
            print(f'  ✅ {file.name} 处理完成')
        else:
            processed_refs, special_count = _rebuild_reference_list(
                fm.get('reference', []), unique_map, file.stem, is_existing=True)
            fm['reference'] = processed_refs
            fm['特殊引用数'] = special_count
            print(f'  ✅ {file.name} 收集到 {len(processed_refs)} 个DOI映射，已去重')
    return (file, fm, rest)


def _build_maps_from_fms(md_files, fms, unique_map, cited_by_map):
    for f, fm in zip(md_files, fms):
        if fm is None:
            continue
        for ref in fm.get('reference', []):
            ref = ref.strip()
            if not ref:
                continue
            parsed = split_wikilink(ref)
            if parsed:
                display_doi, name_part = process_doi(parsed[1])[0], parsed[0]
                if is_plausible_doi(display_doi):
                    _update_doi_map(display_doi, name_part, unique_map, f.stem, slot=0)
        for item in fm.get('cited_by', []):
            if p := _parse_cited_by_entry(item):
                name, disp = p
                dl = disp.lower()
                cited_by_map.setdefault(dl, (disp, []))
                if f.stem not in cited_by_map[dl][1]:
                    cited_by_map[dl][1].append(f.stem)
                _update_doi_map(disp, name, unique_map, f.stem, slot=1)


def _collect_stats_maps(md_files: List[Path]) -> Tuple[Dict[str, DoiEntry], Dict[str, Tuple[str, List[str]]]]:
    unique_map: Dict[str, DoiEntry] = {}
    cited_by_map: Dict[str, Tuple[str, List[str]]] = {}
    fms = parse_frontmatter_batch(md_files, fm_only=True)
    _build_maps_from_fms(md_files, fms, unique_map, cited_by_map)
    return unique_map, cited_by_map


def _print_top_orphans(unique_map: Dict[str, DoiEntry],
                       cited_by_map: Dict[str, Tuple[str, List[str]]], lead: str = '') -> None:
    """打印「引用最多但不存在的DOI」与「cited_by最多但不存在的外部DOI」两条战报。"""
    missing = [(doi, e[0][1]) for doi, e in unique_map.items()
               if e[0][0] is None and e[1][0] is None]
    if missing:
        doi, stems = max(missing, key=lambda x: len(x[1]))
        print(f'{lead}🏆 引用最多的目前不存在的DOI：{doi} （被引 {len(stems)} 次）')
    else:
        print(f'{lead}未找到符合条件的目前不存在的DOI')
    external_cited = {k: v for k, v in cited_by_map.items()
                      if _shared_spec(unique_map.get(k)) is None}
    if external_cited:
        _, (disp, stems) = max(external_cited.items(), key=lambda x: len(x[1][1]))
        print(f'🏆 cited_by 出现最多的目前不存在的外部 DOI：{disp} （被 {len(stems)} 篇论文收录）')
    else:
        print('未找到符合条件的目前不存在的外部 cited_by DOI')


def run_markdown_graph(directory: str, depth: int = 0) -> None:
    target = Path(directory)
    md_files = sorted(target.rglob('*.md'))
    print(f'找到 {len(md_files)} 个MD文件，开始处理...\n')

    doi_title_cache = load_doi_title_cache()
    cite_by_cache = load_cite_by_cache()

    unique_map: Dict[str, DoiEntry] = {}
    cited_by_map: Dict[str, Tuple[str, List[str]]] = {}
    files_data: List[Tuple[Path, Dict, str]] = []
    lock = threading.Lock()

    with ThreadPoolExecutor() as ex:
        futures = {ex.submit(_process_one_file, f, unique_map, cited_by_map, lock): f for f in md_files}
        for fut in as_completed(futures):
            result = fut.result()
            if result:
                files_data.append(result)

    print(f'\n已收集到 {len(unique_map)} 个全局DOI标题映射')
    print('\n开始计算引用关系和引用情况并保存文件...')

    for file, fm, rest in files_data:
        refs, _ = _rebuild_reference_list(fm.get('reference', []), unique_map)
        fm['reference'] = refs
        if fm.get('cited_by'):
            fm['cited_by'] = _resolve_cited_by(fm['cited_by'], unique_map)
        self_doi = _resolve_self_doi(file.stem, refs, doi_title_cache)
        key = self_doi.lower() if self_doi else None
        citing_stems = list(unique_map[key][0][1]) if (key and key in unique_map) else []
        citing_stems = [s for s in citing_stems if s != file.stem]
        fm['被引'] = [f'[[{s}]]' for s in citing_stems]
        fm['tags'] = ['正向' if (len(citing_stems) - fm.get('特殊引用数', 0)) > 0 else '负向']
        fm.pop('引用情况', None)
        if self_doi and is_plausible_doi(self_doi):
            title = fm.get('title')
            if isinstance(title, list):
                title = ' '.join(str(t) for t in title)
            if not (isinstance(title, str) and title.strip()):
                m = H1_RE.search(rest)
                title = m.group(1).strip() if m else None
            if title:
                put_doi_title(doi_title_cache, self_doi, title)
            for ref in refs:
                if ref_doi := wikilink_doi(ref):
                    if ref_doi.lower() == key or not is_plausible_doi(ref_doi):
                        continue
                    citing = cite_by_cache.setdefault(ref_doi, [])
                    if self_doi not in citing:
                        citing.append(self_doi)
        try:
            file.write_text(dump_frontmatter(fm, rest), encoding='utf-8')
            print(f'  ✅ {file.name} 更新完成：被引={len(citing_stems)}篇，标签={fm["tags"][0]}')
        except Exception as e:
            print(f'  ❌ {file.name} 保存失败 → {str(e)}')

    save_doi_title_cache(doi_title_cache)
    save_cite_by_cache(cite_by_cache)

    if depth > 0:
        tiers: Dict[int, List[Path]] = {}
        for p in target.rglob('*'):
            if p.is_dir() and (d := len(p.relative_to(target).parts)) <= depth:
                tiers.setdefault(d, []).append(p)
        for d in range(1, depth + 1):
            for folder in sorted(tiers.get(d, [])):
                md_files = sorted(folder.rglob('*.md'))
                if not md_files:
                    continue
                unique_map, cited_by_map = _collect_stats_maps(md_files)
                print(f'\n📁 {folder.name}')
                _print_top_orphans(unique_map, cited_by_map)

    print('\n🎉 全部处理完成！')
    _print_top_orphans(unique_map, cited_by_map, lead='\n')
