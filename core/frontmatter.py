"""/s: YAML frontmatter parse/dump for Obsidian Vault notes."""

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
try:
    from yaml import CSafeLoader as _YamlLoader, CSafeDumper as _YamlDumper
except ImportError:
    from yaml import SafeLoader as _YamlLoader, SafeDumper as _YamlDumper

PATTERN_FRONTMATTER = re.compile(r'^---\r?\n(.*?)\r?\n---', re.DOTALL | re.MULTILINE)
_ENCODINGS = ('utf-8', 'gbk')


def parse_frontmatter_str(content: str) -> Tuple[Dict, str]:
    fm_match = PATTERN_FRONTMATTER.search(content)
    if not fm_match:
        return {}, content
    try:
        loaded = yaml.load(fm_match.group(1), Loader=_YamlLoader)
        fm = loaded if isinstance(loaded, dict) else {}
    except Exception:
        fm = {}
    return fm, content[fm_match.end():].lstrip('\n\r')


def parse_frontmatter_file(path: Path) -> Tuple[Optional[Dict], str]:
    data = path.read_bytes()
    for enc in _ENCODINGS:
        try:
            raw = data.decode(enc).lstrip('\ufeff')
            break
        except UnicodeDecodeError:
            pass
    else:
        raw = data.decode('utf-8', errors='replace')
    fm, rest = parse_frontmatter_str(raw)
    return (fm if fm else None), rest


def read_fm(path: Path) -> Tuple[Dict, str]:
    """Read .md with encoding fallback, returning (fm_dict, body)."""
    fm, body = parse_frontmatter_file(path)
    return (fm if fm else {}), body


def dump_frontmatter(fm: Dict, body: str) -> str:
    if fm:
        yaml_str = yaml.dump(fm, sort_keys=False, allow_unicode=True,
                             default_flow_style=False, Dumper=_YamlDumper).rstrip('\n')
        return f'---\n{yaml_str}\n---\n{body}'
    return body


def cited_by_fresh(fm: Dict, days: int = 30) -> bool:
    val = fm.get('cited_by_date')
    if not val:
        return False
    try:
        last = datetime.strptime(str(val)[:10], '%Y-%m-%d')
    except ValueError:
        return False
    return (datetime.now() - last).days < days


def build_doi_set(md_dir: Path, include_refs: bool = False) -> set:
    """Collect all DOIs from frontmatter of .md files in directory tree.

    When include_refs is True, also gather DOIs from 'reference' and 'cited_by' wikilinks.
    """
    from core.doi import extract_doi_from_frontmatter, PATTERN_DOI
    existing = set()
    for md_file in md_dir.rglob('*.md'):
        try:
            fm, body = read_fm(md_file)
        except Exception:
            continue
        if main := extract_doi_from_frontmatter(fm):
            existing.add(main.lower())
        if include_refs:
            for key in ('reference', 'cited_by'):
                for ref in fm.get(key, []):
                    if isinstance(ref, str) and (m := PATTERN_DOI.search(ref)):
                        existing.add(m.group(0).lower())
    return existing
