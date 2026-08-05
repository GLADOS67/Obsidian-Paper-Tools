"""/s: Obsidian URI (obsidian://open?vault=...&file=...) resolver with fuzzy glob fallback.
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
    return None


def _fallback_search(file_clean: str) -> Optional[Path]:
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
    md_candidate = _try_suffix(full_path, '.md')
    if md_candidate:
        return md_candidate
    stripped_candidate = _try_strip_dot(full_path)
    if stripped_candidate:
        return stripped_candidate
    fuzzy = _fuzzy_search(full_path.parent, full_path.stem.strip('. \t').rstrip('.'))
    if fuzzy:
        return fuzzy
    return _fallback_search(file_clean) if fallback_search else None
