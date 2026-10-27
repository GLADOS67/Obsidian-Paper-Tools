import os
import re
import shutil
from pathlib import Path

from config import DEFAULT_IMAGE_PATH, OBSIDIAN_ROOT
from core.cache import map_parallel, read_text_safe

PATTERN_IMG = re.compile(r'!\[[^\]]*\]\(([^)]+)\)')


def image_names(images_dir: Path) -> set:
    """images_dir 下所有实际存在的图片文件名集合。"""
    return {f.name for f in images_dir.iterdir() if f.is_file()}


def _scan_one(md_path: Path) -> set:
    text = read_text_safe(md_path)
    if not text:
        return set()
    names = set()
    for m in PATTERN_IMG.finditer(text):
        url = m.group(1)
        if url.startswith(('http://', 'https://')):
            continue
        normalized = url.replace('\\', '/')
        if 'Vault/IMAGE' in normalized or '/images/' in normalized or normalized.startswith('images/'):
            names.add(os.path.basename(normalized))
    return names


def scan_referenced_images(md_files, show_progress: bool = False) -> set:
    """并行扫描 .md 文件，返回被引用的本地图片文件名集合。"""
    referenced = set()
    for i, names in enumerate(map_parallel(_scan_one, md_files), 1):
        referenced.update(names)
        if show_progress and i % 200 == 0:
            print(f'  进度: {i}/{len(md_files)}')
    return referenced


def move_images_to(names, images_dir: Path, trash_dir: Path) -> int:
    """将 names 中的图片从 images_dir 并行移入 trash_dir，返回移动成功数。"""
    trash_dir.mkdir(parents=True, exist_ok=True)

    def _mv(name) -> int:
        try:
            shutil.move(str(images_dir / name), str(trash_dir / name))
            return 1
        except Exception:
            return 0

    return sum(map_parallel(_mv, names))


def prune_unreferenced_images(md_files, images_dir: Path, trash_dir: Path,
                              show_progress: bool = False) -> tuple:
    """扫描 MD 引用并将未引用图片移入 trash_dir（clean_images / trash 共用清理主链）。

    返回 (referenced, unreferenced, moved)；无冗余时不建目录不移动，moved=0。
    """
    referenced = scan_referenced_images(md_files, show_progress=show_progress)
    unreferenced = image_names(images_dir) - referenced
    moved = move_images_to(unreferenced, images_dir, trash_dir) if unreferenced else 0
    return referenced, unreferenced, moved


def run_clean_images(path_vault=None, path_images=None, path_trash=None):
    vault = Path(path_vault or OBSIDIAN_ROOT)
    images_dir = Path(path_images or DEFAULT_IMAGE_PATH)
    trash_dir = Path(path_trash or (vault / 'TRASH' / 'Image'))

    print(f'IMAGE目录文件: {len(image_names(images_dir))}')
    md_files = list(vault.rglob('*.md'))
    print(f'扫描MD文件: {len(md_files)}')
    referenced, unreferenced, moved = prune_unreferenced_images(
        md_files, images_dir, trash_dir, show_progress=True)
    print(f'已引用图片: {len(referenced)}')
    print(f'未引用图片: {len(unreferenced)}')

    if not unreferenced:
        print('无冗余图片')
        return
    print(f'已移入TRASH: {moved}/{len(unreferenced)}')
