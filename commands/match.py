import shutil
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Optional, Tuple

from core.doi import PATTERN_DOI as DOI_RE
from core.frontmatter import parse_frontmatter_file, dump_frontmatter
from core.obsidian_path import SM_QUICK
from core.refs import (
    WIKILINK_RE, LINK_TARGET_RE,
    parse_h1_wikilink, extract_wikilink_name, first_ref_target,
    extract_doi_set,
)
from config import OBSIDIAN_ROOT

JACCARD_THRESHOLD = 0.85
FUZZY_THRESHOLD = SM_QUICK
TRASH_CLAUDE = OBSIDIAN_ROOT / 'TRASH' / 'Claude'


def _extract_clippings_doi(fm: dict) -> Optional[str]:
    refs = fm.get('reference', [])
    if refs and isinstance(refs[0], str):
        m = WIKILINK_RE.search(refs[0].replace('\n', ' '))
        if m and (doi_match := DOI_RE.search(m.group(2) or m.group(1))):
            return doi_match.group(0).lower()
    doi_val = fm.get('doi')
    if isinstance(doi_val, list) and doi_val:
        doi_val = doi_val[0]
    return (dm.group(0).lower()
            if isinstance(doi_val, str) and (dm := DOI_RE.search(doi_val)) else None)


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a) + len(b) - inter
    return inter / union if union else 0.0


def _read_text_safe(md: Path) -> str:
    try:
        return md.read_text(encoding='utf-8')
    except Exception:
        return ''


def _chinese_title_from_text(text: str) -> Optional[str]:
    if parsed := parse_h1_wikilink(text):
        return parsed[1]
    for line in text.split('\n'):
        stripped = line.lstrip('#').strip()
        if stripped and any('一' <= c <= '鿿' for c in stripped):
            return stripped
    return None


def _register_pa(md: Path, text: str, pa_index: Dict[str, Path],
                 pa_text: Dict[str, str], pa_reverse: Dict[str, Tuple[Path, str]]) -> None:
    """登记 PA 笔记：正向索引 + 小写正文缓存 + H1 wikilink 反向索引（下划线/空格双写）。"""
    stem = md.stem
    pa_index[stem] = md
    pa_text[stem] = text.lower()
    if h1_info := parse_h1_wikilink(text):
        clip_stem, ch_title = h1_info
        pa_reverse[clip_stem] = (md, ch_title)
        pa_reverse[clip_stem.replace('_', ' ')] = (md, ch_title)


def _fuzzy_best(stem: str, candidates: Dict[str, Path],
                threshold: float = FUZZY_THRESHOLD) -> Optional[Tuple[Path, float]]:
    stem_lower = stem.lower()
    best, best_score = None, 0.0
    for cand_stem, cand_path in candidates.items():
        sm = SequenceMatcher(None, stem_lower, cand_stem.lower())
        if sm.quick_ratio() < threshold * 0.9:
            continue
        score = sm.ratio()
        if score > best_score:
            best_score, best = score, cand_path
    return (best, best_score) if best and best_score >= threshold else None


def _pa_by_doi(pa_index: Dict[str, Path], pa_text: Dict[str, str],
               pa_alias: Dict[str, str], doi: str,
               memo: Dict[str, Optional[Tuple[Path, Optional[str], str]]]
               ) -> Tuple[Optional[Path], Optional[str], str]:
    """在索引时缓存的 PA 正文(小写)中查找包含该 DOI 的文件，避免重复 IO；memo 避免重复全文扫描。"""
    if doi not in memo:
        memo[doi] = next(
            ((pa_index[s], pa_alias.get(s), 'doi') for s, t in pa_text.items() if doi in t),
            None)
    return memo[doi] or (None, None, '')


def _find_pa(clip_stem: str, pa_index: Dict[str, Path],
             pa_reverse: Dict[str, Tuple[Path, str]], pa_text: Dict[str, str],
             pa_alias: Dict[str, str], doi: Optional[str],
             doi_memo: Dict[str, Optional[Tuple[Path, Optional[str], str]]]
             ) -> Tuple[Optional[Path], Optional[str], str]:
    """按 reverse → filename → doi → fuzzy 顺序定位 PA 笔记。"""
    underscore_stem = clip_stem.replace(' ', '_')
    rev = pa_reverse.get(clip_stem) or pa_reverse.get(underscore_stem)
    if rev:
        return rev[0], rev[1], 'reverse'
    if pa_path := pa_index.get(underscore_stem):
        return pa_path, pa_alias.get(pa_path.stem), 'filename'
    if doi:
        found = _pa_by_doi(pa_index, pa_text, pa_alias, doi, doi_memo)
        if found[0]:
            return found
    if result := _fuzzy_best(underscore_stem, pa_index):
        return result[0], pa_alias.get(result[0].stem), 'fuzzy'
    return None, None, ''


def _find_fe(underscore_stem: str, fe_index: Dict[str, Path],
             fe_reverse: Dict[str, Tuple[Path, str]]
             ) -> Tuple[Optional[Path], Optional[str], str]:
    """按 reverse → filename → fuzzy 顺序定位 FE 笔记。"""
    if rev := fe_reverse.get(underscore_stem):
        return rev[0], rev[1], 'reverse'
    if fe_path := fe_index.get(underscore_stem):
        return fe_path, None, 'filename'
    if result := _fuzzy_best(underscore_stem + '_figures', fe_index):
        return result[0], None, 'fuzzy'
    return None, None, ''


def _apply_found(clip_md: Path, fm: dict, key: str, existing, found, label: str):
    """PA/FE 共用的匹配结果落地逻辑：目标未变则跳过，否则写入 wikilink。"""
    path, alias, method = found
    if not path:
        return ('failed' if not existing else 'skipped'), None
    if existing and (m := LINK_TARGET_RE.search(str(existing))) and m.group(1).strip() == path.stem:
        return 'skipped', None
    fm[key] = f'[[{path.stem}|{alias}]]' if alias else f'[[{path.stem}]]'
    print(f'[{label}] {method:10s}  {clip_md.name} -> {path.name}')
    return 'matched', path


def _match_pa(clip_md: Path, fm: dict, pa_index: Dict[str, Path],
              pa_reverse: Dict[str, Tuple[Path, str]], pa_text: Dict[str, str],
              pa_alias: Dict[str, str], force: bool,
              clippings_doi_cache: Optional[str] = None,
              doi_memo: Optional[dict] = None):
    existing = fm.get('paper-analyze')
    if existing and not force:
        return 'skipped', None
    doi = _extract_clippings_doi(fm) if clippings_doi_cache is None else clippings_doi_cache
    found = _find_pa(clip_md.stem, pa_index, pa_reverse, pa_text, pa_alias,
                     doi, doi_memo if doi_memo is not None else {})
    return _apply_found(clip_md, fm, 'paper-analyze', existing, found, 'PA')


def _match_fe(clip_md: Path, fm: dict, fe_index: Dict[str, Path],
              fe_reverse: Dict[str, Tuple[Path, str]], force: bool):
    existing = fm.get('figure-extractor')
    if existing and not force:
        return 'skipped', None
    found = _find_fe(clip_md.stem.replace(' ', '_'), fe_index, fe_reverse)
    return _apply_found(clip_md, fm, 'figure-extractor', existing, found, 'FE')


def _find_chi(clip_md: Path, fm: dict, chi_reverse: Dict[str, Tuple[Path, str]],
              by_source: Dict[str, Path], by_first_ref: Dict[str, Path],
              chi_doi_sets: Dict[Path, set], threshold: float):
    """按 reverse → source → first_ref → jaccard 顺序定位 Chi 笔记。"""
    rev = chi_reverse.get(clip_md.stem)
    if rev:
        return rev[0], rev[1], 'reverse', 1.0
    clip_src = (fm.get('source') or '').strip().lower().rstrip('/')
    if clip_src in by_source:
        return by_source[clip_src], None, 'source', 1.0
    clip_fr = first_ref_target(fm.get('reference', []))
    if clip_fr in by_first_ref:
        return by_first_ref[clip_fr], None, 'first_ref', 1.0
    clip_dois = extract_doi_set(fm.get('reference', []))
    score, chi_path = 0.0, None
    for chi_p, chi_dois in chi_doi_sets.items():
        s = _jaccard(clip_dois, chi_dois)
        if s > score:
            score, chi_path = s, chi_p
            if s >= 1.0:  # 已达上界，无需继续扫描
                break
    return (chi_path, None, 'jaccard', score) if score >= threshold else (None, None, '', score)


def run_match(base_dir: str, dry_run: bool = False, threshold: float = JACCARD_THRESHOLD,
              force: bool = False, verbose: bool = False,
              reconcile_claude: bool = False) -> bool:
    base = Path(base_dir)
    clip_dir = base / 'Clippings'
    chi_dir = base / 'Chi'
    if not clip_dir.is_dir():
        print(f'ERROR: Clippings 目录不存在: {clip_dir}')
        return False
    if not chi_dir.is_dir():
        print(f'ERROR: Chi 目录不存在: {chi_dir}')
        return False
    print(f'Clippings: {clip_dir}\nChi: {chi_dir}')
    if reconcile_claude:
        print(f'TRASH Claude: {TRASH_CLAUDE}')
    if dry_run:
        print('[DRY RUN]\n')

    by_source: Dict[str, Path] = {}
    by_first_ref: Dict[str, Path] = {}
    chi_doi_sets: Dict[Path, set] = {}
    chi_display: Dict[Path, str] = {}
    chi_reverse: Dict[str, Tuple[Path, str]] = {}

    chi_mds = sorted(chi_dir.rglob('*.md'))
    with ThreadPoolExecutor() as ex:  # IO并行，字典更新保持原顺序串行
        chi_parsed = list(ex.map(parse_frontmatter_file, chi_mds))
    for md, (fm, _) in zip(chi_mds, chi_parsed):
        if not fm:
            continue
        src = (fm.get('source') or '').strip().lower().rstrip('/')
        if src:
            by_source[src] = md
        fr = first_ref_target(fm.get('reference', []))
        if fr:
            by_first_ref[fr] = md
        chi_doi_sets[md] = extract_doi_set(fm.get('reference', []))
        title = fm.get('title', '')
        if isinstance(title, list):
            title = ' '.join(str(t) for t in title)
        chi_display[md] = str(title).strip() or md.stem
        pt_target = extract_wikilink_name(fm.get('paper-translate'))
        if pt_target:
            chi_reverse[pt_target] = (md, chi_display[md])
    print(f'Chi: {len(by_source)} src, {len(by_first_ref)} first-ref, {len(chi_doi_sets)} total\n')

    pa_index: Dict[str, Path] = {}
    fe_index: Dict[str, Path] = {}
    pa_reverse: Dict[str, Tuple[Path, str]] = {}
    fe_reverse: Dict[str, Tuple[Path, str]] = {}
    pa_alias: Dict[str, str] = {}
    pa_text: Dict[str, str] = {}

    claude_dir = base / 'Claude'
    if claude_dir.is_dir():
        claude_mds = sorted(claude_dir.rglob('*.md'))
        with ThreadPoolExecutor() as ex:  # IO并行读取正文
            claude_texts = list(ex.map(_read_text_safe, claude_mds))
        for md, text in zip(claude_mds, claude_texts):
            stem = md.stem
            if 'zh-CN' in stem:
                continue
            if stem.endswith('_figures'):
                fe_index[stem[:-8]] = md
                continue
            _register_pa(md, text, pa_index, pa_text, pa_reverse)
            if ch := _chinese_title_from_text(text):
                pa_alias[stem] = ch

    for fe_stem, fe_path in fe_index.items():
        space_stem = fe_stem.replace('_', ' ')
        if fe_stem in pa_index:
            ch = pa_alias.get(fe_stem)
            if ch:
                fe_reverse[fe_stem] = (fe_path, ch)
        elif space_stem in pa_reverse:
            fe_reverse[space_stem] = (fe_path, pa_reverse[space_stem][1])
            fe_reverse[fe_stem] = (fe_path, pa_reverse[space_stem][1])

    print(f'Claude: {len(pa_index)} PA, {len(fe_index)} FE, '
          f'{len(pa_reverse)} PA-reverse, {len(fe_reverse)} FE-reverse\n')

    trash_pa_source: Dict[str, Path] = {}
    trash_fe_source: Dict[str, Path] = {}
    if reconcile_claude and TRASH_CLAUDE.is_dir():
        trash_files = sorted(TRASH_CLAUDE.rglob('*.md'))
        with ThreadPoolExecutor() as ex:
            trash_texts = list(ex.map(_read_text_safe, trash_files))
        for md, text in zip(trash_files, trash_texts):
            stem = md.stem
            if 'zh-CN' in stem:
                continue
            if stem.endswith('_figures'):
                if stem[:-8] not in fe_index:
                    fe_index[stem[:-8]] = md
                    trash_fe_source[stem[:-8]] = md
                continue
            if stem not in pa_index:
                _register_pa(md, text, pa_index, pa_text, pa_reverse)
                trash_pa_source[stem] = md
        print(f'TRASH: {len(trash_pa_source)} PA, {len(trash_fe_source)} FE scanned\n')

    stats = {
        'pt': {'matched': 0, 'skipped': 0, 'failed': 0,
               'methods': {'reverse': 0, 'source': 0, 'first_ref': 0, 'jaccard': 0}},
        'pa': {'matched': 0, 'skipped': 0, 'failed': 0},
        'fe': {'matched': 0, 'skipped': 0, 'failed': 0},
    }
    doi_memo: Dict[str, Optional[Tuple[Path, Optional[str], str]]] = {}
    matched_stems: set = set()
    trash_reclaims: Dict[str, str] = {}

    for clip_md in sorted(clip_dir.rglob('*.md')):
        fm, body = parse_frontmatter_file(clip_md)
        if not fm:
            print(f'SKIP (no fm): {clip_md.name}')
            for k in ('pt', 'pa', 'fe'):
                stats[k]['skipped'] += 1
            continue

        any_changed = False

        existing_pt = fm.get('paper-translate')
        if existing_pt and not force:
            stats['pt']['skipped'] += 1
        else:
            chi_path, chi_alias, method, score = _find_chi(
                clip_md, fm, chi_reverse, by_source, by_first_ref, chi_doi_sets, threshold)
            if (chi_path and existing_pt and (m := LINK_TARGET_RE.search(str(existing_pt)))
                    and m.group(1).strip() == chi_path.stem):
                stats['pt']['skipped'] += 1
            elif chi_path:
                display = chi_alias or chi_display.get(chi_path) or chi_path.stem
                fm['paper-translate'] = f'[[{chi_path.stem}|{display}]]'
                stats['pt']['matched'] += 1
                stats['pt']['methods'][method] += 1
                any_changed = True
                print(f'[PT] {method:10s} (conf={score:.2f})  {clip_md.name} -> {chi_path.name}')
            elif not existing_pt:
                stats['pt']['failed'] += 1
                if verbose:
                    clip_dois = extract_doi_set(fm.get('reference', []))
                    print(f'[PT] FAIL: {clip_md.name}')
                    for cand_p, cand_s in sorted(
                        ((p, _jaccard(clip_dois, d)) for p, d in chi_doi_sets.items()),
                        key=lambda x: x[1], reverse=True
                    )[:3]:
                        print(f'  jaccard={cand_s:.3f}  {cand_p.name}')
            else:
                stats['pt']['skipped'] += 1

        clip_doi_value = _extract_clippings_doi(fm)
        pa_result, pa_path = _match_pa(clip_md, fm, pa_index, pa_reverse, pa_text,
                                       pa_alias, force, clip_doi_value, doi_memo)
        stats['pa']['matched'] += pa_result == 'matched'
        stats['pa']['skipped'] += pa_result == 'skipped'
        stats['pa']['failed'] += pa_result == 'failed'
        any_changed |= pa_result == 'matched'
        pa_stem = pa_path.stem if pa_path else extract_wikilink_name(fm.get('paper-analyze'))
        if pa_stem:
            matched_stems.add(pa_stem)
            if pa_stem in trash_pa_source:
                trash_reclaims[pa_stem] = base.name

        fe_result, fe_path = _match_fe(clip_md, fm, fe_index, fe_reverse, force)
        stats['fe']['matched'] += fe_result == 'matched'
        stats['fe']['skipped'] += fe_result == 'skipped'
        stats['fe']['failed'] += fe_result == 'failed'
        any_changed |= fe_result == 'matched'
        fe_stem = fe_path.stem if fe_path else extract_wikilink_name(fm.get('figure-extractor'))
        if fe_stem:
            matched_stems.add(fe_stem)
            if fe_stem in trash_fe_source:
                trash_reclaims[fe_stem] = base.name

        if any_changed and not dry_run:
            clip_md.write_text(dump_frontmatter(fm, body), encoding='utf-8')

    print(f'\n=== Results ===')
    pt_m = stats['pt']['methods']
    print(f'[PT] Matched: {stats["pt"]["matched"]}  Skipped: {stats["pt"]["skipped"]}  '
          f'Failed: {stats["pt"]["failed"]}  Methods: reverse={pt_m["reverse"]} '
          f'source={pt_m["source"]} first_ref={pt_m["first_ref"]} jaccard={pt_m["jaccard"]}')
    print(f'[PA] Matched: {stats["pa"]["matched"]}  Skipped: {stats["pa"]["skipped"]}  '
          f'Failed: {stats["pa"]["failed"]}')
    print(f'[FE] Matched: {stats["fe"]["matched"]}  Skipped: {stats["fe"]["skipped"]}  '
          f'Failed: {stats["fe"]["failed"]}')

    if not reconcile_claude:
        return stats['pt']['matched'] + stats['pa']['matched'] + stats['fe']['matched'] > 0

    print(f'\n--- Claude Trash Reconciliation ---')
    vault_claude_dir = base / 'Claude'
    moved_to_trash = 0
    reclaimed = 0

    if vault_claude_dir.is_dir():
        vault_name = base.name
        trash_target = TRASH_CLAUDE / vault_name
        for md in sorted(vault_claude_dir.rglob('*.md')):
            if md.stem in matched_stems or 'zh-CN' in md.stem:
                continue
            if md.stem.endswith('_figures'):
                continue
            rel = md.relative_to(vault_claude_dir)
            dest = trash_target / rel.parent
            if not dry_run:
                dest.mkdir(parents=True, exist_ok=True)
                shutil.move(str(md), str(dest / md.name))
            moved_to_trash += 1
        for stem, vault in trash_reclaims.items():
            src = trash_pa_source.get(stem) or trash_fe_source.get(stem)
            if not src or not src.exists():
                continue
            dest_vault_claude = OBSIDIAN_ROOT / vault / 'Claude'
            subdir = src.parent.relative_to(TRASH_CLAUDE)
            dest_dir = dest_vault_claude / subdir.relative_to(subdir.parts[0]) if subdir.parts and subdir.parts[0] != '.' else dest_vault_claude
            dest = dest_dir / src.name
            if dest.exists():
                continue
            if not dry_run:
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
            reclaimed += 1
            print(f'[RECLAIM] {src.name} -> {vault}/Claude')

    print(f'  Vault Claude → TRASH: {moved_to_trash} files')
    print(f'  TRASH → Vault Claude: {reclaimed} files')
    return stats['pt']['matched'] + stats['pa']['matched'] + stats['fe']['matched'] > 0
