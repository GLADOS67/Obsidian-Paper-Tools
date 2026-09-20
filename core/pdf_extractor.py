import multiprocessing
import queue
import re
from pathlib import Path

import pdfplumber

from core.doi import find_plausible_dois, normalize_unicode_dashes, repair_doi_text

_SENTENCE_END = '.。!！?？:：;；)）]】-—'

_RE_NUMBERED_HEADING = re.compile(r'^[\d.]+\s+\w')
_RE_SECTION_HEADING = re.compile(
    r'^(Abstract|Introduction|Methods?|Results?|Discussion|Conclusion|References?|'
    r'Acknowledgments?|Supplementary|Appendix)',
    re.IGNORECASE
)

_MAX_DOI_LEN = 80


# ── DOI extraction from pdf ──────────────────────────────────────

def _pdf_pages_task(queue, pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        queue.put([normalize_unicode_dashes(page.extract_text(x_tolerance=2, y_tolerance=2) or '')
                    for page in pdf.pages])


def extract_dois_from_pdf(pdf_path, timeout=60):
    if not (pdf_path and pdf_path.exists()):
        return set()
    try:
        ctx = multiprocessing.get_context('spawn')
        result_queue = ctx.Queue()
        p = ctx.Process(target=_pdf_pages_task, args=(result_queue, pdf_path))
        p.start()
        p.join(timeout=timeout)
        if p.is_alive():
            p.terminate()
            p.join()
            print(f'PDF文本提取超时({timeout}s)，跳过 {pdf_path.name}')
            return set()
        try:
            pages = result_queue.get_nowait()
        except queue.Empty:
            pages = []
        p.close()
        if not pages:
            return set()
        return {
            d
            for page_text in pages
            for section in re.split(r'\n\s*\n', page_text)
            for d in find_plausible_dois(repair_doi_text(section.replace('\n', ' ')))
            if len(d) <= _MAX_DOI_LEN
        }
    except Exception as e:
        print(f'从PDF提取DOI失败 {pdf_path.name}: {e}')
    return set()


def extract_first_doi_from_pdf(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = normalize_unicode_dashes(page.extract_text() or '')
                for d in find_plausible_dois(repair_doi_text(text)):
                    if len(d) <= _MAX_DOI_LEN:
                        return d
    except Exception as e:
        print(f'PDF提取主DOI失败: {e}')
    return None


# ── table extraction ─────────────────────────────────────────────

def table_to_md(table):
    data = table.extract()
    if not data:
        return ''
    max_cols = max(len(row) for row in data)
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
    separator = '| ' + ' | '.join(['---'] * max_cols) + ' |'
    lines.insert(1, separator)
    return '\n'.join(lines) + '\n'


# ── markdown post-processing ─────────────────────────────────────

def merge_paragraphs(text):
    lines = text.split('\n')
    result = [lines[0].rstrip()]
    for line in lines[1:]:
        curr = line.rstrip()
        prev = result[-1]
        if not curr:
            result.append('')
        elif not prev or (prev[-1] in _SENTENCE_END and not prev.endswith('-') and not curr[0].islower()):
            result.append(curr)
        else:
            result[-1] = (prev[:-1] + curr.lstrip()) if prev.endswith('-') else f'{prev} {curr.lstrip()}'
    return '\n'.join(result)


def post_process_md(text):
    lines = text.split('\n')
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith('#') and (
            _RE_NUMBERED_HEADING.match(stripped) or
            (len(stripped) < 80 and stripped.isupper() and sum(c.isalpha() for c in stripped) > 3) or
            _RE_SECTION_HEADING.match(stripped)
        ):
            lines[i] = f'## {stripped}'
    return '\n'.join(lines)


# ── PDF → Markdown ───────────────────────────────────────────────

def convert_pdf_to_md(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            parts = []
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=2, y_tolerance=2)
                if text:
                    parts.append(merge_paragraphs(text))
                for t in page.find_tables():
                    mt = table_to_md(t)
                    if mt:
                        parts.append(mt)
                parts.append('')
        return post_process_md(normalize_unicode_dashes('\n'.join(parts)))
    except Exception as e:
        print(f'PDF转换失败 {pdf_path}: {e}')
        return ''
