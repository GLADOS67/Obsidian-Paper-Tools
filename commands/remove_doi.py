"""/s: Purge erroneous DOI wikilinks from all Obsidian .md files in a directory tree.
"""
from pathlib import Path

from core.doi import make_wikilink


def run_remove_doi(directory: str, doi: str) -> list:
    target = Path(directory)
    wikilink = make_wikilink(doi)
    modified = []
    for md_file in target.rglob('*.md'):
        try:
            content = md_file.read_text(encoding='utf-8')
        except Exception:
            continue
        if wikilink not in content:
            continue
        lines = content.split('\n')
        filtered = [l for l in lines if wikilink not in l]
        if len(filtered) != len(lines):
            md_file.write_text('\n'.join(filtered), encoding='utf-8')
            modified.append((md_file, len(lines) - len(filtered)))
    return modified
