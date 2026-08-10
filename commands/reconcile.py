"""/s: Reconcile PA/PT/FE frontmatter links — scan wikilinks back to actual file content, detect broken/duplicate links.
"""
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from core.frontmatter import parse_frontmatter_file

WIKILINK_RE = re.compile(r'\[\[([^|]+)\|([^]]+)\]\]')
H1_WIKILINK_RE = re.compile(r'^#\s*\[\[([^|]+)\|([^]]+)\]\]')
_PA_PREFIX_RE = re.compile(r'^\d+_?\s*')

_VAULT_SKIP = {'.obsidian', 'TRASH', 'IMAGE', 'PDF', 'ZIP'}


def _parse_h1_wikilink(text: str) -> Optional[Tuple[str, str]]:
    for line in text.split('\n'):
        m = H1_WIKILINK_RE.match(line.strip())
        if m:
            return m.group(1).strip(), m.group(2).strip()
    return None


def _extract_wikilink_name(value) -> Optional[str]:
    if not value:
        return None
    m = WIKILINK_RE.search(str(value).replace('\n', ' '))
    return m.group(1).strip() if m else None


def _first_ref_target(ref_list: list) -> Optional[str]:
    if not ref_list:
        return None
    ref0 = (ref_list[0].replace('\n', ' ').strip() if isinstance(ref_list[0], str)
            else str(ref_list[0]).replace('\n', ' ').strip())
    m = WIKILINK_RE.search(ref0)
    return m.group(1).strip() if m else None


def _norm_stems(stem: str) -> Set[str]:
    return {stem, stem.replace(' ', '_'), stem.replace('_', ' ')}


def _pa_stem_variants(pa_stem: str) -> list:
    variants = [pa_stem]
    stripped = _PA_PREFIX_RE.sub('', pa_stem)
    if stripped and stripped != pa_stem:
        variants.append(stripped)
    for v in list(variants):
        if '_' in v:
            variants.append(v.replace('_', ' '))
        elif ' ' in v:
            variants.append(v.replace(' ', '_'))
    seen = set()
    return [x for x in variants if not (x in seen or seen.add(x))]


def _is_vault_dir(p: Path) -> bool:
    if not p.is_dir():
        return False
    if p.name.startswith('.') or p.name in _VAULT_SKIP:
        return False
    return any((p / d).is_dir() for d in ('Clippings', 'Claude', 'Chi'))


def _resolve_pa_target(pa_path: Path) -> Optional[str]:
    try:
        parsed = _parse_h1_wikilink(pa_path.read_text(encoding='utf-8'))
    except Exception:
        return None
    return parsed[0] if parsed else None


def _resolve_pt_target(chi_path: Path) -> Optional[str]:
    fm, _ = parse_frontmatter_file(chi_path)
    if not fm:
        return None
    pt = _extract_wikilink_name(fm.get('paper-translate'))
    return pt or _first_ref_target(fm.get('reference', []))


def build_clippings_index(vault_root: Path) -> Tuple[Dict[str, str], Set[str], Set[str]]:
    """返回 (clip_to_vault, pa_referenced, pt_referenced).

    clip_to_vault: {normalized_stem → vault_name}
    pa_referenced:  {pa_stem} — Clippings 的 paper-analyze 指向
    pt_referenced:  {chi_stem} — Clippings 的 paper-translate 指向
    """
    clip_to_vault: Dict[str, str] = {}
    pa_referenced: Set[str] = set()
    pt_referenced: Set[str] = set()

    for vault_dir in sorted(vault_root.iterdir()):
        if not _is_vault_dir(vault_dir):
            continue
        clip_dir = vault_dir / 'Clippings'
        if not clip_dir.is_dir():
            continue
        for md in sorted(clip_dir.rglob('*.md')):
            stem = md.stem
            for variant in _norm_stems(stem):
                if variant not in clip_to_vault:
                    clip_to_vault[variant] = vault_dir.name
            fm, _ = parse_frontmatter_file(md)
            if not fm:
                continue
            if pa := _extract_wikilink_name(fm.get('paper-analyze')):
                pa_referenced.add(pa)
            if pt := _extract_wikilink_name(fm.get('paper-translate')):
                pt_referenced.add(pt)
    return clip_to_vault, pa_referenced, pt_referenced


def resolve_action(target_stem: Optional[str], orig_vault: str, file_stem: str,
                   clip_to_vault: Dict[str, str], referenced: Set[str]) -> str:
    """返回 'keep' | 'move:{vault}' | 'trash'"""
    if target_stem:
        for variant in _norm_stems(target_stem):
            if variant in clip_to_vault:
                tv = clip_to_vault[variant]
                return 'keep' if tv == orig_vault else f'move:{tv}'
    if file_stem in referenced:
        return 'keep'
    return 'trash'


def _move_file(src: Path, dst_dir: Path, dry_run: bool) -> bool:
    dst = dst_dir / src.name
    if dst.exists():
        return False
    if not dry_run:
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    return True


def _rel(vault_root: Path, p: Path) -> str:
    try:
        return str(p.relative_to(vault_root))
    except ValueError:
        return str(p)


def run_reconcile(vault_root: str = r'C:\Vault',
                  trash_base: str = r'C:\Vault\TRASH\Claude',
                  dry_run: bool = True) -> bool:
    vault_root = Path(vault_root)
    trash_base = Path(trash_base)

    print(f'Vault: {vault_root}')
    if dry_run:
        print('[DRY RUN]\n')

    clip_to_vault, pa_referenced, pt_referenced = build_clippings_index(vault_root)
    vault_count = len(set(clip_to_vault.values()))
    print(f'索引: {len(clip_to_vault)} stems ({vault_count} vaults)  '
          f'PA反 {len(pa_referenced)}  PT反 {len(pt_referenced)}\n')

    pa_info: Dict[str, Tuple[Path, str, str]] = {}
    fe_info: Dict[str, Tuple[Path, str, str]] = {}
    pt_info: Dict[str, Tuple[Path, str, str]] = {}

    for vault_dir in sorted(vault_root.iterdir()):
        if not _is_vault_dir(vault_dir):
            continue
        vname = vault_dir.name
        claude_dir = vault_dir / 'Claude'
        chi_dir = vault_dir / 'Chi'

        if claude_dir.is_dir():
            for md in sorted(claude_dir.glob('*.md')):
                stem = md.stem
                if 'zh-CN' in stem:
                    continue
                if stem.endswith('_figures'):
                    pa_stem = stem[:-8]
                    key = f'{vname}/{pa_stem}'
                    fe_info[key] = (md, vname, pa_stem)
                else:
                    target = _resolve_pa_target(md)
                    action = resolve_action(target, vname, stem, clip_to_vault, pa_referenced)
                    key = f'{vname}/{stem}'
                    pa_info[key] = (md, vname, action)
                    print(f'[PA] {action:20s} {_rel(vault_root, md)}')
                    if target:
                        print(f'     target={target}')

        if chi_dir.is_dir():
            for md in sorted(chi_dir.glob('*.md')):
                stem = md.stem
                target = _resolve_pt_target(md)
                action = resolve_action(target, vname, stem, clip_to_vault, pt_referenced)
                pt_info[str(md)] = (md, vname, action)
                print(f'[PT] {action:20s} {_rel(vault_root, md)}')
                if target:
                    print(f'     target={target}')

    fe_action: Dict[str, Tuple[Path, str, str]] = {}
    for fe_key, (fe_path, fvname, pa_stem) in fe_info.items():
        pa_entry = None
        for variant in _pa_stem_variants(pa_stem):
            pa_entry = pa_info.get(f'{fvname}/{variant}')
            if pa_entry is not None:
                break
            for pk in pa_info:
                if pk.endswith(f'/{variant}'):
                    pa_entry = pa_info[pk]
                    break
            if pa_entry is not None:
                break
        if pa_entry:
            action = pa_entry[2]
            if action.startswith('move:'):
                fe_action[fe_key] = (fe_path, fvname, pa_entry[2])
            elif action == 'trash':
                fe_action[fe_key] = (fe_path, fvname, 'trash')
            else:
                fe_action[fe_key] = (fe_path, fvname, 'keep')
        else:
            fe_action[fe_key] = (fe_path, fvname, 'trash')

    keep_vault: Dict[str, Dict[str, int]] = {}
    total: Dict[str, Dict[str, int]] = {
        'PA': {'keep': 0, 'move': 0, 'trash': 0},
        'FE': {'keep': 0, 'move': 0, 'trash': 0},
        'PT': {'keep': 0, 'move': 0, 'trash': 0},
    }
    moves: List[Tuple[Path, Path, str]] = []

    for info_map, ftype, subdir in [(pa_info, 'PA', 'Claude'), (pt_info, 'PT', 'Chi')]:
        for key, (path, vname, action) in info_map.items():
            cat = action.split(':')[0]
            total[ftype][cat] = 1 + total[ftype].get(cat, 0)
            if cat == 'keep':
                keep_vault.setdefault(vname, {'PA': 0, 'FE': 0, 'PT': 0})[ftype] += 1
            elif action.startswith('move:'):
                tv = action.split(':', 1)[1]
                moves.append((path, vault_root / tv / subdir, f'{ftype} {vname}→{tv}'))
            elif cat == 'trash':
                moves.append((path, trash_base / vname, f'{ftype}:orphan'))

    for key, (path, vname, action) in fe_action.items():
        cat = action.split(':')[0]
        total['FE'][cat] = 1 + total['FE'].get(cat, 0)
        if cat == 'keep':
            keep_vault.setdefault(vname, {'PA': 0, 'FE': 0, 'PT': 0})['FE'] += 1
        elif action.startswith('move:'):
            tv = action.split(':', 1)[1]
            moves.append((path, vault_root / tv / 'Claude', f'FE {vname}→{tv}'))
        elif cat == 'trash':
            moves.append((path, trash_base / vname, 'FE:orphan'))

    print()
    for src, dst_dir, label in moves:
        dst = dst_dir / src.name
        if dst.exists():
            print(f'[SKIP] {label}  目标已存在: {_rel(vault_root, dst)}')
            continue
        if dry_run:
            print(f'[DRY] {label}: {_rel(vault_root, src)}')
        else:
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            print(f'[MOVE] {label}: {_rel(vault_root, src)}')

    if dry_run and moves:
        print(f'\n[DRY RUN] {len(moves)} 个操作（--force 执行）')
    elif not moves:
        print('无需操作')

    print(f'\n=== 统计 ===')
    for ftype in ('PA', 'FE', 'PT'):
        t = total[ftype]
        print(f'[{ftype}] keep={t["keep"]}  move={t["move"]}  trash={t["trash"]}')
    if keep_vault:
        print('\n各vault保留:')
        for v in sorted(keep_vault):
            kv = keep_vault[v]
            parts = [f'{t}={kv[t]}' for t in ('PA', 'FE', 'PT') if kv.get(t)]
            if parts:
                print(f'  {v}:  {", ".join(parts)}')

    return len(moves) > 0
