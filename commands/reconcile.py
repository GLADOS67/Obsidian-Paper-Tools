import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

sys.stdout.reconfigure(encoding='utf-8')
from core import iter_vault_dirs
from core.frontmatter import parse_frontmatter_file
from core.refs import (
    parse_h1_wikilink, extract_wikilink_name,
    first_ref_target, norm_stems, pa_stem_variants,
)

_CITATION_RE = re.compile(r'_(?:fwd_)?citations$')
_DUPE_SUFFIX_RE = re.compile(r' \d+$')


def _resolve_pa_target(pa_path: Path) -> Optional[str]:
    try:
        parsed = parse_h1_wikilink(pa_path.read_text(encoding='utf-8'))
    except Exception:
        return None
    return parsed[0] if parsed else None


def _resolve_pt_target(chi_path: Path) -> Optional[str]:
    fm, _ = parse_frontmatter_file(chi_path)
    if not fm:
        return None
    pt = extract_wikilink_name(fm.get('paper-translate'))
    return pt or first_ref_target(fm.get('reference', []))


def build_clippings_index(vault_root: Path) -> Tuple[Dict[str, str], Set[str], Set[str]]:
    clip_to_vault: Dict[str, str] = {}
    pa_referenced: Set[str] = set()
    pt_referenced: Set[str] = set()

    for vault_dir in iter_vault_dirs(vault_root):
        clip_dir = vault_dir / 'Clippings'
        if not clip_dir.is_dir():
            continue
        mds = sorted(clip_dir.rglob('*.md'))
        with ThreadPoolExecutor() as ex:  # IO并行解析，索引更新保持原顺序串行
            parsed = list(ex.map(parse_frontmatter_file, mds))
        for md, (fm, _) in zip(mds, parsed):
            stem = md.stem
            for variant in norm_stems(stem):
                clip_to_vault.setdefault(variant, vault_dir.name)
            if not fm:
                continue
            if pa := extract_wikilink_name(fm.get('paper-analyze')):
                pa_referenced.add(pa)
            if pt := extract_wikilink_name(fm.get('paper-translate')):
                pt_referenced.add(pt)
    return clip_to_vault, pa_referenced, pt_referenced


def _vault_of_stem(stem: str, clip_to_vault: Dict[str, str]) -> Optional[str]:
    for variant in norm_stems(stem):
        if variant in clip_to_vault:
            return clip_to_vault[variant]
    return None


def resolve_action(target_stem: Optional[str], orig_vault: str, file_stem: str,
                   clip_to_vault: Dict[str, str], referenced: Set[str],
                   force_keep: bool = False) -> str:
    if force_keep:
        return 'keep'
    tv = _vault_of_stem(target_stem, clip_to_vault) if target_stem else None
    if tv is None:
        if file_stem in referenced:
            return 'keep'
        tv = _vault_of_stem(file_stem, clip_to_vault)
    if tv is None:
        return 'trash'
    return 'keep' if tv == orig_vault else f'move:{tv}'


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

    for vault_dir in iter_vault_dirs(vault_root):
        vname = vault_dir.name
        claude_dir = vault_dir / 'Claude'
        chi_dir = vault_dir / 'Chi'

        if claude_dir.is_dir():
            claude_mds = sorted(claude_dir.glob('*.md'))
            pa_mds = [md for md in claude_mds
                      if 'zh-CN' not in md.stem and not md.stem.endswith('_figures')]
            with ThreadPoolExecutor() as ex:  # IO并行解析H1，判定保持原顺序串行
                pa_targets = dict(zip(pa_mds, ex.map(_resolve_pa_target, pa_mds)))
            for md in claude_mds:
                stem = md.stem
                if 'zh-CN' in stem:
                    continue
                if stem.endswith('_figures'):
                    fe_info[f'{vname}/{stem[:-8]}'] = (md, vname, stem[:-8])
                    continue
                force_keep = bool(_CITATION_RE.search(stem))
                dupe_m = _DUPE_SUFFIX_RE.search(stem)
                is_dupe = bool(dupe_m) and (md.parent / f'{stem[:dupe_m.start()]}.md').exists()
                target = pa_targets[md]
                action = resolve_action(target, vname, stem, clip_to_vault, pa_referenced, force_keep)
                pa_info[f'{vname}/{stem}'] = (md, vname, action)
                extra = ' [citation]' if force_keep else (' [duplicate]' if is_dupe else '')
                print(f'[PA] {action:20s} {_rel(vault_root, md)}{extra}')
                if target:
                    print(f'     target={target}')

        if chi_dir.is_dir():
            chi_mds = sorted(chi_dir.glob('*.md'))
            with ThreadPoolExecutor() as ex:  # IO并行解析frontmatter
                pt_targets = list(ex.map(_resolve_pt_target, chi_mds))
            for md, target in zip(chi_mds, pt_targets):
                stem = md.stem
                action = resolve_action(target, vname, stem, clip_to_vault, pt_referenced)
                pt_info[str(md)] = (md, vname, action)
                print(f'[PT] {action:20s} {_rel(vault_root, md)}')
                if target:
                    print(f'     target={target}')

    # 预计算 stem→条目 索引（保持 pa_info 插入顺序，首个命中），避免 O(F×V×N) 嵌套扫描
    pa_by_stem: Dict[str, Tuple[Path, str, str]] = {}
    for pk, entry in pa_info.items():
        pa_by_stem.setdefault(pk.split('/', 1)[1], entry)

    fe_action: Dict[str, Tuple[Path, str, str]] = {}
    for fe_key, (fe_path, fvname, pa_stem) in fe_info.items():
        pa_entry = None
        for variant in pa_stem_variants(pa_stem):
            pa_entry = pa_info.get(f'{fvname}/{variant}') or pa_by_stem.get(variant)
            if pa_entry is not None:
                break

        if pa_entry:
            action = pa_entry[2]
            fe_action[fe_key] = (fe_path, fvname, action if ':' in action else action)
        else:
            fe_action[fe_key] = (fe_path, fvname, 'trash')

    total = {'PA': {'keep': 0, 'move': 0, 'trash': 0},
             'FE': {'keep': 0, 'move': 0, 'trash': 0},
             'PT': {'keep': 0, 'move': 0, 'trash': 0}}
    keep_vault: Dict[str, Dict[str, int]] = {}
    moves: List[Tuple[Path, Path, str]] = []

    for info_map, ftype, subdir in [(pa_info, 'PA', 'Claude'), (pt_info, 'PT', 'Chi'),
                                    (fe_action, 'FE', 'Claude')]:
        for key, (path, vname, action) in info_map.items():
            cat = action.split(':')[0]
            total[ftype][cat] += 1
            if cat == 'keep':
                keep_vault.setdefault(vname, {'PA': 0, 'FE': 0, 'PT': 0})[ftype] += 1
            elif action.startswith('move:'):
                tv = action.split(':', 1)[1]
                moves.append((path, vault_root / tv / subdir, f'{ftype} {vname}→{tv}'))
            else:
                moves.append((path, trash_base / vname, f'{ftype}:orphan'))

    dupes_trashed = 0
    print()
    for src, dst_dir, label in moves:
        dst = dst_dir / src.name
        if dst.exists():
            src_vault = label.split(' ')[1].split('\u2192')[0] if '\u2192' in label else ''
            trash_dst_dir = trash_base / src_vault if src_vault else trash_base / '_dupes'
            if dry_run:
                print(f'[DUPE] {label}  目标已存在-> TRASH: {_rel(vault_root, src)}')
            else:
                trash_dst_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(trash_dst_dir / src.name))
                print(f'[DUPE] {label}: {_rel(vault_root, src)}')
            dupes_trashed += 1
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
    if dupes_trashed:
        print(f'[DUPE] -> TRASH: {dupes_trashed}')
    if keep_vault:
        print('\n各vault保留:')
        for v in sorted(keep_vault):
            kv = keep_vault[v]
            parts = [f'{t}={kv[t]}' for t in ('PA', 'FE', 'PT') if kv.get(t)]
            if parts:
                print(f'  {v}:  {", ".join(parts)}')

    return len(moves) > 0
