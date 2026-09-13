"""/s: Replace Unicode symbols with ASCII equivalents across Obsidian Vault .md files."""

import re
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

from core import iter_vault_dirs
from core.refs import canonicalize_stem

_WIKILINK_RE = re.compile(r'\[\[([^|#\]\n]+)([|#][^\]\n]*)?\]\]')
_SUBDIRS = ('Claude', 'Chi', 'Clippings')


def _iter_subdirs(vault_root: Path) -> Iterator[Path]:
    for vault_dir in iter_vault_dirs(vault_root):
        for sub in _SUBDIRS:
            sd = vault_dir / sub
            if sd.is_dir():
                yield sd


def _scan_vault(vault_root: Path) -> Tuple[List[Path], Dict[str, str], List[Tuple[Path, str]]]:
    """单次全库扫描，同时收集 (所有md文件, 需规范化stem映射, 待重命名路径)。"""
    md_files: List[Path] = []
    changed: Dict[str, str] = {}
    changed_paths: List[Tuple[Path, str]] = []
    for sd in _iter_subdirs(vault_root):
        for md in sorted(sd.rglob('*.md')):
            md_files.append(md)
            norm = canonicalize_stem(md.stem)
            if norm != md.stem:
                changed[md.stem] = norm
                changed_paths.append((md, norm))
    return md_files, changed, changed_paths


def _fix_wikilinks(content: str, stem_map: Dict[str, str]) -> Tuple[str, int]:
    """stem_map 同时含 {旧stem: 新stem} 与 {新stem: 新stem}，按原样或规范化目标命中。"""
    count = 0

    def _replace(m):
        nonlocal count
        target = m.group(1).strip()
        new_target = stem_map.get(target) or stem_map.get(canonicalize_stem(target))
        if not new_target or new_target == target:
            return m.group(0)
        count += 1
        rest = m.group(2) or ''
        return f'[[{new_target}{rest}]]'

    return _WIKILINK_RE.sub(_replace, content), count


def run_unify_symbols(vault_root: str = r'C:\Vault', dry_run: bool = True) -> bool:
    vault_root = Path(vault_root)
    md_files, changed, changed_paths = _scan_vault(vault_root)

    if not changed:
        print('所有文件名已规范化，无需修复')
        return True

    print(f'发现 {len(changed)} 个需要规范化的文件名:\n')
    for old, new in sorted(changed.items()):
        print(f'  {old}\n  -> {new}\n')

    if dry_run:
        print('[DRY RUN] 未执行实际修改。加 --force 以执行')
        return True

    print(f'扫描 {len(md_files)} 个 .md 文件中的 wikilink...')

    link_map = {**{v: v for v in changed.values()}, **changed}
    total_links = 0
    for md in md_files:
        try:
            content = md.read_text(encoding='utf-8')
        except Exception:
            continue
        new_content, link_count = _fix_wikilinks(content, link_map)
        if link_count:
            total_links += link_count
            try:
                md.write_text(new_content, encoding='utf-8')
            except Exception as e:
                print(f'  写入失败 {md}: {e}')
                continue
            print(f'  [{link_count} links] {md.relative_to(vault_root)}')

    renames = 0
    for md, new_stem in changed_paths:
        new_path = md.with_name(f'{new_stem}{md.suffix}')
        try:
            md.rename(new_path)
            renames += 1
            print(f'  RENAME {md.relative_to(vault_root)}')
        except Exception as e:
            print(f'  重命名失败 {md}: {e}')

    print(f'\n完成: {renames} 个文件重命名, {total_links} 个链接更新')
    return True
