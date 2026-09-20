import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from itertools import repeat
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
try:
    from yaml import CSafeLoader as _YamlLoader, CSafeDumper as _YamlDumper
except ImportError:
    from yaml import SafeLoader as _YamlLoader, SafeDumper as _YamlDumper

from core.doi import PATTERN_DOI, extract_doi_from_frontmatter, make_wikilink, process_doi

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
            continue
    else:
        raw = data.decode('utf-8', errors='replace')
    fm, rest = parse_frontmatter_str(raw)
    return fm or None, rest


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


def apply_cited_by(fm: Dict, citing_dois: list) -> None:
    """统一写入 cited_by_date / cited_by（citing_dois 为空时仅刷新日期）。"""
    fm.pop('cited_by_count', None)
    fm['cited_by_date'] = datetime.now().strftime('%Y-%m-%d')
    if citing_dois:
        fm['cited_by'] = [make_wikilink(process_doi(d)[0]) for d in citing_dois]


def _collect_file_dois(md_file: Path, include_refs: bool) -> List[str]:
    try:
        fm = parse_frontmatter_file(md_file)[0] or {}
    except Exception:
        return []
    dois = []
    if main := extract_doi_from_frontmatter(fm):
        dois.append(main.lower())
    if include_refs and fm:
        for key in ('reference', 'cited_by'):
            for ref in fm.get(key, []):
                if isinstance(ref, str) and (m := PATTERN_DOI.search(ref)):
                    dois.append(m.group(0).lower())
    return dois


def build_doi_set(md_dir: Path, include_refs: bool = False) -> set:
    """Collect all DOIs from frontmatter of .md files in directory tree.

    When include_refs is True, also gather DOIs from 'reference' and 'cited_by' wikilinks.
    """
    existing = set()
    with ThreadPoolExecutor() as ex:
        for dois in ex.map(_collect_file_dois, md_dir.rglob('*.md'), repeat(include_refs)):
            existing.update(dois)
    return existing
