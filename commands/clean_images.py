import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from config import DEFAULT_IMAGE_PATH, OBSIDIAN_ROOT

PATTERN_IMG = re.compile(r'!\[[^\]]*\]\(([^)]+)\)')


def image_names(images_dir: Path) -> set:
    """images_dir 下所有实际存在的图片文件名集合。"""
    return {f.name for f in images_dir.iterdir() if f.is_file()}


def _scan_one(md_path: Path) -> set:
    try:
        text = md_path.read_text(encoding='utf-8')
    except Exception:
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
    md_files = list(md_files)
    referenced = set()
    with ThreadPoolExecutor() as ex:
        for i, names in enumerate(ex.map(_scan_one, md_files), 1):
            referenced.update(names)
            if show_progress and i % 200 == 0:
                print(f'  进度: {i}/{len(md_files)}')
    return referenced


def move_images_to(names, images_dir: Path, trash_dir: Path) -> int:
    """将 names 中的图片从 images_dir 移入 trash_dir，返回移动成功数。"""
    trash_dir.mkdir(parents=True, exist_ok=True)
    moved = 0
    for name in names:
        try:
            shutil.move(str(images_dir / name), str(trash_dir / name))
            moved += 1
        except Exception:
            pass
    return moved


def run_clean_images(path_vault=None, path_images=None, path_trash=None):
    vault = Path(path_vault or OBSIDIAN_ROOT)
    images_dir = Path(path_images or DEFAULT_IMAGE_PATH)
    trash_dir = Path(path_trash or (vault / 'TRASH' / 'Image'))

    actual_files = image_names(images_dir)
    print(f'IMAGE目录文件: {len(actual_files)}')

    md_files = list(vault.rglob('*.md'))
    print(f'扫描MD文件: {len(md_files)}')
    referenced = scan_referenced_images(md_files, show_progress=True)
    print(f'已引用图片: {len(referenced)}')

    unreferenced = actual_files - referenced
    print(f'未引用图片: {len(unreferenced)}')

    if not unreferenced:
        print('无冗余图片')
        return
    moved = move_images_to(unreferenced, images_dir, trash_dir)
    print(f'已移入TRASH: {moved}/{len(unreferenced)}')
