"""/s: Vault-to-vault Obsidian note archiver.
Hardlinks/copies a .md + its PA (paper-analyze), PT (paper-translate), FE (_figures.md)
and image assets into a target Obsidian vault, auto-fixing markdown image paths.
"""
import os
import re
import shutil
from pathlib import Path
from typing import Optional

from core.frontmatter import parse_frontmatter_str
from config import DEFAULT_IMAGE_PATH


def _norm(s: str) -> str:
    return re.sub(r'[-\u2013\u2014]', '-', s)


PATTERN_IMG = re.compile(
    r'(!\[[^\]]*\])\((?:[A-Z]:[\\/].*?images|\.\.[\\/]images)[\\/]([a-f0-9]+\.(?:jpg|png|jpeg|gif))\)',
    re.IGNORECASE,
)
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


def _wikilink_page(raw) -> Optional[str]:
    if not raw:
        return None
    m = PATTERN_WIKILINK.search(str(raw))
    return m.group(1) if m else None


def _replace_img(m, *, src_images, dst_images, prefix, counter):
    alt, img = m.group(1), m.group(2)
    dst_img = dst_images / img
    if not dst_img.exists():
        for src_dir in (src_images, DEFAULT_IMAGE_PATH):
            if src_dir is None or src_dir == dst_images:
                continue
            src_img = src_dir / img
            if src_img.exists():
                shutil.copy2(src_img, dst_img)
                break
    counter[0] += 1
    return f'{alt}({prefix}{img})'


def _fix_image_paths(md_file: Path, src_images: Path, dst_images: Path) -> int:
    try:
        content = md_file.read_text(encoding='utf-8')
    except Exception:
        return 0
    prefix = dst_images.resolve().as_posix() + '/'
    counter = [0]
    content = PATTERN_IMG.sub(
        lambda m: _replace_img(m, src_images=src_images, dst_images=dst_images,
                               prefix=prefix, counter=counter),
        content)
    if counter[0]:
        md_file.write_text(content, encoding='utf-8')
    return counter[0]


def _find_parent(path: Path, condition):
    p = path
    while p != p.parent:
        if condition(p):
            return p
        p = p.parent
    return None if not condition(p) else p


def _find_clippings_dir(path: Path) -> Optional[Path]:
    return _find_parent(path, lambda p: p.name == 'Clippings')


def _find_vault(path: Path) -> Path:
    vault = _find_parent(path, lambda p: (p / '.obsidian').exists())
    if vault is None:
        raise SystemExit(f'Target not under any Obsidian vault: {path}')
    return vault


def _try_copy(src: Path, dst: Path) -> str:
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

    vault = _find_vault(dst_dir)
    src_clippings = _find_clippings_dir(src)
    src_images = (src_clippings / 'images') if src_clippings else None
    src_vault_sub = src_clippings.parent if src_clippings else None

    rel = dst_dir.relative_to(vault)
    if not rel.parts:
        dst_dir = dst_dir / 'Clippings'
        rel = dst_dir.relative_to(vault)
    mother = rel.parts[0]
    if mother == 'Clippings':
        dst_images = vault / 'IMAGE'
        dst_claude = vault / 'Claude'
        dst_chi = vault / 'Chi'
    else:
        dst_images = vault / 'IMAGE'
        dst_claude = vault / mother / 'Claude'
        dst_chi = vault / mother / 'Chi'
        if len(rel.parts) == 2 and rel.parts[1] == 'Clippings':
            dst_dir = dst_dir / 'PENDING'

    dst_dir.mkdir(parents=True, exist_ok=True)
    dst_images.mkdir(parents=True, exist_ok=True)
    rows = []

    md_dst = dst_dir / src.name
    status = _try_copy(src, md_dst)
    rows.append(('.md', status, md_dst))

    if src_images and md_dst.exists():
        n = _fix_image_paths(md_dst, src_images, dst_images)
        rows.append(('图片', f'{n}张', dst_images))

    src_claude = (src_vault_sub / 'Claude') if src_vault_sub else None
    src_chi = (src_vault_sub / 'Chi') if src_vault_sub else None
    link_map = [
        ('paper-analyze', src_claude, dst_claude),
        ('paper-translate', src_chi, dst_chi),
    ]

    pa_name = None
    for prop, src_dir_link, dst_link in link_map:
        page = _wikilink_page(fm.get(prop, ''))
        if not page or src_dir_link is None:
            continue
        if prop == 'paper-analyze':
            pa_name = page
        target_path = _resolve_note(src_dir_link, page)
        dst = dst_link / f'{page}.md'
        dst_link.mkdir(parents=True, exist_ok=True)
        label = 'PA' if prop == 'paper-analyze' else 'PT'
        rows.append((label, _try_copy(target_path, dst), dst if target_path.exists() else target_path))
        if target_path.exists() and dst.exists():
            fixed = _fix_image_paths(dst, src_images, dst_images) if src_images else 0
            if fixed:
                rows.append((f'{label}图片', f'{fixed}张', str(dst)))

    if pa_name and src_vault_sub:
        claude_src = src_vault_sub / 'Claude'
        tgt = _norm(pa_name)
        for figs in claude_src.glob('*_figures.md'):
            if _norm(figs.stem) != f'{tgt}_figures':
                continue
            fig_dst = dst_claude / f'{tgt}_figures.md'
            rows.append(('Figures', _try_copy(figs, fig_dst), fig_dst))
            if fig_dst.exists():
                fixed = _fix_image_paths(fig_dst, src_images, dst_images) if src_images else 0
                if fixed:
                    rows.append(('Figures图片', f'{fixed}张', str(fig_dst)))

    status_map = {'hardlinked': '硬链接', 'copied': '已复制', 'exists': '跳过(已存在)', 'not found': '未找到'}
    for item, status, path in rows:
        status_disp = status_map.get(status, status)
        print(f'| {item} | {status_disp} | {path} |')
    print()
    print('=== 请手动验证图片链接是否正确 ===')
