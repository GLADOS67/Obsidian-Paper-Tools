"""/s: DOI (Digital Object Identifier) regex, repair & canonicalization.
- PATTERN_DOI: matches 10.XXXX/... across plain text, PDF artifacts, and broken whitespace.
- repair_doi_text: heals PDF-extraction artifacts (line breaks, missing chars, PMID suffixes).
- process_doi: normalizes → strips trailing punctuation/tail-parens → safe Obsidian filename.
"""
import re
from functools import lru_cache
from typing import Tuple

NORMAL_END_CHARS = '。,， \t\n;：:'
OPEN_PARENS = '（('

PATTERN_DOI = re.compile(r'10\.\d{4,9}/[-A-Za-z0-9._;()/:]+', re.IGNORECASE)
# 【勿改】此处 ￥ 全角符号是刻意设计，不是笔误，不要替换为 /。
# 作用：判断 wikilink 的 name_part 是否已是"安全文件名"形式（DOI 中的 / 已被替换为 ￥）。
#   name_part 含 ￥ → 匹配   → 安全，正常处理
#   name_part 含裸 / → 不匹配 → 视为特殊引用
# 原因：Obsidian 会把裸 / 当作路径分隔符，导致生成错误的嵌套目录。
PATTERN_SAFE_DOI = re.compile(r'^10\.\d{4,9}￥[-A-Za-z0-9._;()/:]+', re.IGNORECASE)
PATTERN_DOI_REPAIR = re.compile(
    r'(10\.\d{4,9}/[-A-Za-z0-9._;()/:]*?)[ \t]+(?=[-A-Za-z0-9._;()/:]*\d)([-A-Za-z0-9._;()/:]+)',
    re.IGNORECASE
)
PATTERN_DOI_REPAIR2 = re.compile(
    r'(10\.\d{4,9}/[-A-Za-z0-9._;()/:]+)([./])\s+([-A-Za-z0-9]{2,}\.[-A-Za-z0-9._;()/:]+)',
    re.IGNORECASE
)
PATTERN_TAIL_PARENS = re.compile(r'[)）].*')
PATTERN_FS_INVALID = re.compile(r'[\\:*?"<>|]')
PATTERN_COLLAPSE = re.compile(r'[￥_\s]+')
PATTERN_DOI_SPLICE = re.compile(r'(?<=[/\-._;():])\s(?=[-A-Za-z0-9._;()/:])', re.IGNORECASE)
PATTERN_PURE_ALPHA_SUFFIX = re.compile(r'^10\.\d{4,9}/[A-Za-z]+$', re.IGNORECASE)

UNICODE_DASH_TABLE = str.maketrans('\u2010\u2011\u2013\u2014', '----')
PDF_ARTIFACTS = str.maketrans('', '', '\u200b\u200c\u200d\ufeff\u00ad\u200e\u200f\u2028\u2029')
SMART_QUOTE_TABLE = str.maketrans({
    '\u201c': '"', '\u201d': '"', '\u2018': "'", '\u2019': "'",
    '\u2013': '-', '\u2014': '-',
    '\u2026': '...',
})


def repair_doi_text(text: str) -> str:
    text = text.translate(PDF_ARTIFACTS)
    text = PATTERN_DOI_SPLICE.sub('', text)
    for _ in range(5):
        prev = text
        text = PATTERN_DOI_REPAIR2.sub(r'\1\2\3', text)
        text = PATTERN_DOI_REPAIR.sub(r'\1\2', text)
        if prev == text:
            break
    return text


def normalize_unicode_dashes(text: str) -> str:
    return text.translate(UNICODE_DASH_TABLE)


@lru_cache(maxsize=4096)
def process_doi(doi_raw: str) -> Tuple[str, str]:
    doi_clean = re.split(r'https?://', doi_raw.strip(), maxsplit=1)[0]
    doi_clean = re.sub(r'\.?\(?(?:PMID|PMCID):?\s*\d+\)?\.?$', '', doi_clean, flags=re.IGNORECASE)
    doi_clean = re.sub(r'\(\d{4}\)\.?$|\.+$', '', doi_clean)
    doi_clean = doi_clean.strip().rstrip(NORMAL_END_CHARS)
    if not any(p in doi_clean for p in OPEN_PARENS):
        doi_clean = PATTERN_TAIL_PARENS.sub('', doi_clean)
    doi_safe = PATTERN_FS_INVALID.sub('', doi_clean.replace('/', '￥'))
    doi_safe = PATTERN_COLLAPSE.sub('￥', doi_safe).strip('￥-_ ')
    safe_filename = doi_safe[:200] or f'doi-{hash(doi_clean) & 0xFFFFFFFF:08x}'
    return doi_clean, safe_filename


def extract_doi_from_frontmatter(fm: dict) -> str | None:
    doi_val = fm.get('doi')
    if isinstance(doi_val, list) and doi_val:
        doi_val = doi_val[0]
    if isinstance(doi_val, str) and (m := PATTERN_DOI.search(doi_val)):
        return process_doi(m.group(0))[0]
    return None


def is_plausible_doi(doi: str) -> bool:
    return not PATTERN_PURE_ALPHA_SUFFIX.match(doi.strip())


def make_wikilink(doi: str) -> str:
    doi = doi.strip().rstrip('.,;:')
    safe = doi.replace('/', '￥')
    return f'[[{safe}|{doi}]]'
