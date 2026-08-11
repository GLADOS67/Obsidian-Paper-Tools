"""/s: Match Clippings to PT/PA/FE notes inside an Obsidian Vault."""

from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Optional, Tuple

from core.doi import PATTERN_DOI as DOI_RE
from core.frontmatter import parse_frontmatter_file, dump_frontmatter
from core.refs import (
    WIKILINK_RE, LINK_TARGET_RE,
    parse_h1_wikilink, extract_wikilink_name, first_ref_target,
    extract_doi_set,
)

JACCARD_THRESHOLD = 0.85
FUZZY_THRESHOLD = 0.7


def _extract_clippings_doi(fm: dict) -> Optional[str]:
    refs = fm.get('reference', [])
    if refs and isinstance(refs[0], str):
        m = WIKILINK_RE.search(refs[0].replace('\n', ' '))
        if m:
            doi_match = DOI_RE.search(m.group(2) or m.group(1))
            if doi_match:
                return doi_match.group(0).lower()
    doi_val = fm.get('doi')
    if isinstance(doi_val, list) and doi_val:
        doi_val = doi_val[0]
    return (DOI_RE.search(doi_val).group(0).lower()
            if isinstance(doi_val, str) and DOI_RE.search(doi_val) else None)


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a) + len(b) - inter
    return inter / union if union else 0.0


def _chinese_title_from_h1(md_path: Path) -> Optional[str]:
    try:
        text = md_path.read_text(encoding='utf-8')
    except Exception:
        return None
    parsed = parse_h1_wikilink(text)
    if parsed:
        return parsed[1]
    for line in text.split('\n'):
        stripped = line.lstrip('#').strip()
        if stripped and any('\u4e00' <= c <= '\u9fff' for c in stripped):
            return stripped
    return None


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


def _match_pa(clip_md: Path, fm: dict, pa_index: Dict[str, Path],
              pa_reverse: Dict[str, Tuple[Path, str]], force: bool,
              clippings_doi_cache: Optional[str] = None):
    existing = fm.get('paper-analyze')
    if existing and not force:
        return 'skipped', None

    clip_stem = clip_md.stem
    underscore_stem = clip_stem.replace(' ', '_')

    rev = pa_reverse.get(clip_stem) or pa_reverse.get(underscore_stem)
    if rev:
        pa_path, alias, method = rev[0], rev[1], 'reverse'
    else:
        pa_path = pa_index.get(underscore_stem)
        if pa_path:
            alias = _chinese_title_from_h1(pa_path)
            method = 'filename'
        else:
            doi = _extract_clippings_doi(fm) if clippings_doi_cache is None else clippings_doi_cache
            if doi:
                pa_path, alias, method = _pa_by_doi(pa_index, doi)
            else:
                pa_path, alias, method = None, None, ''
        if not pa_path:
            result = _fuzzy_best(underscore_stem, pa_index)
            if result:
                pa_path, method = result[0], 'fuzzy'
                alias = _chinese_title_from_h1(pa_path)

    if not pa_path:
        return ('failed', None) if not existing else ('skipped', None), None
    if existing and (LINK_TARGET_RE.search(str(existing)).group(1).strip()
                     if LINK_TARGET_RE.search(str(existing)) else None) == pa_path.stem:
        return 'skipped', None
    link = f'[[{pa_path.stem}|{alias}]]' if alias else f'[[{pa_path.stem}]]'
    fm['paper-analyze'] = link
    print(f'[PA] {method:10s}  {clip_md.name} -> {pa_path.name}')
    return 'matched', pa_path


def _pa_by_doi(pa_index: Dict[str, Path], doi: str) -> Tuple[Optional[Path], Optional[str], str]:
    for pa_stem, pa_p in pa_index.items():
        try:
            if doi in pa_p.read_text(encoding='utf-8').lower():
                return pa_p, _chinese_title_from_h1(pa_p), 'doi'
        except Exception:
            continue
    return None, None, ''


def _match_fe(clip_md: Path, fm: dict, fe_index: Dict[str, Path],
              fe_reverse: Dict[str, Tuple[Path, str]], force: bool):
    existing = fm.get('figure-extractor')
    if existing and not force:
        return 'skipped', None

    underscore_stem = clip_md.stem.replace(' ', '_')

    rev = fe_reverse.get(underscore_stem)
    if rev:
        fe_path, alias, method = rev[0], rev[1], 'reverse'
    else:
        fe_path = fe_index.get(underscore_stem)
        if fe_path:
            alias, method = None, 'filename'
        else:
            result = _fuzzy_best(underscore_stem + '_figures', {k: v for k, v in fe_index.items()})
            if result:
                fe_path, method = result[0], 'fuzzy'
                alias = None
            else:
                fe_path, alias, method = None, None, ''

    if not fe_path:
        return ('failed', None) if not existing else ('skipped', None), None
    if existing and (LINK_TARGET_RE.search(str(existing)).group(1).strip()
                     if LINK_TARGET_RE.search(str(existing)) else None) == fe_path.stem:
        return 'skipped', None
    link = f'[[{fe_path.stem}|{alias}]]' if alias else f'[[{fe_path.stem}]]'
    fm['figure-extractor'] = link
    print(f'[FE] {method:10s}  {clip_md.name} -> {fe_path.name}')
    return 'matched', fe_path


def run_match(base_dir: str, dry_run: bool = False, threshold: float = JACCARD_THRESHOLD,
              force: bool = False, verbose: bool = False) -> bool:
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
    if dry_run:
        print('[DRY RUN]\n')

    by_source: Dict[str, Path] = {}
    by_first_ref: Dict[str, Path] = {}
    chi_doi_sets: Dict[Path, set] = {}
    chi_display: Dict[Path, str] = {}
    chi_reverse: Dict[str, Tuple[Path, str]] = {}

    for md in sorted(chi_dir.rglob('*.md')):
        fm, _ = parse_frontmatter_file(md)
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

    claude_dir = base / 'Claude'
    if claude_dir.is_dir():
        for md in sorted(claude_dir.rglob('*.md')):
            stem = md.stem
            if 'zh-CN' in stem:
                continue
            if stem.endswith('_figures'):
                fe_index[stem[:-8]] = md
            else:
                pa_index[stem] = md
                try:
                    h1_info = parse_h1_wikilink(md.read_text(encoding='utf-8'))
                except Exception:
                    h1_info = None
                if h1_info:
                    clip_stem, ch_title = h1_info
                    pa_reverse[clip_stem] = (md, ch_title)
                    pa_reverse[clip_stem.replace('_', ' ')] = (md, ch_title)
                ch = _chinese_title_from_h1(md)
                if ch:
                    pa_alias[md.stem] = ch

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

    stats = {
        'pt': {'matched': 0, 'skipped': 0, 'failed': 0,
               'methods': {'reverse': 0, 'source': 0, 'first_ref': 0, 'jaccard': 0}},
        'pa': {'matched': 0, 'skipped': 0, 'failed': 0},
        'fe': {'matched': 0, 'skipped': 0, 'failed': 0},
    }

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
            clip_src = (fm.get('source') or '').strip().lower().rstrip('/')
            clip_fr = first_ref_target(fm.get('reference', []))
            chi_path, method, score, chi_alias = None, '', 0.0, None

            rev = chi_reverse.get(clip_md.stem)
            if rev:
                chi_path, chi_alias, method, score = rev[0], rev[1], 'reverse', 1.0
            elif clip_src in by_source:
                chi_path, chi_alias, method, score = by_source[clip_src], None, 'source', 1.0
            elif clip_fr in by_first_ref:
                chi_path, chi_alias, method, score = by_first_ref[clip_fr], None, 'first_ref', 1.0
            else:
                clip_dois = extract_doi_set(fm.get('reference', []))
                for chi_p, chi_dois in chi_doi_sets.items():
                    s = _jaccard(clip_dois, chi_dois)
                    if s > score:
                        score, chi_path = s, chi_p
                if score >= threshold:
                    method = 'jaccard'
                else:
                    chi_path = None

            if chi_path and existing_pt and (LINK_TARGET_RE.search(str(existing_pt)).group(1).strip()
                                             if LINK_TARGET_RE.search(str(existing_pt)) else '') == chi_path.stem:
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
                    print(f'[PT] FAIL: {clip_md.name}')
                    for cand_p, cand_s in sorted(
                        ((p, _jaccard(clip_dois, d)) for p, d in chi_doi_sets.items()),
                        key=lambda x: x[1], reverse=True
                    )[:3]:
                        print(f'  jaccard={cand_s:.3f}  {cand_p.name}')
            else:
                stats['pt']['skipped'] += 1

        clip_doi_value = _extract_clippings_doi(fm)
        pa_result, pa_path = _match_pa(clip_md, fm, pa_index, pa_reverse, force, clip_doi_value)
        stats['pa']['matched'] += pa_result == 'matched'
        stats['pa']['skipped'] += pa_result == 'skipped'
        stats['pa']['failed'] += pa_result == 'failed'
        any_changed |= pa_result == 'matched'

        fe_result, _ = _match_fe(clip_md, fm, fe_index, fe_reverse, force)
        stats['fe']['matched'] += fe_result == 'matched'
        stats['fe']['skipped'] += fe_result == 'skipped'
        stats['fe']['failed'] += fe_result == 'failed'
        any_changed |= fe_result == 'matched'

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
    return stats['pt']['matched'] + stats['pa']['matched'] + stats['fe']['matched'] > 0
