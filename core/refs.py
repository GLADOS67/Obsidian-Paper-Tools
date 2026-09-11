"""/s: Wikilink reference utilities for DOI citation lists."""

import re
from typing import Dict, Iterable, List, Optional, Tuple

from core.doi import PATTERN_DOI, CANONICAL_CHAR_TABLE, is_plausible_doi, process_doi


def canonicalize_stem(stem: str) -> str:
    return stem.translate(CANONICAL_CHAR_TABLE)


WIKILINK_RE = re.compile(r'\[\[([^|]+)\|([^]]+)\]\]')
LINK_TARGET_RE = re.compile(r'\[\[\s*([^|\]]+)')
H1_WIKILINK_RE = re.compile(r'^#\s*\[\[([^|]+)\|([^]]+)\]\]')


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
    if not ref_list:
        return None
    m = WIKILINK_RE.search(str(ref_list[0]).replace('\n', ' '))
    return m.group(1).strip() if m else None


def extract_doi_set(ref_list: list) -> set:
    if not ref_list:
        return set()
    result = set()
    for ref in ref_list:
        if not isinstance(ref, str):
            continue
        m = WIKILINK_RE.search(ref.replace('\n', ' '))
        result.update(PATTERN_DOI.findall(m.group(2) if m else ref))
    return result


_STEM_PREFIX_RE = re.compile(r'^\d+_?\s*')


def norm_stems(stem: str) -> set:
    variants = {stem, canonicalize_stem(stem)}
    variants |= {w for v in tuple(variants) for w in (v.replace(' ', '_'), v.replace('_', ' '))}
    if (stripped := _STEM_PREFIX_RE.sub('', stem)) != stem:
        variants.add(stripped)
        variants |= {sv for v in tuple(variants) if (sv := _STEM_PREFIX_RE.sub('', v)) != v}
    return variants


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
