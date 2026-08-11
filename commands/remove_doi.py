"""/s: Remove wrong DOI wikilinks from Obsidian Vault .md files."""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    modified = []
    lock = threading.Lock()
    md_files = list(target.rglob('*.md'))

    with ThreadPoolExecutor() as ex:
        futures = {ex.submit(_process_one, f, wikilink): f for f in md_files}
        for fut in as_completed(futures):
            result = fut.result()
            if result:
                with lock:
                    modified.append(result)
    return modified
