"""/s: pdfplumber offline PDF-to-Markdown conversion (local, no cloud upload).
Extracts text, tables → Markdown from PDFs without MinerU API — suitable for sensitive
documents. Enriches frontmatter with Crossref API references & PubMed cited-by data.
"""
import re
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pdfplumber

from commands.pdf2md import (
    _build_clippings_all_doi_set,
    _mark_pdf_done,
    _process_md_content,
    _build_clippings_index,
    _find_clippings_md,
)
from config import OBSIDIAN_ROOT
from commands.match import run_match
from core.crossref_api import load_cache, save_cache
from core.doi import normalize_unicode_dashes
from core.frontmatter import dump_frontmatter

_SENTENCE_END = '.。!！?？:：;；)）]】-—'


def _table_to_md(table):
    data = table.extract()
    if not data:
        return ''
    max_cols = max(len(row) for row in data)
    separator = '| ' + ' | '.join(['---'] * max_cols) + ' |'
    has_content = False
    lines = []
    for row in data:
        cells = [str(c).replace('\n', ' ').strip() if c else '' for c in row]
        cells += [''] * (max_cols - len(row))
        if not has_content:
            has_content = any(cells)
        lines.append('| ' + ' | '.join(cells) + ' |')
    if not has_content:
        return ''
    lines.insert(1, separator)
    return '\n'.join(lines) + '\n'


def _merge_paragraphs(text):
    lines = text.split('\n')
    result = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            result.append('')
            i += 1
            continue
        while i + 1 < len(lines) and lines[i + 1].strip() and (
            line[-1] not in _SENTENCE_END
            or lines[i + 1].strip()[0].islower()
            or line.endswith('-')
        ):
            nxt = lines[i + 1].strip()
            line = line[:-1] + nxt if line.endswith('-') else line + ' ' + nxt
            i += 1
        result.append(line)
        i += 1
    return '\n'.join(result)


_RE_NUMBERED_HEADING = re.compile(r'^[\d.]+\s+\w')
_RE_SECTION_HEADING = re.compile(
    r'^(Abstract|Introduction|Methods?|Results?|Discussion|Conclusion|References?|'
    r'Acknowledgments?|Supplementary|Appendix|背景|方法|结果|讨论|结论|参考文献|摘要|引言)',
    re.IGNORECASE
)


def _detect_heading(s):
    if _RE_NUMBERED_HEADING.match(s):
        return True
    if len(s) < 80 and s.isupper() and sum(c.isalpha() for c in s) > 3:
        return True
    return bool(_RE_SECTION_HEADING.match(s))


def _post_process_markdown(text):
    lines = text.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        if _detect_heading(stripped) and not stripped.startswith('#'):
            result.append(f'## {stripped}')
        else:
            result.append(line)
    return '\n'.join(result)


def convert_pdf_to_markdown(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            parts = []
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=2, y_tolerance=2)
                if text:
                    parts.append(_merge_paragraphs(text))
                for t in page.find_tables():
                    mt = _table_to_md(t)
                    if mt:
                        parts.append(mt)
                parts.append('')
        raw = normalize_unicode_dashes('\n'.join(parts))
        return _post_process_markdown(raw)
    except Exception as e:
        print(f'PDF转换失败 {pdf_path}: {e}')
        return ''


def run_pdf2md_local(
    path_pdf=None, path_md0=None,
    enable_api_refs=True, enable_cited_by=True, cited_by_max=10,
):
    """本地提取 避免信息泄露 — pdfplumber offline PDF→MD"""
    path_pdf = path_pdf or r'C:\Vault\PDF'
    path_md0 = path_md0 or r'C:\Vault\Claude\MDfrPDF'

    pp = Path(path_pdf)
    pm = Path(path_md0)
    for p in (pp, pm):
        p.mkdir(parents=True, exist_ok=True)

    images_dir = pm / 'images'
    images_dir.mkdir(exist_ok=True)
    trash_dir = pp.parent / 'TRASH'
    trash_dir.mkdir(exist_ok=True)

    clippings_idx = _build_clippings_index()
    pdf_files = []
    for pdf_file in sorted({f.absolute() for f in pp.rglob('*.pdf') if '完成' not in f.name}):
        done_path = pdf_file.parent / f'完成_{pdf_file.name}'
        if not done_path.exists():
            pdf_files.append(pdf_file)
            continue
        print(f'已存在完成版本: {pdf_file.name}')
        md_path, domain_dir = _find_clippings_md(pdf_file.stem, clippings_idx)
        if md_path:
            print(f'  找到已归档: {md_path.relative_to(OBSIDIAN_ROOT)}')
            print(f'  执行MATCH: {domain_dir}')
            match_ok = run_match(str(domain_dir), force=True)
            if match_ok:
                print(f'  MATCH成功，移入TRASH: {pdf_file.name}')
                try:
                    shutil.move(str(pdf_file), str(trash_dir / pdf_file.name))
                except Exception as e:
                    print(f'  移入TRASH失败: {e}')
            else:
                print(f'  MATCH无结果，跳过TRASH')
        else:
            print(f'  未找到对应.md，跳过TRASH')

    if not pdf_files:
        print('未找到需处理PDF')
        return

    print(f'共发现 {len(pdf_files)} 个PDF待处理')

    crossref_cache = load_cache()
    clippings_doi_set = _build_clippings_all_doi_set(pm) if enable_cited_by else None
    _cache_lock = threading.Lock()

    def _process_one(pdf_path, idx):
        print(f'[{idx}/{len(pdf_files)}] {pdf_path.name}')
        md_content = convert_pdf_to_markdown(pdf_path)
        if not md_content:
            print('  转换失败，跳过')
            return None
        md_dst = pm / f'{pdf_path.stem}.md'
        fm = {'title': pdf_path.stem, 'pdf_path': str(pdf_path)}
        try:
            md_dst.write_text(dump_frontmatter(fm, md_content), encoding='utf-8')
        except Exception as e:
            print(f'  写入失败: {e}')
            return None
        with _cache_lock:
            _process_md_content(
                md_dst, None, pdf_path, enable_api_refs,
                crossref_cache, enable_cited_by, cited_by_max,
                images_dir, clippings_doi_set,
            )
        _mark_pdf_done(pdf_path)
        return md_dst.name

    with ThreadPoolExecutor(max_workers=min(4, len(pdf_files))) as ex:
        futures = {ex.submit(_process_one, pf, i): pf for i, pf in enumerate(pdf_files, 1)}
        for fut in as_completed(futures):
            name = fut.result()
            if name:
                print(f'  完成 -> {name}')

    save_cache(crossref_cache)
    print(f'\n全部完成！共处理 {len(pdf_files)} 个PDF，输出到 {pm}')
