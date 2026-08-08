"""/s: Image garbage collector — scan vault .md for image references, move unreferenced images to TRASH.
"""
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from config import DEFAULT_IMAGE_PATH, OBSIDIAN_ROOT

PATTERN_IMG = re.compile(r'!\[[^\]]*\]\(([^)]+)\)')


def _extract_local_names(text: str) -> set:
    names = set()
    for m in PATTERN_IMG.finditer(text):
        url = m.group(1)
        normalized = url.replace('\\', '/')
        if url.startswith(('http://', 'https://')):
            continue
        if 'Vault/IMAGE' in normalized or '/images/' in normalized or normalized.startswith('images/'):
            names.add(os.path.basename(normalized))
    return names


def _scan_one(md_path: Path) -> set:
    try:
        return _extract_local_names(md_path.read_text(encoding='utf-8'))
    except Exception:
        return set()


def run_clean_images(path_vault=None, path_images=None, path_trash=None):
    vault = Path(path_vault or OBSIDIAN_ROOT)
    images_dir = Path(path_images or DEFAULT_IMAGE_PATH)
    trash_dir = Path(path_trash or (vault / 'TRASH' / 'Image'))

    actual_files = {f.name for f in images_dir.iterdir() if f.is_file()}
    print(f'IMAGE目录文件: {len(actual_files)}')

    md_files = list(vault.rglob('*.md'))
    print(f'扫描MD文件: {len(md_files)}')

    referenced = set()
    with ThreadPoolExecutor() as ex:
        futures = [ex.submit(_scan_one, p) for p in md_files]
        for i, fut in enumerate(as_completed(futures), 1):
            referenced.update(fut.result())
            if i % 200 == 0:
                print(f'  进度: {i}/{len(md_files)}')

    print(f'已引用图片: {len(referenced)}')

    unreferenced = actual_files - referenced
    print(f'未引用图片: {len(unreferenced)}')

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
    print(f'已移入TRASH: {moved}/{len(unreferenced)}')
