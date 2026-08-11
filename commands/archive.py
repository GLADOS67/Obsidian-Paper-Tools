"""/s: Hardlink/copy notes and assets across Obsidian Vaults."""

import os
import re
import shutil
from pathlib import Path
from typing import Optional

from core.frontmatter import parse_frontmatter_str


def _norm(s: str) -> str:
    return re.sub(r'[-\u2013\u2014]', '-', s)


PATTERN_WIKILINK = re.compile(r'\[\[([^\]|]+)')


def _resolve_note(src_dir: Path, page: str) -> Path:
    exact = src_dir / f'{page}.md'
    if exact.exists() or not src_dir.exists():
        return exact
    tgt = _norm(page)
    for f in src_dir.glob('*.md'):
        if _norm(f.stem) == tgt:
            return f
    return exact


def _find_parent(path: Path, condition) -> Optional[Path]:
    p = path
    while not condition(p) and p != p.parent:
        p = p.parent
    return p if condition(p) else None


def _copy_file(src: Path, dst: Path) -> str:
    if not src.exists():
        return 'not found'
    if dst.exists():
        return 'exists'
    try:
        os.link(src, dst)
        return 'hardlinked'
    except OSError:
        shutil.copy2(src, dst)
        return 'copied'


def run_archive(source: str, target: str) -> None:
    src = Path(source).resolve()
    dst_dir = Path(target).resolve()
    if not src.exists():
        raise SystemExit(f'源文件不存在: {src}')

    content = src.read_text(encoding='utf-8')
    fm, _ = parse_frontmatter_str(content)

    vault = _find_parent(dst_dir, lambda p: (p / '.obsidian').exists())
    if vault is None:
        raise SystemExit(f'Target not under any Obsidian vault: {dst_dir}')
    src_clippings = _find_parent(src, lambda p: p.name == 'Clippings')
    src_vault_sub = src_clippings.parent if src_clippings else None

    rel = dst_dir.relative_to(vault)
    if not rel.parts:
        dst_dir = dst_dir / 'Clippings'
        rel = dst_dir.relative_to(vault)
    mother = rel.parts[0]
    is_clippings = mother == 'Clippings'
    dst_claude = vault / 'Claude' if is_clippings else vault / mother / 'Claude'
    dst_chi = vault / 'Chi' if is_clippings else vault / mother / 'Chi'
    if not is_clippings and len(rel.parts) == 2 and rel.parts[1] == 'Clippings':
        dst_dir = dst_dir / 'PENDING'

    dst_dir.mkdir(parents=True, exist_ok=True)
    rows = [('.md', _copy_file(src, dst_dir / src.name), dst_dir / src.name)]

    src_claude = (src_vault_sub / 'Claude') if src_vault_sub else None
    src_chi = (src_vault_sub / 'Chi') if src_vault_sub else None
    link_config = [('paper-analyze', 'PA', src_claude, dst_claude),
                   ('paper-translate', 'PT', src_chi, dst_chi)]
    pa_name = None
    for prop, label, src_dir_link, dst_link in link_config:
        raw = fm.get(prop, '')
        m = PATTERN_WIKILINK.search(str(raw)) if raw else None
        page = m.group(1) if m else None
        if not page or src_dir_link is None:
            continue
        if label == 'PA':
            pa_name = page
        target_path = _resolve_note(src_dir_link, page)
        dst_link.mkdir(parents=True, exist_ok=True)
        dst = dst_link / f'{page}.md'
        rows.append((label, _copy_file(target_path, dst),
                     dst if target_path.exists() else target_path))

    if pa_name and src_vault_sub:
        src_claude_dir = src_vault_sub / 'Claude'
        tgt = _norm(pa_name)
        for figs in src_claude_dir.glob('*_figures.md'):
            if _norm(figs.stem) == f'{tgt}_figures':
                rows.append(('Figures', _copy_file(figs, dst_claude / f'{tgt}_figures.md'),
                             dst_claude / f'{tgt}_figures.md'))

    status_map = {'hardlinked': '硬链接', 'copied': '已复制',
                  'exists': '跳过(已存在)', 'not found': '未找到'}
    for item, status, path in rows:
        print(f'| {item} | {status_map.get(status, status)} | {path} |')
    print()
    print('=== 归档完成 ===')
