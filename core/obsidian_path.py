"""/s: Obsidian URI (obsidian://open?vault=...&file=...) resolver with fuzzy glob fallback.
Resolves Obsidian deep links to absolute filesystem paths via vault-relative glob + SequenceMatcher.
"""
import re
import urllib.parse
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional, Tuple

from config import OBSIDIAN_ROOT

SM_QUICK = 0.7


def _parse_obsidian_uri(uri: str) -> Optional[Tuple[str, str]]:
    try:
        parsed = urllib.parse.urlparse(uri)
        q = urllib.parse.parse_qs(parsed.query)
        vault, file = q.get('vault', [None])[0], q.get('file', [None])[0]
        return (vault, file) if vault and file else None
    except Exception:
        return None


def resolve_input_path(input_str: str, fallback_search: bool = False) -> Optional[Path]:
    if not input_str.startswith('obsidian://'):
        return Path(input_str)
    result = _parse_obsidian_uri(input_str)
    if not result:
        return None
    vault, file = result
    file_clean = urllib.parse.unquote(file).rstrip(' \t\n')
    full_path = OBSIDIAN_ROOT / vault / file_clean
    if full_path.exists():
        return full_path
    if full_path.suffix.lower() != '.md':
        candidate = full_path.with_suffix('.md')
        if candidate.exists():
            return candidate
    stem = full_path.stem
    stripped_stem = stem.rstrip('.')
    if stripped_stem and stripped_stem != stem:
        candidate = full_path.with_name(stripped_stem + '.md')
        if candidate.exists():
            return candidate
    stem_raw = stem.strip('. \t').rstrip('.')
    dir_path = full_path.parent
    if dir_path.exists() and stem_raw:
        safe_stem = re.sub(r'([\[\]*?])', r'[\1]', stem_raw)
        stem_lower = stem_raw.lower()
        try:
            candidates = [
                p for p in dir_path.glob(f'{safe_stem}*.md')
                if (sm := SequenceMatcher(None, stem_lower, p.stem.lower())).quick_ratio() >= SM_QUICK
                and sm.ratio() >= SM_QUICK
            ]
            if candidates:
                candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                return candidates[0]
        except Exception:
            pass
    if not fallback_search:
        return None
    basename = Path(file_clean).name
    name_stem = Path(basename).stem
    for name in (basename, name_stem):
        try:
            matches = sorted(OBSIDIAN_ROOT.rglob(f'{name}.md'), key=lambda p: p.stat().st_mtime, reverse=True)
            if matches:
                return matches[0]
        except Exception:
            continue
    return None
