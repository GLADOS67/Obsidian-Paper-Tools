"""/s: DOI regex, repair and canonicalization utilities."""

import re
from functools import lru_cache
from typing import List, Optional, Tuple

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
    r'(10\.\d{4,9}/[-A-Za-z0-9._;()/:]+)[ \t]*([./])[ \t]+([-A-Za-z0-9]{2,}\.[-A-Za-z0-9._;()/:]+)',
    re.IGNORECASE
)
PATTERN_TAIL_PARENS = re.compile(r'[)）].*')
PATTERN_FS_INVALID = re.compile(r'[\\:*?"<>|]')
PATTERN_COLLAPSE = re.compile(r'[￥_\s]+')
PATTERN_DOI_SPLICE = re.compile(r'(?<=[/\-._;():])[ \t](?=[-A-Za-z0-9._;()/:])', re.IGNORECASE)
PATTERN_PURE_ALPHA_SUFFIX = re.compile(r'^10\.\d{4,9}/[A-Za-z]+$', re.IGNORECASE)
_RE_URL_SPLIT = re.compile(r'https?://')
_RE_ID_TAIL = re.compile(r'\.?\(?(?:PMID|PMCID):?\s*\d+\)?\.?$', re.IGNORECASE)
_RE_YEAR_OR_DOTS_TAIL = re.compile(r'\(\d{4}\)\.?$|\.+$')

UNICODE_DASH_TABLE = str.maketrans('\u2010\u2011\u2012\u2013\u2014\u2015\u2212', '-------')
PDF_ARTIFACTS = str.maketrans('', '', '\u200b\u200c\u200d\ufeff\u00ad\u200e\u200f\u2028\u2029')
SMART_QUOTE_TABLE = str.maketrans({
    '\u2018': '\u201c', '\u2019': '\u201d', '\u201a': '\u201c',
    '\u201b': '\u201c', '\u201c': '\u201c', '\u201d': '\u201d',
    '\u201e': '\u201c', '\u201f': '\u201d', '\u2039': '\u201c',
    '\u203a': '\u201d',
    '\u2010': '-', '\u2011': '-', '\u2012': '-', '\u2013': '-',
    '\u2014': '-', '\u2015': '-', '\u2212': '-',
    '\u2026': '...',
})


def repair_doi_text(text: str) -> str:
    text = text.translate(PDF_ARTIFACTS)
    text = PATTERN_DOI_SPLICE.sub('', text)
    prev = None
    while text != prev:
        prev = text
        text = PATTERN_DOI_REPAIR2.sub(r'\1\2\3', text)
        text = PATTERN_DOI_REPAIR.sub(r'\1\2', text)
    return text


def normalize_unicode_dashes(text: str) -> str:
    return text.translate(UNICODE_DASH_TABLE)


@lru_cache(maxsize=4096)
def process_doi(doi_raw: str) -> Tuple[str, str]:
    doi_clean = _RE_URL_SPLIT.split(doi_raw.strip(), maxsplit=1)[0]
    doi_clean = _RE_ID_TAIL.sub('', doi_clean)
    doi_clean = _RE_YEAR_OR_DOTS_TAIL.sub('', doi_clean)
    doi_clean = doi_clean.strip().rstrip(NORMAL_END_CHARS)
    if not any(p in doi_clean for p in OPEN_PARENS):
        doi_clean = PATTERN_TAIL_PARENS.sub('', doi_clean)
    doi_safe = PATTERN_FS_INVALID.sub('', doi_clean.replace('/', '￥'))
    doi_safe = PATTERN_COLLAPSE.sub('￥', doi_safe).strip('￥-_ ')
    return doi_clean, doi_safe[:200] or f'doi-{hash(doi_clean) & 0xFFFFFFFF:08x}'


def extract_doi_from_frontmatter(fm: dict) -> str | None:
    doi_val = fm.get('doi')
    if isinstance(doi_val, list) and doi_val:
        doi_val = doi_val[0]
    return process_doi(m.group(0))[0] if (isinstance(doi_val, str) and (m := PATTERN_DOI.search(doi_val))) else None


PATTERN_DOUBLE_DOI = re.compile(r'10\.\d{4,9}/.*10\.\d{4,9}/', re.IGNORECASE)
PATTERN_EMBEDDED_DOI_LABEL = re.compile(r'\.doi[:\d]', re.IGNORECASE)
PATTERN_STAT_OR_CI = re.compile(r'\d+\.\d+\(\d+\.\d+[-–]\d+\.\d+\)')
PATTERN_REF_TAIL = re.compile(r'\d{1,3}\.[A-Z][a-z]{2,}')
MAX_DOI_RAW_LEN = 200


def is_plausible_doi(doi: str) -> bool:
    doi = doi.strip()
    if PATTERN_PURE_ALPHA_SUFFIX.match(doi):
        return False
    if len(doi) > MAX_DOI_RAW_LEN:
        return False
    if PATTERN_DOUBLE_DOI.search(doi):
        return False
    if PATTERN_EMBEDDED_DOI_LABEL.search(doi):
        return False
    if PATTERN_STAT_OR_CI.search(doi):
        return False
    if PATTERN_REF_TAIL.search(doi):
        return False
    return True


def find_plausible_dois(text: str) -> List[str]:
    return [d for d in PATTERN_DOI.findall(text) if is_plausible_doi(d)]


def doi_from_doi_line(content: str) -> Optional[str]:
    for line in content.splitlines():
        if line.strip().lower().startswith('doi:') and (m := PATTERN_DOI.search(line)):
            return process_doi(m.group(0))[0]
    return None


def get_main_doi(fm: dict, content: str, all_dois: set = None) -> Optional[str]:
    if main := extract_doi_from_frontmatter(fm):
        return main
    if doi := doi_from_doi_line(content):
        return doi
    # 正文中第一个出现的DOI = 论文自身DOI（出现在标题/URL区，早于参考文献）
    if dois := find_plausible_dois(content):
        return process_doi(dois[0])[0]
    if all_dois:
        return process_doi(next(iter(all_dois)))[0]
    return None


def make_wikilink(doi: str) -> str:
    doi = doi.strip().rstrip('.,;:')
    return f'[[{doi.replace("/", "￥")}|{doi}]]'


