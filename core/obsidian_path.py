"""/s: Obsidian URI / path resolution for Obsidian Vault notes."""

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


def _try_suffix(full_path: Path, suffix: str) -> Optional[Path]:
    candidate = full_path.with_suffix(suffix)
    return candidate if candidate.exists() else None


def _try_strip_dot(full_path: Path) -> Optional[Path]:
    stem = full_path.stem.rstrip('.')
    if not stem or stem == full_path.stem:
        return None
    candidate = full_path.with_name(stem + '.md')
    return candidate if candidate.exists() else None


def _fuzzy_search(dir_path: Path, stem_raw: str) -> Optional[Path]:
    if not dir_path.exists() or not stem_raw:
        return None
    stem_lower = stem_raw.lower()
    safe_stem = re.sub(r'([\[\]*?])', r'[\1]', stem_raw)
    best, best_mtime = None, 0.0
    try:
        for p in dir_path.glob(f'{safe_stem}*.md'):
            p_stem_lower = p.stem.lower()
            if p_stem_lower != stem_lower:
                sm = SequenceMatcher(None, stem_lower, p_stem_lower)
                if sm.quick_ratio() < SM_QUICK or sm.ratio() < SM_QUICK:
                    continue
            mtime = p.stat().st_mtime
            if mtime > best_mtime:
                best, best_mtime = p, mtime
    except Exception:
        return None
    return best


def _fallback_search(file_clean: str) -> Optional[Path]:
    basename = Path(file_clean).name
    for name in dict.fromkeys((basename, Path(basename).stem)):
        try:
            matches = sorted(OBSIDIAN_ROOT.rglob(f'{name}.md'), key=lambda p: p.stat().st_mtime, reverse=True)
            if matches:
                return matches[0]
        except Exception:
            continue
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
    for candidate in (_try_suffix(full_path, '.md'), _try_strip_dot(full_path)):
        if candidate:
            return candidate
    fuzzy = _fuzzy_search(full_path.parent, full_path.stem.strip('. \t').rstrip('.'))
    return fuzzy or (_fallback_search(file_clean) if fallback_search else None)
