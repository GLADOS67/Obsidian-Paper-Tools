"""/s: Wikilink reference utilities.
"""
from typing import Iterable, List, Optional, Tuple

from core.doi import PATTERN_DOI, is_plausible_doi, process_doi


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
            name, display = parsed[0].replace('/', '￥'), parsed[1]
            key = display.lower()
        else:
            key = ref
            display = None
        if key in seen:
            continue
        seen.add(key)
        processed.append(f'[[{name}|{display}]]' if display else ref)
    return processed


def wikilink_doi(ref: str) -> Optional[str]:
    parsed = split_wikilink(ref.strip()) if isinstance(ref, str) else None
    name_part, doi_part = (parsed[0], parsed[1]) if parsed else ('', ref.strip())
    m = PATTERN_DOI.search(doi_part)
    return process_doi(m.group(0))[0] if m and is_plausible_doi(m.group(0)) else None
