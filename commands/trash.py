"""/s: Obsidian vault subdirectory archiver.
"""
import os
import shutil
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from commands.clean_images import _scan_one
from config import DEFAULT_IMAGE_PATH, DEFAULT_ZIP_PATH, OBSIDIAN_ROOT


def _scan_referenced(vault: Path) -> set:
    md_files = list(vault.rglob('*.md'))
    referenced = set()
    with ThreadPoolExecutor() as ex:
        futures = [ex.submit(_scan_one, p) for p in md_files]
        for fut in as_completed(futures):
            referenced.update(fut.result())
    print(f'扫描MD: {len(md_files)}, 引用图片: {len(referenced)}')
    return referenced


def _trash_unreferenced(images_dir: Path, referenced: set, trash_dir: Path) -> None:
    actual = {f.name for f in images_dir.iterdir() if f.is_file()}
    unreferenced = actual - referenced
    if not unreferenced:
        print('无冗余图片')
        return
    trash_dir.mkdir(parents=True, exist_ok=True)
    moved = 0
    for name in unreferenced:
        try:
            shutil.move(str(images_dir / name), str(trash_dir / name))
            moved += 1
        except Exception:
            pass
    print(f'冗余图片移入 {trash_dir}: {moved}/{len(unreferenced)}')


def _extract_entry(zf: zipfile.ZipFile, entry: str, dest: Path) -> None:
    with zf.open(entry) as src, open(dest, 'wb') as dst:
        shutil.copyfileobj(src, dst)


def _restore_missing(images_dir: Path, referenced: set, zip_dir: Path) -> None:
    actual = {f.name for f in images_dir.iterdir() if f.is_file()}
    missing = referenced - actual
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
                    _extract_entry(zf, entry, images_dir / name)
                    missing.discard(name)
                    restored += 1
        except Exception:
            pass
    print(f'缺失图片已提取: {restored}, 仍缺失: {len(missing)}')
    for name in sorted(missing):
        print(f'  未找到: {name}')


def run_trash(path: str) -> None:
    referenced = _scan_referenced(OBSIDIAN_ROOT)
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
