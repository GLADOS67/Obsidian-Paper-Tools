"""/s: Obsidian wikilink DOI citation graph builder.
Scans all .md in a directory, builds global DOI→title mapping from reference/cited_by
wikilinks, resolves names, populates 被引/正向/负向 frontmatter fields.
"""
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.doi import (PATTERN_DOI, PATTERN_SAFE_DOI, UNICODE_DASH_TABLE,
                      normalize_unicode_dashes, process_doi, repair_doi_text)
from core.frontmatter import dump_frontmatter, parse_frontmatter_str
from core.markdown_utils import clean_markdown_body

Slot = Tuple[Optional[str], List[str]]
DoiEntry = Tuple[Slot, Slot]


def _shared_spec(entry: Optional[DoiEntry]) -> Optional[str]:
    return (entry[0][0] or entry[1][0]) if entry else None


def _split_wikilink(ref: str) -> Optional[Tuple[str, str]]:
    if not (ref.startswith('[[') and ref.endswith(']]') and '|' in ref):
        return None
    name_part, display_doi = map(str.strip, ref[2:-2].split('|', 1))
    return name_part, process_doi(display_doi)[0]


def _parse_cited_by_entry(cb_item) -> Optional[Tuple[str, str]]:
    if not isinstance(cb_item, str):
        return None
    s = cb_item.strip()
    if s.startswith('[[') and s.endswith(']]') and '|' in s:
        name_part, doi_part = map(str.strip, s[2:-2].split('|', 1))
    else:
        name_part, doi_part = '', s
    m = PATTERN_DOI.search(doi_part)
    return (name_part, process_doi(m.group(0))[0]) if m else None


def _update_doi_map(display_doi: str, name_part: str,
                    unique_map: Dict[str, DoiEntry],
                    citing_stem: str, slot: int = 0) -> Tuple[str, bool]:
    is_special = not PATTERN_SAFE_DOI.match(name_part)
    safe_name = process_doi(display_doi)[1]
    key = display_doi.lower()
    (ref_spec, ref_stems), (cb_spec, cb_stems) = unique_map.get(key, ((None, []), (None, [])))
    spec_add = name_part if is_special else None
    if slot == 0:
        ref_spec, ref_stems = ref_spec or spec_add, ref_stems + [citing_stem]
    else:
        cb_spec, cb_stems = cb_spec or spec_add, cb_stems + [citing_stem]
    unique_map[key] = ((ref_spec, ref_stems), (cb_spec, cb_stems))
    return (ref_spec or cb_spec or safe_name), is_special


def _process_references(refs: List, unique_map: Dict[str, DoiEntry],
                        citing_stem: str, is_existing: bool = True) -> Tuple[List[str], int]:
    if not refs:
        return [], 0
    special_count = 0
    seen: set = set()
    result: list = []
    for item in refs:
        if is_existing:
            ref = item.strip()
            if not ref:
                continue
            parsed = _split_wikilink(ref)
            if parsed is None:
                key = ref.lower()
                if key not in seen:
                    seen.add(key)
                    result.append(ref)
                continue
            name_part, display_doi = parsed
        else:
            display_doi, name_part = item
        used_name, is_special = _update_doi_map(display_doi, name_part, unique_map, citing_stem)
        if is_special:
            special_count += 1
        dedup_key = display_doi.lower()
        if dedup_key not in seen:
            seen.add(dedup_key)
            result.append(f'[[{used_name}|{display_doi}]]')
    return result, special_count


def _resolve_refs_final(refs, unique_map):
    if not refs:
        return []
    seen = set()
    result = []
    for item in refs:
        ref = item.strip()
        if not ref:
            continue
        parsed = _split_wikilink(ref)
        if parsed is None:
            key = ref.lower()
            if key not in seen:
                seen.add(key)
                result.append(ref)
            continue
        name_part, display_doi = parsed
        is_special = not PATTERN_SAFE_DOI.match(name_part)
        spec = _shared_spec(unique_map.get(display_doi.lower()))
        used_name = spec or (name_part if is_special else process_doi(display_doi)[1])
        dedup_key = display_doi.lower()
        if dedup_key not in seen:
            seen.add(dedup_key)
            result.append(f'[[{used_name}|{display_doi}]]')
    return result


def _resolve_cited_by(cited: List, unique_map: Dict[str, DoiEntry]) -> List[str]:
    if not cited:
        return []
    seen = set()
    result = []
    for item in cited:
        parsed = _parse_cited_by_entry(item)
        if parsed is None:
            continue
        _, display_doi = parsed
        dedup_key = display_doi.lower()
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        used_name = _shared_spec(unique_map.get(dedup_key)) or process_doi(display_doi)[1]
        result.append(f'[[{used_name}|{display_doi}]]')
    return result


def _resolve_self_doi(file_stem: str, refs: List[str]) -> Optional[str]:
    if not refs:
        return None
    for ref in refs:
        if ref.startswith('[[') and ref.endswith(']]') and '|' in ref:
            name_part, doi_part = ref[2:-2].split('|', 1)
            if name_part.strip() == file_stem:
                m = PATTERN_DOI.search(doi_part)
                if m:
                    return process_doi(m.group(0))[0]
    first = refs[0]
    inner = first[2:-2] if (first.startswith('[[') and first.endswith(']]')) else first
    doi_part = inner.split('|', 1)[-1] if '|' in inner else inner
    m = PATTERN_DOI.search(doi_part)
    return process_doi(m.group(0))[0] if m else None


def _process_unhandled_file(file: Path, content: str, fm: Dict, rest: str,
                            unique_map: Dict[str, DoiEntry]) -> Tuple[Dict, str]:
    if not isinstance(fm, dict):
        print(f'    ⚠️  {file.name} 的 frontmatter 非字典类型，已重置为空字典')
        fm = {}
    rest = clean_markdown_body(rest)
    removed = ','.join(k for k in ('author', 'published') if fm.pop(k, None) is not None)
    if removed:
        print(f'    🗑️  删除 {file.name} 字段：{removed}')
    unique_dois = list({doi.lower(): doi for doi in PATTERN_DOI.findall(repair_doi_text(content))}.values())
    doi_refs = [process_doi(doi) for doi in unique_dois]
    refs, special_count = _process_references(doi_refs, unique_map, file.stem, is_existing=False)
    if refs:
        fm['reference'] = refs
        print(f'    ✅ 添加 {len(refs)} 个DOI')
    fm['aliases'] = []
    fm['特殊引用数'] = special_count
    return fm, rest


def run_markdown_graph(directory: str) -> None:
    target = Path(directory)
    md_files = sorted(target.rglob('*.md'))
    print(f'找到 {len(md_files)} 个MD文件，开始处理...\n')

    unique_map: Dict[str, DoiEntry] = {}
    cited_by_map: Dict[str, Tuple[str, List[str]]] = {}
    files_data: List[Tuple[Path, Dict, str]] = []

    for file in md_files:
        try:
            content = normalize_unicode_dashes(file.read_text(encoding='utf-8'))
        except Exception as e:
            print(f'  警告：读取文件 {file.name} 失败，跳过 → {str(e)}')
            continue
        fm, rest = parse_frontmatter_str(content)
        for cb_item in fm.get('cited_by', []):
            parsed = _parse_cited_by_entry(cb_item)
            if parsed is None:
                continue
            name, disp = parsed
            dl = disp.lower()
            if dl not in cited_by_map:
                cited_by_map[dl] = (disp, [])
            if file.stem not in cited_by_map[dl][1]:
                cited_by_map[dl][1].append(file.stem)
            _update_doi_map(disp, name, unique_map, file.stem, slot=1)
        if 'aliases' in fm or 'reference' in fm:
            processed_refs, special_count = _process_references(
                fm.get('reference', []), unique_map, file.stem, is_existing=True)
            fm['reference'] = processed_refs
            fm['特殊引用数'] = special_count
            print(f'  ✅ {file.name} 收集到 {len(processed_refs)} 个DOI映射，已去重')
        else:
            print(f'处理未处理文件：{file.name}')
            fm, rest = _process_unhandled_file(file, content, fm, rest, unique_map)
            print(f'  ✅ {file.name} 处理完成')
        files_data.append((file, fm, rest))

    print(f'\n已收集到 {len(unique_map)} 个全局DOI标题映射')
    print('\n开始计算引用关系和引用情况并保存文件...')

    for file, fm, rest in files_data:
        refs = fm.get('reference', [])
        refs = _resolve_refs_final(refs, unique_map)
        fm['reference'] = refs
        if fm.get('cited_by'):
            fm['cited_by'] = _resolve_cited_by(fm['cited_by'], unique_map)
        self_doi = _resolve_self_doi(file.stem, refs)
        key = self_doi.lower() if self_doi else None
        citing_stems = unique_map[key][0][1] if (key and key in unique_map) else []
        fm['被引'] = [f'[[{s}]]' for s in citing_stems]
        fm['tags'] = ['正向' if (len(citing_stems) - fm.get('特殊引用数', 0)) > 0 else '负向']
        fm.pop('引用情况', None)
        try:
            file.write_text(dump_frontmatter(fm, rest), encoding='utf-8')
            print(f'  ✅ {file.name} 更新完成：被引={len(citing_stems)}篇, 标签={fm["tags"][0]}')
        except Exception as e:
            print(f'  ❌ {file.name} 保存失败 → {str(e)}')

    print('\n🎉 全部处理完成！')
    missing = [(doi, ref[1]) for doi, (ref, cb) in unique_map.items() if ref[0] is None and cb[0] is None]
    if missing:
        doi, stems = max(missing, key=lambda x: len(x[1]))
        print(f'\n🏆 引用最多的目前不存在的DOI：{doi} （被引 {len(stems)} 次）')
    else:
        print('\n未找到符合条件的目前不存在的DOI')

    external_cited = {k: v for k, v in cited_by_map.items()
                      if _shared_spec(unique_map.get(k)) is None}
    if external_cited:
        doi_lower, (disp, stems) = max(external_cited.items(), key=lambda x: len(x[1][1]))
        print(f'\n🏆 cited_by 出现最多的目前不存在的外部 DOI：{disp} （被 {len(stems)} 篇论文收录）')
    else:
        print('\n未找到符合条件的目前不存在的外部 cited_by DOI')
