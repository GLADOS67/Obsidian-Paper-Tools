import multiprocessing
import re
import threading

import pdfplumber

from core.doi import find_plausible_dois, normalize_unicode_dashes, repair_doi_text
from config import CPU_CORES

_SENTENCE_END = '.。!！?？:：;；)）]】-—'

_RE_NUMBERED_HEADING = re.compile(r'^[\d.]+\s+\w')
_RE_BLANK_SPLIT = re.compile(r'\n\s*\n')
_RE_SECTION_HEADING = re.compile(
    r'^(Abstract|Introduction|Methods?|Results?|Discussion|Conclusion|References?|'
    r'Acknowledgments?|Supplementary|Appendix)',
    re.IGNORECASE
)

_MAX_DOI_LEN = 80


# ── DOI extraction from pdf ──────────────────────────────────────

_pool = None
_pool_lock = threading.Lock()


def _get_pool():
    """进程池惰性单例（spawn 上下文）：pdfplumber 需子进程规避主线程句柄泄漏。

    复用的池消除了按 PDF 逐次 spawn 的进程启动开销（每文件省 ~1-2s），
    超时语义与原先逐次 terminate 一致（get(timeout) 后丢弃结果）。
    """
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = multiprocessing.get_context('spawn').Pool(processes=min(CPU_CORES, 4))
    return _pool


def _pdf_pages(pdf_path) -> list:
    with pdfplumber.open(pdf_path) as pdf:
        return [normalize_unicode_dashes(page.extract_text(x_tolerance=2, y_tolerance=2) or '')
                for page in pdf.pages]


def extract_dois_from_pdf(pdf_path, timeout=60):
    if not (pdf_path and pdf_path.exists()):
        return set()
    try:
        pages = _get_pool().apply_async(_pdf_pages, (pdf_path,)).get(timeout=timeout)
    except TimeoutError:
        print(f'PDF文本提取超时({timeout}s)，跳过 {pdf_path.name}')
        return set()
    except Exception as e:
        print(f'从PDF提取DOI失败 {pdf_path.name}: {e}')
        return set()
    if not pages:
        return set()
    return {
        d
        for page_text in pages
        for section in _RE_BLANK_SPLIT.split(page_text)
        for d in find_plausible_dois(repair_doi_text(section.replace('\n', ' ')))
        if len(d) <= _MAX_DOI_LEN
    }


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
    has_content, lines = False, []
    for row in data:
        cells = [str(c).replace('\n', ' ').strip() if c else '' for c in row]
        cells += [''] * (max_cols - len(row))
        has_content = has_content or any(cells)
        lines.append('| ' + ' | '.join(cells) + ' |')
    if not has_content:
        return ''
    lines.insert(1, '| ' + ' | '.join(['---'] * max_cols) + ' |')
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
