from itertools import repeat
from pathlib import Path

from core.cache import map_parallel
from core.doi import make_wikilink


def _process_one(md_file: Path, wikilink: str) -> tuple:
    try:
        content = md_file.read_text(encoding='utf-8')
    except Exception:
        return None
    if wikilink not in content:
        return None
    # wikilink 不含换行符，命中即必有整行包含，len 差即为删除行数（无需二次校验）
    lines = content.split('\n')
    kept = [l for l in lines if wikilink not in l]
    md_file.write_text('\n'.join(kept), encoding='utf-8')
    return md_file, len(lines) - len(kept)


def run_remove_doi(directory: str, doi: str) -> list:
    target = Path(directory)
    wikilink = make_wikilink(doi)
    return [r for r in map_parallel(_process_one, target.rglob('*.md'), repeat(wikilink)) if r]
