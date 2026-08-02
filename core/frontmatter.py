"""/s: YAML frontmatter (YFM / Jekyll-style --- ) parser & dumper for Obsidian .md notes.
Uses PyYAML with CSafeLoader/CSafeDumper when available for speed.
"""
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

import yaml
try:
    from yaml import CSafeLoader as _YamlLoader, CSafeDumper as _YamlDumper
except ImportError:
    from yaml import SafeLoader as _YamlLoader, SafeDumper as _YamlDumper

PATTERN_FRONTMATTER = re.compile(r'^---\n(.*?)\n---', re.DOTALL | re.MULTILINE)


def parse_frontmatter_str(content: str) -> Tuple[Dict, str]:
    fm_match = PATTERN_FRONTMATTER.search(content)
    if not fm_match:
        return {}, content
    try:
        loaded = yaml.load(fm_match.group(1), Loader=_YamlLoader)
        fm = loaded if isinstance(loaded, dict) else {}
    except Exception:
        fm = {}
    return fm, content[fm_match.end():].lstrip('\n')


def parse_frontmatter_file(path: Path) -> Tuple[Optional[Dict], str]:
    data = path.read_bytes()
    for enc in ('utf-8', 'utf-8-sig', 'gbk', 'gb2312'):
        try:
            raw = data.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        raw = data.decode('utf-8', errors='replace')

    fm, rest = parse_frontmatter_str(raw)
    return (fm if fm else None), rest


def dump_frontmatter(fm: Dict, body: str) -> str:
    if fm:
        yaml_str = yaml.dump(fm, sort_keys=False, allow_unicode=True,
                             default_flow_style=False, Dumper=_YamlDumper).rstrip('\n')
        return f'---\n{yaml_str}\n---\n{body}'
    return body
