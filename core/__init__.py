"""/s: core package for Obsidian Vault tools: crossref_api, doi, frontmatter, http, markdown_utils, obsidian_path, pdf_extractor, refs. Crossref API, PubMed E-utilities, DOI, MinerU."""

import os
import shutil
from pathlib import Path

_VAULT_DIRS = {'Clippings', 'Claude', 'Chi'}
_VAULT_SKIP = {'.obsidian', 'TRASH', 'IMAGE', 'PDF', 'ZIP'}


def is_vault_dir(p: Path) -> bool:
    if not p.is_dir() or p.name.startswith('.') or p.name in _VAULT_SKIP:
        return False
    return any((p / d).is_dir() for d in _VAULT_DIRS)


def iter_vault_dirs(vault_root: Path):
    """按名称排序产出 vault_root 下的有效 vault 目录。"""
    return (d for d in sorted(vault_root.iterdir()) if is_vault_dir(d))


def try_copy(src: Path, dst: Path) -> bool:
    if not src.exists() or dst.exists():
        return False
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)
    return True
