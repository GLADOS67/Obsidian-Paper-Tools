"""/s: Wikilink reference utilities for Obsidian citation graphs.
- split_wikilink: parse `[[name|display]]` into (name, display) tuple.
- build_existing_dois: collect existing DOIs from reference lists.
- process_existing_references: deduplicate & normalize wikilink references.
"""
from typing import List, Optional, Tuple


def split_wikilink(ref: str) -> Optional[Tuple[str, str]]:
    if not (ref.startswith('[[') and ref.endswith(']]')):
        return None
    inner = ref[2:-2]
    if '|' not in inner:
        return None
    name, display = inner.split('|', 1)
    return name.strip(), display.strip()


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
