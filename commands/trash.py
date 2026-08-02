"""/s: Obsidian vault subdirectory archiver — move subdirs to dated trash/ folder, preserve .obsidian.
"""
import os
import shutil
from datetime import datetime
from pathlib import Path


def run_trash(path: str) -> None:
    p = Path(path)
    white = {'.obsidian', 'TRASH'}
    folders = [f for f in p.iterdir() if f.is_dir() and f.name not in white]
    backup_dir = p / 'trash' / datetime.now().strftime('%Y%m%d')
    backup_dir.mkdir(parents=True, exist_ok=True)
    for f in folders:
        src = str(f)
        shutil.move(src, str(backup_dir / f.name))
        os.mkdir(src)
    print(f'已归档 {len(folders)} 个文件夹到 {backup_dir}')
