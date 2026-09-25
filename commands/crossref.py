import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional

from core.crossref_api import (fetch_references, get_doi_from_citation,
                                load_doi_title_cache, put_doi_title,
                                save_doi_title_cache)
from core.doi import (PATTERN_DOI, extract_doi_from_frontmatter,
                       get_main_doi, process_doi, repair_doi_text)
from core.frontmatter import dump_frontmatter, parse_frontmatter_str
from core.obsidian_path import resolve_input_path, SM_QUICK
from core.pdf_extractor import extract_first_doi_from_pdf
from core.refs import new_doi_wikilinks, process_existing_references, split_wikilink

RE_REF_ENTRY = re.compile(r'^\s*(?:\[(\d+)\]|(\d+)\.)\s+(.*)$', re.MULTILINE)

_USAGE_MSG = (
    '无法识别的输入格式，请检查：\n'
    '1. 本地文件路径（支持Obsidian URI）\n'
    '2. ￥文件路径 （全面接管：清空引用→标题搜DOI→重建）\n'
    '3. local:文件路径 [doi:目标DOI] （处理本地参考文献，可指定主DOI）\n'
    '4. doi:DOI号（拉取DOI的参考文献并导入到指定笔记）'
)

def _build_ref_list(md_stem: str, main_doi: Optional[str], references: List[Dict],
                    existing_refs: Optional[List[str]] = None) -> List[str]:
    final = process_existing_references(existing_refs) if existing_refs is not None else []
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
    if main_doi:
        fm_data['doi'] = main_doi
    fm_data['reference'] = _build_ref_list(
        md_path.stem, main_doi, references,
        existing_refs=fm_data.get('reference', []),
    )
    md_path.write_text(dump_frontmatter(fm_data, body), encoding='utf-8')
    print(f'成功更新Markdown文件: {md_path}')


def _get_main_doi(pdf_path: Optional[Path], content: Optional[str], fm: Optional[dict]) -> Optional[str]:
    main = extract_doi_from_frontmatter(fm) if fm else None
    if main:
        return main
    if pdf_path and pdf_path.exists() and (doi := extract_first_doi_from_pdf(pdf_path)):
        return process_doi(doi)[0]
    return get_main_doi(fm or {}, content or '')


def _get_md_title(fm_data, fallback_stem):
    if fm_data:
        title = fm_data.get('title')
        if isinstance(title, list):
            title = ' '.join(str(t) for t in title)
        title = str(title).strip() if title else ''
        # wikilink 包裹标题（[[...]]）视为无效，回退文件地址（文件名即标题）
        if title and '[' not in title and ']' not in title:
            return title
    return fallback_stem


def _resolve_doi_by_title(title: str, md_title: str, cache: dict) -> Optional[str]:
    candidate = get_doi_from_citation(title, cache)
    if not candidate:
        return None
    doi, crossref_title = candidate
    if not crossref_title or not md_title:
        print(f'标题→DOI: {doi}')
        return doi
    sm = SequenceMatcher(None, md_title.lower(), crossref_title.lower())
    quick = sm.quick_ratio()
    sim = sm.ratio() if quick >= SM_QUICK else quick
    print(f'标题比对: [{crossref_title[:80]}] vs [{md_title[:80]}] → 相似度 {sim:.2f}')
    if sim >= 0.5:
        print(f'标题→DOI: {doi}')
        return doi
    print('相似度不足，用Crossref标题重试...')
    retry = get_doi_from_citation(crossref_title, cache)
    result = retry[0] if retry else doi
    print(f'重试→DOI: {result}')
    return result


def _load_md_or_pdf(file_path: Path):
    """读取 .md（返回 fm/body）或标记 .pdf；不支持的类型返回 fm=None。"""
    suffix = file_path.suffix.lower()
    if suffix not in ('.md', '.pdf'):
        return suffix, None, None, None
    content = file_path.read_text(encoding='utf-8') if suffix == '.md' else None
    fm, body = parse_frontmatter_str(content) if content else ({}, '')
    return suffix, content, fm, body


def process_file(file_path: Path, cache: dict) -> None:
    if not file_path.exists():
        print(f'文件不存在: {file_path}')
        return
    suffix, content, fm_data, _ = _load_md_or_pdf(file_path)
    if fm_data is None:
        print(f'不支持的文件类型: {suffix}')
        return
    print(f'处理{"Markdown" if suffix == ".md" else "PDF"}: {file_path}')
    pdf_path = file_path if suffix == '.pdf' else None
    stem = file_path.stem
    md_title = ''  # 惰性计算的 _get_md_title 结果
    main_doi = _get_main_doi(pdf_path, content, fm_data)
    if not main_doi:
        print('未提取到 DOI，尝试标题搜索...')
        md_title = _get_md_title(fm_data, stem)
        main_doi = _resolve_doi_by_title(fm_data.get('title', stem), md_title, cache)
    if not main_doi:
        if suffix == '.md':
            process_local_references_in_md(file_path, cache=cache)
        else:
            print('未能匹配论文，操作终止。')
        return
    print(f'目标DOI: {main_doi}')
    put_doi_title(cache, main_doi, md_title or _get_md_title(fm_data, stem))
    refs, _ = fetch_references(main_doi, cache)
    if suffix == '.md':
        update_md_references(file_path, refs, main_doi)
    else:
        print(f'拉取到 {len(refs)} 条参考文献')


def process_local_references_in_md(md_path: Path, override_main_doi: Optional[str] = None, cache: dict = None) -> None:
    if not md_path.exists():
        print(f'文件不存在: {md_path}')
        return
    cache = cache or load_doi_title_cache()
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
        if m := PATTERN_DOI.search(repair_doi_text(text)):
            doi = m.group(0)
        else:
            result = get_doi_from_citation(text, cache)
            doi = result[0] if result else None
        if doi:
            display, _ = process_doi(doi)
            print(f'  {num1 or num2}: 找到DOI {display}')
            references.append({'text': text, 'doi': display, 'title': text})
        else:
            print(f'  {num1 or num2}: 未找到DOI，跳过')
    update_md_references(md_path, references, main_doi)
    print('本地参考文献更新完成。')


def _handle_local_mode(raw_input: str, cache: dict) -> None:
    path_part, _, doi_part = raw_input.partition('doi:')
    path_part = path_part.strip()
    override_main_doi = doi_part.strip() if doi_part else None
    if override_main_doi and not PATTERN_DOI.match(override_main_doi):
        print(f"警告：提供的DOI格式无效 '{override_main_doi}'，将忽略并使用文件中的DOI。")
        override_main_doi = None
    path = resolve_input_path(path_part)
    if not path or not path.exists():
        print(f'无法解析或文件不存在: {path_part}')
        return
    process_local_references_in_md(path, override_main_doi, cache)


def _handle_doi_import_mode(main_doi: str, cache: dict) -> None:
    if not PATTERN_DOI.match(main_doi):
        print(f'无效的DOI格式: {main_doi}')
        return
    print(f'检测到DOI导入模式，正在拉取 {main_doi} 的参考文献...')
    refs, _ = fetch_references(main_doi, cache)
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
            break
        print('无效的文件路径，请重新输入有效的Markdown文件路径。')
    update_md_references(resolved, refs, main_doi)
    print(f'已成功将DOI {main_doi} 及其参考文献导入到笔记 {resolved} 的reference属性中。')


def _handle_takeover_mode(file_path: Path, cache: dict) -> None:
    suffix, content, fm_data, body = _load_md_or_pdf(file_path)
    if fm_data is None:
        print(f'不支持的文件类型: {suffix}')
        return
    print(f'￥ 接管模式: {file_path}')
    stem = file_path.stem
    title = fm_data.get('title', stem) if suffix == '.md' else stem
    md_title = _get_md_title(fm_data, stem)
    print(f'使用标题搜索: {title}')
    main_doi = _resolve_doi_by_title(title, md_title, cache)
    if not main_doi:
        print('标题搜索失败，无法确定DOI')
        return
    print(f'标题→DOI: {main_doi}')
    put_doi_title(cache, main_doi, title)
    refs, _ = fetch_references(main_doi, cache)
    if suffix == '.md':
        fm_data['doi'] = main_doi
        fm_data['reference'] = _build_ref_list(file_path.stem, main_doi, refs)
        file_path.write_text(dump_frontmatter(fm_data, body), encoding='utf-8')
        print(f'￥ 接管完成: 清空旧引用，写入 {len(fm_data["reference"])} 条引用（标题DOI置顶）')


def handle_input(input_str: str, cache: dict = None) -> bool:
    input_str = input_str.strip()
    if not input_str:
        return False
    cache = cache or load_doi_title_cache()
    takeover = input_str.startswith('￥')
    if takeover:
        input_str = input_str[1:].strip()
        if not input_str:
            print('￥ 接管模式缺少文件路径')
            return True

    lower = input_str.lower()
    if lower.startswith('local:'):
        _handle_local_mode(input_str[6:].strip(), cache)
        return True
    if lower.startswith('doi:'):
        _handle_doi_import_mode(input_str[4:].strip(), cache)
        return True

    path = resolve_input_path(input_str, fallback_search=takeover)
    if not (path and path.exists()):
        print('￥ 接管模式：无法解析文件路径' if takeover else _USAGE_MSG)
        return True
    _handle_takeover_mode(path, cache) if takeover else process_file(path, cache)
    return True


def run_crossref_interactive() -> None:
    print('=== Obsidian 学术文献管理工具 ===')
    print('循环交互模式（支持 ￥路径 / local:路径 [doi:目标DOI] / 文件路径 / doi:DOI号）')
    cache = load_doi_title_cache()
    while True:
        try:
            user_input = input('请输入内容: ').strip()
            if user_input:
                handle_input(user_input, cache)
                save_doi_title_cache(cache)
                print('\n--- 处理完成，可继续输入 ---\n')
        except KeyboardInterrupt:
            print('\n退出程序')
            save_doi_title_cache(cache)
            break
        except Exception as e:
            import traceback
            traceback.print_exc()
