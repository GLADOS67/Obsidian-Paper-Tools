import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

sys.stdout.reconfigure(encoding='utf-8')
from config import OBSIDIAN_ROOT
from core import iter_vault_dirs
from core.cache import map_parallel, read_text_safe
from core.doi import extract_doi_from_frontmatter
from core.frontmatter import parse_frontmatter_batch
from core.refs import (
    classify_claude_stem,
    parse_h1_wikilink, extract_wikilink_name,
    first_ref_target, norm_stems, pa_stem_variants,
    extract_doi_set, wikilink_doi,
)

_TRASH_CLAUDE = OBSIDIAN_ROOT / 'TRASH' / 'Claude'
_CITATION_RE = re.compile(r'_(?:fwd_)?citations$')
_DUPE_SUFFIX_RE = re.compile(r' \d+$')
DOI_JACCARD_THRESHOLD = 0.5


def build_clippings_index(vault_root: Path) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str],
                                                      Dict[str, str], Dict[str, set], Dict[str, List[str]],
                                                      Dict[str, str]]:
    """全库 Clippings 索引:stem→vault(变体展开)、PA/PT反向引用名→vault、source→vault、DOI倒排、主DOI→vault。

    返回 (clip_to_vault, pa_ref, pt_ref, clip_by_source, clip_doi_sets, clip_by_doi, clip_first_doi)；
    反向引用/DOI/source/主DOI 均沿用 match 的 reverse/source/first_ref 定位方法，跨 vault 版本。
    """
    clip_to_vault: Dict[str, str] = {}
    pa_ref: Dict[str, str] = {}
    pt_ref: Dict[str, str] = {}
    clip_by_source: Dict[str, str] = {}
    clip_doi_sets: Dict[str, set] = {}
    clip_by_doi: Dict[str, List[str]] = {}
    clip_first_doi: Dict[str, str] = {}

    for vault_dir in iter_vault_dirs(vault_root):
        clip_dir = vault_dir / 'Clippings'
        if not clip_dir.is_dir():
            continue
        mds = sorted(clip_dir.rglob('*.md'))
        parsed = parse_frontmatter_batch(mds, fm_only=True)  # 仅需fm，免全量body驻留内存
        for md, fm in zip(mds, parsed):
            stem = md.stem
            for variant in norm_stems(stem):
                clip_to_vault.setdefault(variant, vault_dir.name)
            if not fm:
                continue
            if pa := extract_wikilink_name(fm.get('paper-analyze')):
                pa_ref.setdefault(pa, vault_dir.name)
            if pt := extract_wikilink_name(fm.get('paper-translate')):
                pt_ref.setdefault(pt, vault_dir.name)
            src = (fm.get('source') or '').strip().lower().rstrip('/')
            if src:
                clip_by_source.setdefault(src, vault_dir.name)
            refs = fm.get('reference', [])
            dois = extract_doi_set(refs)
            if main_doi := extract_doi_from_frontmatter(fm):
                dois.add(main_doi.lower())
            if dois:
                clip_doi_sets[stem] = dois
                for d in dois:
                    clip_by_doi.setdefault(d, []).append(stem)
            if refs and (d0 := wikilink_doi(refs[0])):
                clip_first_doi.setdefault(d0.lower(), vault_dir.name)
    return clip_to_vault, pa_ref, pt_ref, clip_by_source, clip_doi_sets, clip_by_doi, clip_first_doi


def _ref_vault(file_stem: str, referenced: Dict[str, str]) -> Optional[str]:
    """反向引用(变体交叉)命中的 clip vault；精确优先，变体多 vault 冲突返回 None。"""
    if file_stem in referenced:
        return referenced[file_stem]
    hits = {referenced[v] for v in norm_stems(file_stem) if v in referenced}
    return next(iter(hits)) if len(hits) == 1 else None


def _match_by_doi(dois: set, clip_to_vault: Dict[str, str],
                  clip_by_doi: Dict[str, List[str]],
                  clip_doi_sets: Dict[str, set]) -> Optional[str]:
    """DOI jaccard 定位 clip vault(沿 match._find_chi 倒排预筛语义)。"""
    if not dois:
        return None
    cands = {s for d in dois for s in clip_by_doi.get(d, ())}
    best, best_score = None, 0.0
    for c in cands:
        cset = clip_doi_sets[c]
        inter = len(dois & cset)
        union = len(dois) + len(cset) - inter
        if not union:
            continue
        score = inter / union
        if score > best_score:
            best, best_score = c, score
    if best is None or best_score < DOI_JACCARD_THRESHOLD:
        return None
    return _vault_of_stem(best, clip_to_vault)


def _vault_of_stem(stem: str, clip_to_vault: Dict[str, str]) -> Optional[str]:
    for variant in norm_stems(stem):
        if variant in clip_to_vault:
            return clip_to_vault[variant]
    return None


def resolve_action(target_stem: Optional[str], orig_vault: str, file_stem: str,
                   clip_to_vault: Dict[str, str], referenced: Dict[str, str],
                   force_keep: bool = False) -> str:
    if force_keep:
        return 'keep'
    tv = _vault_of_stem(target_stem, clip_to_vault) if target_stem else None
    if tv is None:
        rv = _ref_vault(file_stem, referenced)
        if rv is not None:
            return 'keep' if rv == orig_vault else f'move:{rv}'
        tv = _vault_of_stem(file_stem, clip_to_vault)
    if tv is None:
        return 'trash'
    return 'keep' if tv == orig_vault else f'move:{tv}'


def _rel(vault_root: Path, p: Path) -> str:
    try:
        return str(p.relative_to(vault_root))
    except ValueError:
        return str(p)


def _unique_dest(dst_dir: Path, name: str) -> Path:
    """TRASH 落点唯一名:目标同名时追加 ' (n)' 递增，避免 shutil.move 覆盖。"""
    cand = dst_dir / name
    i = 1
    while cand.exists():
        cand = dst_dir / f'{Path(name).stem} ({i}){Path(name).suffix}'
        i += 1
    return cand


def _resolve_pa(md: Path) -> Optional[str]:
    parsed = parse_h1_wikilink(read_text_safe(md))
    return parsed[0] if parsed else None


def run_reconcile(vault_root=OBSIDIAN_ROOT,
                  trash_base=_TRASH_CLAUDE,
                  dry_run: bool = True) -> bool:
    vault_root = Path(vault_root)
    trash_base = Path(trash_base)

    print(f'Vault: {vault_root}')
    if dry_run:
        print('[DRY RUN]\n')

    (clip_to_vault, pa_referenced, pt_referenced,
     clip_by_source, clip_doi_sets, clip_by_doi, clip_first_doi) = build_clippings_index(vault_root)
    vault_count = len(set(clip_to_vault.values()))
    print(f'索引: {len(clip_to_vault)} stems ({vault_count} vaults)  '
          f'PA反 {len(pa_referenced)}  PT反 {len(pt_referenced)}'
          f'  source {len(clip_by_source)}  DOI {len(clip_by_doi)}\n')

    pa_info: Dict[str, Tuple[Path, str, str]] = {}
    fe_info: Dict[str, Tuple[Path, str, str]] = {}
    pt_info: Dict[str, Tuple[Path, str, str]] = {}

    for vault_dir in iter_vault_dirs(vault_root):
        vname = vault_dir.name
        claude_dir = vault_dir / 'Claude'
        chi_dir = vault_dir / 'Chi'

        if claude_dir.is_dir():
            claude_mds = sorted(claude_dir.glob('*.md'))
            kinds = {md.stem: classify_claude_stem(md.stem) for md in claude_mds}  # 全循环分类一次，主循环免重复判定
            pa_mds = [md for md in claude_mds if kinds[md.stem] == 'pa']

            pa_targets = dict(zip(pa_mds, map_parallel(_resolve_pa, pa_mds)))  # IO并行解析H1，判定保持原顺序
            for md in claude_mds:
                stem = md.stem
                kind = kinds[stem]
                if kind == 'zh':
                    continue
                if kind == 'fe':
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
            chi_parsed = parse_frontmatter_batch(chi_mds, fm_only=True)  # 仅需fm，免全量body驻留内存
            for md, fm in zip(chi_mds, chi_parsed):
                stem = md.stem
                target = None
                tv = None
                if fm:
                    if pt := extract_wikilink_name(fm.get('paper-translate')):
                        target = pt
                        tv = _vault_of_stem(pt, clip_to_vault)
                    if tv is None:
                        src = (fm.get('source') or '').strip().lower().rstrip('/')
                        if src:
                            tv = clip_by_source.get(src)
                    if tv is None:
                        ref0 = first_ref_target(fm.get('reference', []))
                        if ref0:
                            target = ref0
                            tv = _vault_of_stem(ref0, clip_to_vault)
                    if tv is None:
                        refs0 = fm.get('reference', [])
                        if refs0 and (d0 := wikilink_doi(refs0[0])):
                            tv = clip_first_doi.get(d0.lower())
                    if tv is None:
                        dois = extract_doi_set(fm.get('reference', []))
                        if main_doi := extract_doi_from_frontmatter(fm):
                            dois.add(main_doi.lower())
                        tv = _match_by_doi(dois, clip_to_vault, clip_by_doi, clip_doi_sets)
                if tv is None:
                    action = resolve_action(None, vname, stem, clip_to_vault, pt_referenced)
                else:
                    action = 'keep' if tv == vname else f'move:{tv}'
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

        fe_action[fe_key] = (fe_path, fvname, pa_entry[2] if pa_entry else 'trash')

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
                print(f'[WARN] {ftype} 孤立(无匹配clip),保持原位: {_rel(vault_root, path)}')

    dupes_trashed = 0
    print()
    for src, dst_dir, label in moves:
        dst = dst_dir / src.name
        if dst.exists():
            src_vault = label.split(' ')[1].split('\u2192')[0] if '\u2192' in label else ''
            trash_dst_dir = trash_base / src_vault if src_vault else trash_base / '_dupes'
            dst = _unique_dest(trash_dst_dir, src.name)
            if dry_run:
                print(f'[DUPE] {label}  目标已存在-> TRASH: {_rel(vault_root, src)}')
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
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
    print('trash 计数 = 孤立文件(无匹配clip,保持原位,待人工确认)')
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
