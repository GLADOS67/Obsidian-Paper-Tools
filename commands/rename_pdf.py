import os
import re
import threading
from itertools import repeat
from pathlib import Path
from typing import Optional

import fitz

from core.cache import map_parallel
from core.doi import CANONICAL_CHAR_TABLE, norm_title
from core.title_cache import cache_entry_title, load_doi_title_cache

JUNK_TITLES = {
    'untitled', 'microsoft word', 'powerpoint', 'slide', 'slides',
    'pdf', 'document', 'no title', 'title', 'noname',
    'lippincott williams and wilkins', 'lippincott williams & wilkins',
    'wolters kluwer', 'springer', 'elsevier'
}

DOI_RE = re.compile(r'DOI[:;\s]*10\.\d{4,9}/?[-A-Za-z0-9._;()/:]*', re.IGNORECASE)
STATUS_MARKERS = [
    'publish ahead of print',
    'advance online publication',
    'online ahead of print',
    'epub ahead of print',
    'e-pub ahead of print',
    'accepted manuscript',
    'article in press',
    'ahead of print',
    'online first',
    'early online',
    'just accepted',
    'in press',
]
AUTHOR_DEGREE_RE = re.compile(
    r'\s+(?:[A-Z][a-z\xe0-\xfc]+(?:[-\s][A-Z][a-z\xe0-\xfc]+){0,2})\s+'
    r'(?:M\.?D\.?|Ph\.?D\.?|M\.?S\.?|B\.?S\.?|Sc\.?D\.?|D\.?O\.?|D\.?V\.?M\.?)'
    r'(?:\s|,|$)'
)
MSID_RE = re.compile(
    r'(?:^[A-Z]{3,}-\w-\d{2,4}-\d+|'
    r'_pap\s|\.\.\d+|'
    r'^Manuscript\s+ID|^MS\s*\d+)',
    re.IGNORECASE
)
SOURCE_EXT_RE = re.compile(r'\.(?:qxd|indd|docx?|pptx?|ai|cdr|psd|pub|idml)\b', re.IGNORECASE)
STATUS_SET = frozenset(STATUS_MARKERS)
# 平铺页标题块跳过词（原 _extract_from_flat_page 每次调用重建的局部常量，提升模块级）
FLAT_SKIP_TERMS = frozenset(('department', 'university', 'school of', 'hospital',
                             'institute', 'corresponding author'))
ET_AL_RE = re.compile(r',?\s+et\s+al\.?\s*$', re.IGNORECASE)
WS_RE = re.compile(r'\s+')
_FILENAME_STRIP_TABLE = str.maketrans({c: '' for c in r'<>:"/\|?*'})
# CANONICAL规范化 + 文件名字符删除 二合一单趟 translate（键集不相交，替换输出不含被删字符）
_SANITIZE_TABLE = {**CANONICAL_CHAR_TABLE, **_FILENAME_STRIP_TABLE}


_JUNK_PREFIXES = tuple(j for j in JUNK_TITLES if len(j) >= 5)


def _is_title_junk(title):
    if not title or len(title) < 5:
        return True
    tlower = title.lower()
    if tlower in JUNK_TITLES or tlower.startswith(_JUNK_PREFIXES):
        return True
    words = title.split()
    n_words = len(words)
    if n_words == 1 and title[0].isupper():
        return True
    if title.isupper() and (n_words <= 6 and all(len(w) <= 4 for w in words)
                             or sum(1 for w in words if len(w) == 1) >= 3 and len(title) < 40):
        return True
    bad = sum(1 for c in title if ord(c) < 32 or ord(c) == 0xFFFD)
    return bad / len(title) > 0.3


def _clean_title(raw_title):
    title = DOI_RE.sub(' ', raw_title.strip())
    tlower = title.lower()
    for marker in STATUS_MARKERS:
        idx = tlower.find(marker)
        if idx >= 0:
            title = title[idx + len(marker):].strip()
            tlower = title.lower()
            break
    title = ET_AL_RE.sub('', title)
    m = AUTHOR_DEGREE_RE.search(title)
    if m:
        title = title[:m.start()].strip()
    return WS_RE.sub(' ', title).strip(' ,-')


def _get_metadata_title(doc):
    title = (doc.metadata.get('title') or '').strip()
    if (_is_title_junk(title) or MSID_RE.search(title) or SOURCE_EXT_RE.search(title)
            or (title.isupper() and len(title) > 20)):
        return None
    title = _clean_title(title)
    return title if title and not _is_title_junk(title) else None


def _get_first_page_title(doc):
    page = doc[0]
    page_h = page.rect.height
    blocks = [b for b in page.get_text("dict").get("blocks", []) if b.get("type") == 0]
    spans = [
        {'size': span["size"], 'text': text, 'y': line["bbox"][1], 'x': line["bbox"][0]}
        for b in blocks for line in b.get("lines", []) for span in line.get("spans", [])
        if (text := span.get("text", "").strip()) and len(text) > 1
    ]
    if not spans:
        return None
    sizes = sorted({s['size'] for s in spans}, reverse=True)
    top_spans = [s for s in spans if s['y'] < page_h * 0.55]
    for sz in sizes:
        same = [s for s in top_spans if abs(s['size'] - sz) < 0.5]
        if not same:
            continue
        same.sort(key=lambda s: (s['y'], s['x']))
        if len(sizes) == 1:
            return _extract_from_flat_page(same, page_h)
        seen, parts = set(), []
        for s in same:
            key = s['text'].lower()
            if key not in seen:
                parts.append(s['text'])
                seen.add(key)
        candidate = ' '.join(parts)
        if len(candidate) > 20 and not _is_title_junk(candidate):
            return candidate
    return None


def _extract_from_flat_page(spans, page_h):
    lines = []
    for s in spans:
        tuned_y = round(s['y'] / 2.0) * 2.0
        if not lines or abs(tuned_y - lines[-1][0]) > 5:
            lines.append((tuned_y, []))
        lines[-1][1].append(s['text'])
    blocks, cur = [], []
    for y, texts in lines:
        txt = ' '.join(texts).strip()
        if not cur or y - cur[-1][0] < 30:
            cur.append((y, txt))
        else:
            blocks.append(cur)
            cur = [(y, txt)]
    if cur:
        blocks.append(cur)

    good = []
    for blk in blocks:
        combined = ' '.join(t for _, t in blk).lower()
        if any(m in combined for m in STATUS_SET) or DOI_RE.search(combined) or AUTHOR_DEGREE_RE.search(combined):
            continue
        if not any(kw in combined for kw in FLAT_SKIP_TERMS) and len(combined) >= 20:
            good.append(blk)
    if not good:
        return None
    best = max(good, key=lambda b: sum(len(t) for _, t in b))
    return ' '.join(t for _, t in best)


def _sanitize_filename(title):
    title = title.translate(_SANITIZE_TABLE).replace('\n', ' ').replace('\r', ' ')
    title = ' '.join(title.split())
    if len(title) > 250:
        cut = title[:251].rfind(' ')
        return title[:cut] if cut > 100 else title[:250]
    return title


def _first_page_tokens(doc) -> list:
    text = doc[0].get_text() or ''
    return [t for t in (t.rstrip('.,;:') for t in norm_title(text).split()) if t]


def _build_frag_index(cache: dict) -> dict:
    """标题前缀索引：按规范化标题首词分桶，_wakeup_from_cache 免全量线性扫描。"""
    index = {}
    for val in cache.values():
        if not (t := cache_entry_title(val)):
            continue
        if nt := norm_title(t):
            index.setdefault(nt.split()[0], []).append((nt, t))
    return index


def _wakeup_from_cache(title: str, doc, frag_index: dict) -> Optional[str]:
    frag = norm_title(title)
    if len(frag) < 20:
        return None
    frag_toks = [t for t in (t.rstrip('.,;:') for t in frag.split()) if t]
    cands = []
    # startswith(frag) 蕴含首词相同，仅需遍历 frag 首词所在分桶（结果与全量扫描一致）
    for norm_cached, full in frag_index.get(frag.split()[0], ()):
        if not norm_cached.startswith(frag):
            continue
        rem = norm_cached[len(frag):].strip()
        if len(rem) < 5:
            continue
        cands.append((full, [t for t in (t.rstrip('.,;:') for t in rem.split()) if t]))
    if not cands:
        return None
    page = _first_page_tokens(doc)
    nf, best, best_len = len(frag_toks), None, -1
    for i in range(len(page) - nf + 1):
        if page[i:i + nf] != frag_toks:
            continue
        for full, rem_toks in cands:
            nr = len(rem_toks)
            if nr > best_len and page[i + nf:i + nf + nr] == rem_toks:
                best, best_len = full, nr
    return best


def _process_one_pdf(pdf_path: Path, names_taken: set, lock: threading.Lock,
                     frag_index: dict) -> tuple:
    title = None
    try:
        with fitz.open(pdf_path) as doc:
            title = _get_metadata_title(doc) or _get_first_page_title(doc)
            title = _clean_title(title) if title else ''
            if title and not _is_title_junk(title) and frag_index:
                try:
                    cached_title = _wakeup_from_cache(title, doc, frag_index)
                except Exception:
                    cached_title = None
                if cached_title:
                    title = cached_title.rstrip('.')
                    print(f'  [CACHE] wakeup: {pdf_path.name} -> {title}')
    except Exception as e:
        return ('skip', pdf_path, str(e))
    title = _clean_title(title) if title else ''
    if not title or _is_title_junk(title):
        return ('skip', pdf_path, '')

    title = _sanitize_filename(title)
    with lock:
        names_taken.discard(pdf_path.stem)
        name, c = title, 1
        while name in names_taken:
            c += 1
            name = f"{title} ({c})"
        names_taken.add(name)
    new_path = pdf_path.with_name(name + '.pdf')
    try:
        os.rename(str(pdf_path), str(new_path))
        return ('renamed', pdf_path, new_path.name)
    except OSError as e:
        return ('failed', pdf_path, str(e))


def run_rename_pdf(directory):
    """Rename PDF files by extracted title."""
    path = Path(directory)
    pdf_files = sorted(p for p in path.glob('*.pdf') if not p.name.startswith('完成_'))
    total = len(pdf_files)
    if total == 0:
        print("No PDF files found (excluding 完成_*)")
        return

    frag_index = _build_frag_index(load_doi_title_cache())
    names_taken = {p.stem for p in pdf_files}
    renamed = skipped = 0
    lock = threading.Lock()

    # 共享线程池（core.cache map_parallel）：复用线程免每轮重建，默认并发度与原 ThreadPoolExecutor() 一致
    results = map_parallel(_process_one_pdf, pdf_files, repeat(names_taken),
                           repeat(lock), repeat(frag_index))
    for status, src, info in results:
        if status == 'renamed':
            renamed += 1
            print(f'  {src.name} -> {info}')
        else:
            skipped += 1
            tag, sep = ('Rename failed', ' -> ') if status == 'failed' else ('Skip', ' | ')
            print(f'  {tag}: {src.name}{sep}{info}')

    print(f"Total: {total}  Renamed: {renamed}  Skipped: {skipped}")
