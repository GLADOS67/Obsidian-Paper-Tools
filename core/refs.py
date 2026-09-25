import re
from functools import lru_cache
from typing import Iterable, List, Optional, Tuple

from core.doi import PATTERN_DOI, CANONICAL_CHAR_TABLE, is_plausible_doi, process_doi


def canonicalize_stem(stem: str) -> str:
    return stem.translate(CANONICAL_CHAR_TABLE)


def classify_claude_stem(stem: str) -> str:
    """Claude 目录笔记分类：'zh' (zh-CN 译文) / 'fe' (*_figures) / 'pa'（普通 PA 笔记）。

    合并 match.py / reconcile.py 中重复的 stem 分类判断。
    """
    if 'zh-CN' in stem:
        return 'zh'
    return 'fe' if stem.endswith('_figures') else 'pa'


WIKILINK_RE = re.compile(r'\[\[([^|]+)\|([^]]+)\]\]')
LINK_TARGET_RE = re.compile(r'\[\[\s*([^|\]]+)')
H1_WIKILINK_RE = re.compile(r'^#\s*\[\[?([^|\]]+)\|([^\]]+?)\]\]?')


def parse_h1_wikilink(text: str) -> Optional[Tuple[str, str]]:
    for line in text.split('\n'):
        m = H1_WIKILINK_RE.match(line.strip())
        if m:
            return m.group(1).strip(), m.group(2).strip()
    return None


def extract_wikilink_name(value) -> Optional[str]:
    if not value:
        return None
    m = WIKILINK_RE.search(str(value).replace('\n', ' '))
    return m.group(1).strip() if m else None


def first_ref_target(ref_list: list) -> Optional[str]:
    return extract_wikilink_name(ref_list[0]) if ref_list else None


def extract_doi_set(ref_list: list) -> set:
    if not ref_list:
        return set()

    def _target(ref: str) -> str:
        m = WIKILINK_RE.search(ref.replace('\n', ' '))
        return m.group(2) if m else ref

    return {d for ref in ref_list if isinstance(ref, str)
            for d in PATTERN_DOI.findall(_target(ref))}


_STEM_PREFIX_RE = re.compile(r'^\d+_?\s*')


@lru_cache(maxsize=None)  # 纯函数；调用方（reconcile）仅迭代不修改返回值
def norm_stems(stem: str) -> set:
    variants = {stem, canonicalize_stem(stem)}
    variants |= {w for v in list(variants) for w in (v.replace(' ', '_'), v.replace('_', ' '))}
    if (stripped := _STEM_PREFIX_RE.sub('', stem)) != stem:
        variants.add(stripped)
        variants |= {sv for v in list(variants) if (sv := _STEM_PREFIX_RE.sub('', v)) != v}
    variants |= {v.lower() for v in variants}
    for v in list(variants):
        if ' - ' in v:
            vb = v.replace(' - ', ' ')
            variants.add(vb)
            prefix = v.split(' - ')[0]
            if prefix and prefix != v:
                variants.update((prefix, prefix.lower()))
    variants |= {v.rstrip('.') for v in list(variants) if v.endswith('.')}
    variants |= {v.lower() for v in variants if not v.islower()}
    return variants


@lru_cache(maxsize=None)  # 纯函数；调用方（reconcile）仅迭代不修改返回值
def pa_stem_variants(pa_stem: str) -> list:
    variants = [pa_stem]
    stripped = _STEM_PREFIX_RE.sub('', pa_stem)
    if stripped and stripped != pa_stem:
        variants.append(stripped)
    for v in list(variants):
        if '_' in v:
            variants.append(v.replace('_', ' '))
        elif ' ' in v:
            variants.append(v.replace(' ', '_'))
    seen = set()
    return [x for x in variants if not (x in seen or seen.add(x))]


def split_wikilink(ref: str) -> Optional[Tuple[str, str]]:
    if not (ref.startswith('[[') and ref.endswith(']]')):
        return None
    inner = ref[2:-2]
    if '|' not in inner:
        return None
    name, display = inner.split('|', 1)
    return name.strip(), display.strip()


def new_doi_wikilinks(dois: Iterable[str], seen: set) -> List[str]:
    refs = []
    for raw in dois:
        display, safe = process_doi(raw)
        key = display.lower()
        if key not in seen:
            refs.append(f'[[{safe}|{display}]]')
            seen.add(key)
    return refs


def build_existing_dois(references: List[str]) -> set:
    return {p[1].lower() for ref in references if (p := split_wikilink(ref)) and p[1]}


def process_existing_references(refs: List[str]) -> List[str]:
    processed, seen = [], set()
    for ref in refs:
        ref = ref.strip()
        parsed = split_wikilink(ref)
        if parsed and parsed[1]:
            key, out = parsed[1].lower(), f'[[{parsed[0].replace("/", "￥")}|{parsed[1]}]]'
        else:
            key, out = ref, ref
        if key in seen:
            continue
        seen.add(key)
        processed.append(out)
    return processed


def wikilink_doi(ref: str) -> Optional[str]:
    if not isinstance(ref, str):
        return None
    parsed = split_wikilink(ref.strip())
    doi_part = (parsed[1] if parsed else ref).strip()
    m = PATTERN_DOI.search(doi_part)
    return process_doi(m.group(0))[0] if m and is_plausible_doi(m.group(0)) else None


def pin_main_doi(fm: dict, main_doi: str, md_stem: str) -> None:
    """去重并将 [[标题|主DOI]] 置顶为 reference[0]（main_doi 为空时不动）。"""
    if not main_doi:
        return
    lower = main_doi.lower()
    refs = [r for r in fm.get('reference', [])
            if not (r.startswith('[[') and r.endswith(']]') and '|' in r
                    and r[2:-2].split('|', 1)[1].strip().lower() == lower)]
    refs.insert(0, f'[[{md_stem}|{main_doi}]]')
    fm['reference'] = refs
