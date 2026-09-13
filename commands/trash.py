"""/s: Archive subdirectories into dated folders inside Obsidian Vault."""

import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from commands.clean_images import image_names, move_images_to, scan_referenced_images
from config import DEFAULT_IMAGE_PATH, DEFAULT_ZIP_PATH, OBSIDIAN_ROOT


def _trash_unreferenced(images_dir: Path, referenced: set, trash_dir: Path) -> None:
    unreferenced = image_names(images_dir) - referenced
    if not unreferenced:
        print('无冗余图片')
        return
    moved = move_images_to(unreferenced, images_dir, trash_dir)
    print(f'冗余图片移入 {trash_dir}: {moved}/{len(unreferenced)}')


def _restore_missing(images_dir: Path, referenced: set, zip_dir: Path) -> None:
    missing = referenced - image_names(images_dir)
    if not missing:
        print('无缺失图片')
        return
    restored = 0
    for zp in zip_dir.glob('*.zip'):
        if not missing:
            break
        try:
            with zipfile.ZipFile(zp) as zf:
                hits = [e for e in zf.namelist() if os.path.basename(e) in missing]
                for entry in hits:
                    name = os.path.basename(entry)
                    with zf.open(entry) as src, open(images_dir / name, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                    missing.discard(name)
                    restored += 1
        except Exception:
            pass
    print(f'缺失图片已提取: {restored}, 仍缺失: {len(missing)}')
    for name in sorted(missing):
        print(f'  未找到: {name}')


def run_trash(path: str) -> None:
    md_files = list(OBSIDIAN_ROOT.rglob('*.md'))
    referenced = scan_referenced_images(md_files)
    print(f'扫描MD: {len(md_files)}, 引用图片: {len(referenced)}')
    _trash_unreferenced(DEFAULT_IMAGE_PATH, referenced, OBSIDIAN_ROOT / 'TRASH' / 'Image')
    _restore_missing(DEFAULT_IMAGE_PATH, referenced, DEFAULT_ZIP_PATH)

    p = Path(path)
    white = {'.obsidian', 'TRASH'}
    folders = [f for f in p.iterdir() if f.is_dir() and f.name not in white]
    if not folders:
        print('没有需要归档的文件夹')
        return
    backup_dir = p / 'trash' / datetime.now().strftime('%Y%m%d')
    backup_dir.mkdir(parents=True, exist_ok=True)
    for f in folders:
        shutil.move(str(f), str(backup_dir / f.name))
        os.mkdir(str(f))
    print(f'已归档 {len(folders)} 个文件夹到 {backup_dir}')
