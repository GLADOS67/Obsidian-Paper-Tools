"""/s: Replace Unicode symbols with ASCII equivalents across Obsidian Vault .md files."""

import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

from core import is_vault_dir
from core.refs import canonicalize_stem

_WIKILINK_RE = re.compile(r'\[\[([^|#\]\n]+)([|#][^\]\n]*)?\]\]')


def _find_changed_files(vault_root: Path) -> Dict[str, str]:
    changed: Dict[str, str] = {}
    for vault_dir in sorted(vault_root.iterdir()):
        if not is_vault_dir(vault_dir):
            continue
        for sub in ('Claude', 'Chi', 'Clippings'):
            sd = vault_dir / sub
            if not sd.is_dir():
                continue
            for md in sorted(sd.rglob('*.md')):
                norm = canonicalize_stem(md.stem)
                if norm != md.stem:
                    changed[md.stem] = norm
    return changed


def _fix_wikilinks(content: str, stem_map: Dict[str, str]) -> Tuple[str, int]:
    count = 0

    def _replace(m):
        nonlocal count
        target = m.group(1).strip()
        norm = canonicalize_stem(target)
        if norm in stem_map:
            new_target = stem_map[norm]
            count += 1
            rest = m.group(2) or ''
            return f'[[{new_target}{rest}]]'
        return m.group(0)

    return _WIKILINK_RE.sub(_replace, content), count


def _collect_md_files(vault_root: Path) -> List[Path]:
    result: List[Path] = []
    for vault_dir in sorted(vault_root.iterdir()):
        if not is_vault_dir(vault_dir):
            continue
        for sub in ('Claude', 'Chi', 'Clippings'):
            sd = vault_dir / sub
            if not sd.is_dir():
                continue
            result.extend(sorted(sd.rglob('*.md')))
    return result


def run_unify_symbols(vault_root: str = r'C:\Vault', dry_run: bool = True) -> bool:
    vault_root = Path(vault_root)
    changed = _find_changed_files(vault_root)

    if not changed:
        print('所有文件名已规范化，无需修复')
        return True

    print(f'发现 {len(changed)} 个需要规范化的文件名:\n')
    for old, new in sorted(changed.items()):
        print(f'  {old}\n  -> {new}\n')

    if dry_run:
        print('[DRY RUN] 未执行实际修改。加 --force 以执行')
        return True

    md_files = _collect_md_files(vault_root)
    print(f'扫描 {len(md_files)} 个 .md 文件中的 wikilink...')

    total_links = 0
    for md in sorted(md_files):
        try:
            content = md.read_text(encoding='utf-8')
        except Exception:
            continue
        new_content, link_count = _fix_wikilinks(content, changed)
        if link_count:
            total_links += link_count
            try:
                md.write_text(new_content, encoding='utf-8')
            except Exception as e:
                print(f'  写入失败 {md}: {e}')
                continue
            print(f'  [{link_count} links] {md.relative_to(vault_root)}')

    renames = 0
    for old_stem, new_stem in sorted(changed.items()):
        for vault_dir in sorted(vault_root.iterdir()):
            if not is_vault_dir(vault_dir):
                continue
            for sub in ('Claude', 'Chi', 'Clippings'):
                sd = vault_dir / sub
                if not sd.is_dir():
                    continue
                for md in sorted(sd.rglob(f'{old_stem}.md')):
                    new_path = md.with_name(f'{new_stem}{md.suffix}')
                    try:
                        md.rename(new_path)
                        renames += 1
                        print(f'  RENAME {md.relative_to(vault_root)}')
                    except Exception as e:
                        print(f'  重命名失败 {md}: {e}')

    print(f'\n完成: {renames} 个文件重命名, {total_links} 个链接更新')
    return True
