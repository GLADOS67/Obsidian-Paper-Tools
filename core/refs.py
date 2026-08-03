from typing import Iterable, List, Optional, Tuple

from core.doi import process_doi


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
    dois = set()
    for ref in references:
        parsed = split_wikilink(ref)
        if parsed and parsed[1]:
            dois.add(parsed[1].lower())
    return dois


def process_existing_references(refs: List[str]) -> List[str]:
    processed, seen = [], set()
    for ref in refs:
        ref = ref.strip()
        parsed = split_wikilink(ref)
        if parsed is None or not parsed[1]:
            if ref not in seen:
                seen.add(ref)
                processed.append(ref)
            continue
        name, display = parsed
        display_lower = display.lower()
        if display_lower not in seen:
            seen.add(display_lower)
            processed.append(f'[[{name.replace("/", "￥")}|{display}]]')
    return processed
