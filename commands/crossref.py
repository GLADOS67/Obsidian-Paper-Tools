"""/s: Crossref API reference tool for Obsidian markdown notes.
Modes: direct file (DOI→Crossref refs), takeover ￥ (title→DOI→rebuild),
local: (parse ## 参考文献 body section), doi: (import refs into target note).
"""
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pdfplumber

from core.crossref_api import (fetch_references, get_doi_from_citation,
                               load_cache, save_cache)
from core.doi import (PATTERN_DOI, doi_from_doi_line, extract_doi_from_frontmatter,
                      find_plausible_dois, process_doi, repair_doi_text)
from core.frontmatter import dump_frontmatter, parse_frontmatter_str
from core.obsidian_path import resolve_input_path, SM_QUICK
from core.refs import new_doi_wikilinks, process_existing_references, split_wikilink

RE_MD_HEADING = re.compile(r'^#\s+(.+)', re.MULTILINE)
RE_REF_ENTRY = re.compile(r'^\s*(?:\[(\d+)\]|(\d+)\.)\s+(.*)$', re.MULTILINE)

_cache = load_cache()

_NON_TITLE_RE = re.compile(
    r'^(authors?|abstract|introduction|methods?|results?|discussions?|'
    r'conclusions?|references?|background|keywords?|acknowledg?ments?|'
    r'summary|materials?|supplementary|appendix)[\s:：]',
    re.IGNORECASE,
)


def _build_ref_list(md_stem: str, main_doi: Optional[str], references: List[Dict],
                    existing_refs: Optional[List[str]] = None) -> List[str]:
    if existing_refs is None:
        final, seen = [], set()
    else:
        final = process_existing_references(existing_refs)
        seen = {p[1].lower() for r in final if (p := split_wikilink(r))}
    if main_doi:
        md_display, _ = process_doi(main_doi)
        final = [r for r in final if md_display.lower() not in r.lower()]
        final.insert(0, f'[[{md_stem}|{md_display}]]')
        seen.add(md_display.lower())
    final.extend(new_doi_wikilinks((r['doi'] for r in references if r.get('doi')), seen))
    return final


def update_md_references(md_path: Path, references: List[Dict], main_doi: Optional[str] = None) -> None:
    content = md_path.read_text(encoding='utf-8')
    fm_data, body = parse_frontmatter_str(content)
    fm_data['reference'] = _build_ref_list(
        md_path.stem, main_doi, references,
        existing_refs=fm_data.get('reference', []),
    )
    md_path.write_text(dump_frontmatter(fm_data, body), encoding='utf-8')
    print(f'成功更新Markdown文件: {md_path}')


_DASH_TABLE = str.maketrans('\u2010\u2011\u2013\u2014\u2015', '-----')


def _extract_doi_from_pdf(pdf_path: Path) -> Optional[str]:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = (page.extract_text() or '').translate(_DASH_TABLE)
                if dois := find_plausible_dois(repair_doi_text(text)):
                    return dois[0]
    except Exception as e:
        print(f'PDF提取主DOI失败: {e}')
    return None


def _get_main_doi(pdf_path: Optional[Path], content: Optional[str], fm: Optional[dict]) -> Optional[str]:
    if fm and (main := extract_doi_from_frontmatter(fm)):
        return main
    if pdf_path and pdf_path.exists() and (doi := _extract_doi_from_pdf(pdf_path)):
        return process_doi(doi)[0]
    if content:
        if doi := doi_from_doi_line(content):
            return doi
        if dois := find_plausible_dois(content):
            return process_doi(dois[0])[0]
    return None


def _get_md_title(content: Optional[str], fm_data: Optional[dict], fallback_stem: str) -> str:
    if content:
        headings = RE_MD_HEADING.findall(content)
        for h in headings:
            h = h.strip()
            if not _NON_TITLE_RE.match(h):
                return h
        if headings:
            return headings[0].strip()
    if fm_data and fm_data.get('title'):
        return fm_data['title']
    return fallback_stem


def _get_file_title(file_path: Path, content: Optional[str], fm_data: Optional[dict]) -> Tuple[str, str]:
    stem = file_path.stem
    if content is None:
        return stem, stem
    title = (fm_data or {}).get('title', stem) if isinstance(fm_data, dict) else stem
    md_title = _get_md_title(content, fm_data, stem)
    return title, md_title


def _resolve_doi_by_title(title: str, md_title: str) -> Optional[str]:
    candidate = get_doi_from_citation(title, _cache)
    if not candidate:
        return None
    doi, crossref_title = candidate
    if not crossref_title or not md_title:
        print(f'标题→DOI: {doi}')
        return doi
    sm = SequenceMatcher(None, md_title.lower(), crossref_title.lower())
    sim = sm.ratio() if sm.quick_ratio() >= SM_QUICK else sm.quick_ratio()
    print(f'标题比对: [{crossref_title[:80]}] vs [{md_title[:80]}] → 相似度 {sim:.2f}')
    if sim >= 0.5:
        print(f'标题→DOI: {doi}')
        return doi
    print('相似度不足，用Crossref标题重试...')
    retry = get_doi_from_citation(crossref_title, _cache)
    if retry:
        verified_doi, _ = retry
        print(f'重试→DOI: {verified_doi}')
        return verified_doi
    print(f'重试失败，仍使用原始DOI: {doi}')
    return doi


def process_file(file_path: Path) -> None:
    if not file_path.exists():
        print(f'文件不存在: {file_path}')
        return
    suffix = file_path.suffix.lower()
    if suffix not in ('.md', '.pdf'):
        print(f'不支持的文件类型: {suffix}')
        return
    label = 'Markdown' if suffix == '.md' else 'PDF'
    print(f'处理{label}: {file_path}')
    content = file_path.read_text(encoding='utf-8') if suffix == '.md' else None
    fm_data, _ = parse_frontmatter_str(content) if content else ({}, '')
    pdf_path = file_path if suffix == '.pdf' else None
    main_doi = _get_main_doi(pdf_path, content, fm_data)
    if not main_doi:
        print('未提取到 DOI，尝试标题搜索...')
        title, md_title = _get_file_title(file_path, content, fm_data)
        main_doi = _resolve_doi_by_title(title, md_title)
        if not main_doi:
            if suffix == '.md':
                process_local_references_in_md(file_path)
            else:
                print('未能匹配论文，操作终止。')
            return
    print(f'目标DOI: {main_doi}')
    refs = fetch_references(main_doi, _cache)
    if suffix == '.md':
        update_md_references(file_path, refs, main_doi)
    else:
        print(f'拉取到 {len(refs)} 条参考文献')


def process_local_references_in_md(md_path: Path, override_main_doi: Optional[str] = None) -> None:
    if not md_path.exists():
        print(f'文件不存在: {md_path}')
        return
    content = md_path.read_text(encoding='utf-8')
    fm_data, _ = parse_frontmatter_str(content)
    main_doi = override_main_doi or _get_main_doi(None, content, fm_data)
    cl = content.lower()
    ref_headings = ['参考文献', 'reference']
    ref_start = next((i for h in ref_headings if (i := cl.find(f'# {h.lower()}')) != -1), -1)
    if ref_start == -1:
        print(f'未找到参考文献部分（支持的标题：{", ".join(ref_headings)}）')
        return
    ref_entries = RE_REF_ENTRY.findall(content[ref_start:])
    print(f'找到 {len(ref_entries)} 条本地参考文献，处理中...')
    references = []
    for num1, num2, text in ref_entries:
        text = text.rstrip('. \t')
        doi = None
        if m := PATTERN_DOI.search(repair_doi_text(text)):
            doi = m.group(0)
        else:
            result = get_doi_from_citation(text, _cache)
            doi = result[0] if result else None
        if doi:
            display, _ = process_doi(doi)
            print(f'  {num1 or num2}: 找到DOI {display}')
            references.append({'text': text, 'doi': display, 'title': text})
        else:
            print(f'  {num1 or num2}: 未找到DOI，跳过')
    update_md_references(md_path, references, main_doi)
    print('本地参考文献更新完成。')


def _handle_local_mode(raw_input: str) -> None:
    parts = raw_input.split('doi:', 1)
    path_part = parts[0].strip()
    override_main_doi = parts[1].strip() if len(parts) > 1 else None
    if override_main_doi and not PATTERN_DOI.match(override_main_doi):
        print(f"警告：提供的DOI格式无效 '{override_main_doi}'，将忽略并使用文件中的DOI。")
        override_main_doi = None
    path = resolve_input_path(path_part)
    if not path or not path.exists():
        print(f'无法解析或文件不存在: {path_part}')
        return
    process_local_references_in_md(path, override_main_doi)


def _handle_doi_import_mode(main_doi: str) -> None:
    if not PATTERN_DOI.match(main_doi):
        print(f'无效的DOI格式: {main_doi}')
        return
    print(f'检测到DOI导入模式，正在拉取 {main_doi} 的参考文献...')
    refs = fetch_references(main_doi, _cache)
    if not refs:
        print('未能拉取到参考文献，操作终止。')
        return
    print(f'成功拉取到 {len(refs)} 条参考文献，请输入要更新的笔记文件路径:')
    while True:
        target = input('目标文件: ').strip()
        if not target:
            print('输入不能为空，请重新输入。')
            continue
        resolved = resolve_input_path(target)
        if resolved and resolved.exists() and resolved.suffix.lower() == '.md':
            update_md_references(resolved, refs, main_doi)
            print(f'已成功将DOI {main_doi} 及其参考文献导入到笔记 {resolved} 的reference属性中。')
            return
        print('无效的文件路径，请重新输入有效的Markdown文件路径。')


def _handle_takeover_mode(file_path: Path) -> None:
    suffix = file_path.suffix.lower()
    if suffix not in ('.md', '.pdf'):
        print(f'不支持的文件类型: {suffix}')
        return
    if suffix == '.md':
        content = file_path.read_text(encoding='utf-8')
        fm_data, body = parse_frontmatter_str(content)
    else:
        content = None
        body = ''
    print(f'￥ 接管模式: {file_path}')
    title, md_title = _get_file_title(file_path, content, fm_data if suffix == '.md' else {})
    print(f'使用标题搜索: {title}')
    main_doi = _resolve_doi_by_title(title, md_title)
    if not main_doi:
        print('标题搜索失败，无法确定DOI')
        return
    print(f'标题→DOI: {main_doi}')
    refs = fetch_references(main_doi, _cache)
    if suffix == '.md':
        fm_data['reference'] = _build_ref_list(file_path.stem, main_doi, refs)
        file_path.write_text(dump_frontmatter(fm_data, body), encoding='utf-8')
        print(f'￥ 接管完成: 清空旧引用，写入 {len(fm_data["reference"])} 条引用（标题DOI置顶）')


def handle_input(input_str: str) -> None:
    input_str = input_str.strip()
    if not input_str:
        return
    takeover = input_str.startswith('￥')
    if takeover:
        input_str = input_str[1:].strip()
        if not input_str:
            print('￥ 接管模式缺少文件路径')
            return
    lower = input_str.lower()
    if lower.startswith('local:'):
        _handle_local_mode(input_str[6:].strip())
        return
    if lower.startswith('doi:'):
        _handle_doi_import_mode(input_str[4:].strip())
        return
    path = resolve_input_path(input_str, fallback_search=takeover)
    if path and path.exists():
        if takeover:
            _handle_takeover_mode(path)
        else:
            process_file(path)
        return
    if takeover:
        print('￥ 接管模式：无法解析文件路径')
        return
    print('无法识别的输入格式，请检查：')
    print('1. 本地文件路径（支持Obsidian URI）')
    print('2. ￥文件路径 （全面接管：清空引用→标题搜DOI→重建）')
    print('3. local:文件路径 [doi:目标DOI] （处理本地参考文献，可指定主DOI）')
    print('4. doi:DOI号（拉取DOI的参考文献并导入到指定笔记）')


def run_crossref_interactive() -> None:
    global _cache
    print('=== Obsidian 学术文献管理工具 ===')
    print('循环交互模式（支持 ￥路径 / local:路径 [doi:目标DOI] / 文件路径 / doi:DOI号）')
    while True:
        try:
            user_input = input('请输入内容: ').strip()
            if user_input:
                handle_input(user_input)
                save_cache(_cache)
                print('\n--- 处理完成，可继续输入 ---\n')
        except KeyboardInterrupt:
            print('\n退出程序')
            save_cache(_cache)
            break
        except Exception as e:
            import traceback
            traceback.print_exc()
