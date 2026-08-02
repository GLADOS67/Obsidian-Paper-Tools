"""/s: PyMuPDF title extraction → auto-rename PDF files.
Extracts metadata title or first-page heading via PyMuPDF (fitz), cleans junk titles
(status markers, degree suffixes, MSIDs), and renames PDFs to sanitized filenames.
"""
import os
import re
from pathlib import Path

JUNK_TITLES = {
    'untitled', 'microsoft word', 'powerpoint', 'slide', 'slides',
    'pdf', 'document', 'no title', 'title', 'noname',
    'lippincott williams and wilkins', 'lippincott williams & wilkins',
    'wolters kluwer', 'springer', 'elsevier'
}
ILLEGAL_CHARS = str.maketrans({c: '' for c in r'<>:"/\|?*'})

SMART_QUOTES = str.maketrans({
    '\u201c': '"',
    '\u201d': '"',
    '\u2018': "'",
    '\u2019': "'",
})

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


def _strip_author_suffix(title):
    title = re.sub(r',?\s+et\s+al\.?\s*$', '', title, flags=re.IGNORECASE)
    m = AUTHOR_DEGREE_RE.search(title)
    if m:
        return title[:m.start()].strip()
    return title


def _is_title_junk(title):
    if not title or len(title) < 5:
        return True
    tlower = title.lower()
    if tlower in JUNK_TITLES:
        return True
    if any(tlower.startswith(j) for j in JUNK_TITLES if len(j) >= 5):
        return True
    words = title.split()
    if len(words) == 1 and title[0].isupper():
        return True
    if title.isupper():
        if len(words) <= 6 and all(len(w) <= 4 for w in words):
            return True
        if sum(1 for w in words if len(w) == 1) >= 3 and len(title) < 40:
            return True
    bad = sum(1 for c in title if ord(c) < 32 or ord(c) in (0xFFFD, 65533))
    return bad / len(title) > 0.3


def _clean_title(raw_title):
    title = raw_title.strip()
    title = DOI_RE.sub(' ', title)
    tlower = title.lower()
    for marker in STATUS_MARKERS:
        idx = tlower.find(marker)
        if idx >= 0:
            title = title[idx + len(marker):].strip()
            tlower = title.lower()
            break
    title = _strip_author_suffix(title)
    title = re.sub(r'\s+', ' ', title).strip(' ,-')
    return title


def _get_metadata_title(doc):
    title = doc.metadata.get('title', '')
    if not title:
        return None
    title = title.strip()
    if _is_title_junk(title):
        return None
    if MSID_RE.search(title):
        return None
    if title.isupper() and len(title) > 20:
        return None
    title = _clean_title(title)
    if not title or _is_title_junk(title):
        return None
    return title


def _get_first_page_title(doc):
    page = doc[0]
    page_h = page.rect.height
    blocks = page.get_text("dict").get("blocks", [])
    spans = []
    for b in blocks:
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []):
            line_y = line["bbox"][1]
            line_x = line["bbox"][0]
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if text and len(text) > 1:
                    spans.append({'size': span["size"], 'text': text, 'y': line_y, 'x': line_x})
    if not spans:
        return None
    sizes = sorted(set(s['size'] for s in spans), reverse=True)
    for sz in sizes:
        same = [s for s in spans if abs(s['size'] - sz) < 0.5 and s['y'] < page_h * 0.55]
        if not same:
            continue
        same.sort(key=lambda s: (s['y'], s['x']))
        if len(sizes) == 1:
            candidate = _extract_from_flat_page(same, page_h)
            if candidate:
                return candidate
        seen = set()
        parts = []
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

    def _block_is_header(block):
        combined = ' '.join(t for _, t in block).lower()
        return any(m in combined for m in STATUS_MARKERS) or DOI_RE.search(combined)

    def _block_is_author(block):
        return AUTHOR_DEGREE_RE.search(' '.join(t for _, t in block))

    def _block_is_affil(block):
        combined = ' '.join(t for _, t in block).lower()
        return any(kw in combined for kw in ['department', 'university', 'school of',
                                             'hospital', 'institute', 'corresponding author'])

    good_blocks = []
    for blk in blocks:
        if _block_is_header(blk):
            continue
        if _block_is_author(blk):
            continue
        if _block_is_affil(blk):
            continue
        combined = ' '.join(t for _, t in blk)
        if len(combined) < 20:
            continue
        good_blocks.append(blk)
    if not good_blocks:
        return None
    best = max(good_blocks, key=lambda b: sum(len(t) for _, t in b))
    return ' '.join(t for _, t in best)


def _sanitize_filename(title):
    title = title.translate(SMART_QUOTES)
    title = title.replace('\n', ' ').replace('\r', ' ')
    title = title.translate(ILLEGAL_CHARS)
    title = ' '.join(title.split())
    if len(title) > 250:
        cut = title[:251].rfind(' ')
        return title[:cut] if cut > 100 else title[:250]
    return title


def run_rename_pdf(directory):
    """Rename PDF files by extracted title."""
    try:
        import fitz
    except ImportError:
        print("PyMuPDF not installed. Run: pip install pymupdf")
        return

    path = Path(directory)
    pdf_files = sorted(p for p in path.glob('*.pdf') if not p.name.startswith('完成_'))
    total = len(pdf_files)
    if total == 0:
        print("No PDF files found (excluding 完成_*)")
        return

    names_taken = {p.stem for p in pdf_files}
    renamed = skipped = 0

    for pdf_path in pdf_files:
        doc = fitz.open(pdf_path)
        try:
            title = _get_metadata_title(doc) or _get_first_page_title(doc)
        finally:
            doc.close()
        if title:
            title = _clean_title(title)
        if not title or _is_title_junk(title):
            skipped += 1
            continue
        title = _sanitize_filename(title)

        names_taken.discard(pdf_path.stem)
        name, c = title, 1
        while name in names_taken:
            name = f"{title} ({c})"
            c += 1
        names_taken.add(name)

        new_path = pdf_path.with_name(name + '.pdf')
        try:
            os.rename(str(pdf_path), str(new_path))
            renamed += 1
        except OSError as e:
            print(f"  Rename failed: {pdf_path.name} -> {new_path.name} | {e}")
            skipped += 1

    print(f"Total: {total}  Renamed: {renamed}  Skipped: {skipped}")
