import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
try:
    from yaml import CSafeLoader as _YamlLoader, CSafeDumper as _YamlDumper
except ImportError:
    from yaml import SafeLoader as _YamlLoader, SafeDumper as _YamlDumper

from core.cache import read_text_auto
from core.doi import PATTERN_DOI, extract_doi_from_frontmatter, make_wikilink, process_doi

PATTERN_FRONTMATTER = re.compile(r'^---\r?\n(.*?)\r?\n---', re.DOTALL | re.MULTILINE)


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
    raw = read_text_auto(path)
    fm, rest = parse_frontmatter_str(raw)
    return fm or None, rest


def parse_frontmatter_batch(paths: List[Path], fm_only: bool = False):
    """并行解析多个文件的 frontmatter（保持输入顺序）；fm_only 时返回 [fm or None]。"""
    with ThreadPoolExecutor() as ex:
        parsed = list(ex.map(parse_frontmatter_file, paths))
    if fm_only:
        return [fm for fm, _ in parsed]
    return parsed


def dump_frontmatter(fm: Dict, body: str) -> str:
    if fm:
        yaml_str = yaml.dump(fm, sort_keys=False, allow_unicode=True,
                             default_flow_style=False, Dumper=_YamlDumper).rstrip('\n')
        # 换行归一：Windows write_text 会把 \n→\r\n，若 body 残留 \r\n 会变 \r\r\n 损坏
        body = body.replace('\r\n', '\n').replace('\r', '\n')
        return f'---\n{yaml_str}\n---\n{body}'
    return body


def fm_title(fm: Dict, fallback: str = '') -> str:
    """frontmatter title → 字符串：列表拼接、去空白；空或 [[wikilink]] 包裹视为无效，回退 fallback。"""
    if not fm:
        return fallback
    raw = fm.get('title')
    if isinstance(raw, list):
        raw = ' '.join(str(t) for t in raw)
    title = str(raw).strip() if raw else ''
    return title if title and '[' not in title and ']' not in title else fallback


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


def build_doi_set(md_dir: Path, include_refs: bool = False) -> set:
    """并行收集目录树下所有 MD 的 frontmatter DOI（去重、小写）。

    include_refs 为 True 时同时收集 reference / cited_by wikilink 中的 DOI。
    """
    def _collect(md_file: Path) -> set:
        try:
            fm = parse_frontmatter_file(md_file)[0] or {}
        except Exception:
            return set()
        dois = set()
        if main := extract_doi_from_frontmatter(fm):
            dois.add(main.lower())
        if include_refs and fm:
            for key in ('reference', 'cited_by'):
                for ref in fm.get(key, []):
                    if isinstance(ref, str) and (m := PATTERN_DOI.search(ref)):
                        dois.add(m.group(0).lower())
        return dois

    with ThreadPoolExecutor() as ex:
        return set().union(*ex.map(_collect, md_dir.rglob('*.md')))
