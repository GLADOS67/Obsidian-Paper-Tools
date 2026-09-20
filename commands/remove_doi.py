from concurrent.futures import ThreadPoolExecutor
from itertools import repeat
from pathlib import Path

from core.doi import make_wikilink


def _process_one(md_file: Path, wikilink: str) -> tuple:
    try:
        content = md_file.read_text(encoding='utf-8')
    except Exception:
        return None
    if wikilink not in content:
        return None
    lines = content.split('\n')
    filtered = [l for l in lines if wikilink not in l]
    diff = len(lines) - len(filtered)
    if not diff:
        return None
    md_file.write_text('\n'.join(filtered), encoding='utf-8')
    return (md_file, diff)


def run_remove_doi(directory: str, doi: str) -> list:
    target = Path(directory)
    wikilink = make_wikilink(doi)
    with ThreadPoolExecutor() as ex:
        return [r for r in ex.map(_process_one, target.rglob('*.md'), repeat(wikilink)) if r]
