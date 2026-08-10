"""/s: Fuzzy matcher linking Clippings to PA/PT/FE.
"""
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Optional, Tuple

from core.doi import PATTERN_DOI as DOI_RE
from core.frontmatter import parse_frontmatter_file, dump_frontmatter

WIKILINK_RE = re.compile(r'\[\[([^|]+)\|([^]]+)\]\]')
LINK_TARGET_RE = re.compile(r'\[\[\s*([^|\]]+)')
H1_WIKILINK_RE = re.compile(r'^#\s*\[\[([^|]+)\|([^]]+)\]\]')
JACCARD_THRESHOLD = 0.85
FUZZY_THRESHOLD = 0.7


def _extract_doi_set(ref_list: list) -> set:
    if not ref_list:
        return set()
    result = set()
    for ref in ref_list:
        if not isinstance(ref, str):
            continue
        text = ref.replace('\n', ' ')
        match = WIKILINK_RE.search(text)
        source = match.group(2) if match else text
        result.update(doi for doi in DOI_RE.findall(source))
    return result


def _first_ref_target(ref_list: list) -> Optional[str]:
    if not ref_list:
        return None
    ref0 = (ref_list[0].replace('\n', ' ').strip() if isinstance(ref_list[0], str)
            else str(ref_list[0]).replace('\n', ' ').strip())
    m = WIKILINK_RE.search(ref0)
    return m.group(1).strip() if m else None


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a) + len(b) - inter
    return inter / union if union else 0.0


def _link_target(value) -> Optional[str]:
    if not value:
        return None
    m = LINK_TARGET_RE.search(str(value))
    return m.group(1).strip() if m else None


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


def _chinese_title_from_h1(md_path: Path) -> Optional[str]:
    try:
        text = md_path.read_text(encoding='utf-8')
    except Exception:
        return None
    parsed = _parse_h1_wikilink(text)
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
    if isinstance(doi_val, str) and (m := DOI_RE.search(doi_val)):
        return m.group(0).lower()
    return None


def _match_pa(clip_md: Path, fm: dict, pa_index: Dict[str, Path],
              pa_reverse: Dict[str, Tuple[Path, str]], force: bool):
    existing = fm.get('paper-analyze')
    if existing and not force:
        return 'skipped', None
    clip_stem, underscore_stem = clip_md.stem, clip_md.stem.replace(' ', '_')
    pa_path, alias, method = None, None, ''
    rev = pa_reverse.get(clip_stem) or pa_reverse.get(underscore_stem)
    if rev:
        pa_path, alias, method = rev[0], rev[1], 'reverse'
    if not pa_path:
        pa_path = pa_index.get(underscore_stem)
        if pa_path:
            alias, method = _chinese_title_from_h1(pa_path), 'filename'
    if not pa_path:
        doi = _extract_clippings_doi(fm)
        if doi:
            for pa_stem, pa_p in pa_index.items():
                try:
                    if doi in pa_p.read_text(encoding='utf-8').lower():
                        pa_path, alias, method = pa_p, _chinese_title_from_h1(pa_p), 'doi'
                        break
                except Exception:
                    continue
    if not pa_path:
        result = _fuzzy_best(underscore_stem, pa_index)
        if result:
            pa_path, method = result[0], 'fuzzy'
            alias = _chinese_title_from_h1(pa_path)
    if not pa_path:
        return ('failed', None) if not existing else ('skipped', None), None
    if existing and _link_target(existing) == pa_path.stem:
        return 'skipped', None
    link = f'[[{pa_path.stem}|{alias}]]' if alias else f'[[{pa_path.stem}]]'
    fm['paper-analyze'] = link
    print(f'[PA] {method:10s}  {clip_md.name} -> {pa_path.name}')
    return 'matched', pa_path


def _match_fe(clip_md: Path, fm: dict, fe_index: Dict[str, Path],
              fe_reverse: Dict[str, Tuple[Path, str]], force: bool):
    existing = fm.get('figure-extractor')
    if existing and not force:
        return 'skipped', None
    underscore_stem = clip_md.stem.replace(' ', '_')
    fe_path, alias, method = None, None, ''
    rev = fe_reverse.get(underscore_stem)
    if rev:
        fe_path, alias, method = rev[0], rev[1], 'reverse'
    if not fe_path:
        fe_path = fe_index.get(underscore_stem)
        if fe_path:
            method = 'filename'
    if not fe_path:
        result = _fuzzy_best(underscore_stem + '_figures', {k: v for k, v in fe_index.items()})
        if result:
            fe_path, method = result[0], 'fuzzy'
    if not fe_path:
        return ('failed', None) if not existing else ('skipped', None), None
    if existing and _link_target(existing) == fe_path.stem:
        return 'skipped', None
    link = f'[[{fe_path.stem}|{alias}]]' if alias else f'[[{fe_path.stem}]]'
    fm['figure-extractor'] = link
    print(f'[FE] {method:10s}  {clip_md.name} -> {fe_path.name}')
    return 'matched', fe_path


def _match_prop(fm, prop, display, index_map, stem, clip_name, force, alias=None):
    existing = fm.get(prop)
    path = index_map.get(stem)
    if not path:
        return ('skipped', None) if existing else ('failed', None), None
    if existing and (not force or _link_target(existing) == path.stem):
        return 'skipped', None
    link = f'[[{path.stem}|{alias}]]' if alias else f'[[{path.stem}]]'
    fm[prop] = link
    print(f'[{display}] filename       {clip_name} -> {path.name}')
    return 'matched', path


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
        fr = _first_ref_target(fm.get('reference', []))
        if fr:
            by_first_ref[fr] = md
        chi_doi_sets[md] = _extract_doi_set(fm.get('reference', []))
        title = fm.get('title', '')
        if isinstance(title, list):
            title = ' '.join(str(t) for t in title)
        chi_display[md] = str(title).strip() or md.stem
        pt_target = _extract_wikilink_name(fm.get('paper-translate'))
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
                    h1_info = _parse_h1_wikilink(md.read_text(encoding='utf-8'))
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
    print(f'Claude: {len(pa_index)} PA, {len(fe_index)} FE, {len(pa_reverse)} PA-reverse, {len(fe_reverse)} FE-reverse\n')

    stats = {
        'pt': {'matched': 0, 'skipped': 0, 'failed': 0, 'methods': {'reverse': 0, 'source': 0, 'first_ref': 0, 'jaccard': 0}},
        'pa': {'matched': 0, 'skipped': 0, 'failed': 0, 'methods': {}},
        'fe': {'matched': 0, 'skipped': 0, 'failed': 0, 'methods': {}},
    }

    for clip_md in sorted(clip_dir.rglob('*.md')):
        fm, body = parse_frontmatter_file(clip_md)
        if not fm:
            print(f'SKIP (no fm): {clip_md.name}')
            for k in ('pt', 'pa', 'fe'):
                stats[k]['skipped'] += 1
            continue
        underscore_stem = clip_md.stem.replace(' ', '_')
        any_changed = False

        existing_pt = fm.get('paper-translate')
        if existing_pt and not force:
            stats['pt']['skipped'] += 1
        else:
            clip_src = (fm.get('source') or '').strip().lower().rstrip('/')
            clip_refs = fm.get('reference', [])
            clip_fr = _first_ref_target(clip_refs)
            chi_path = None; method = ''; score = 0.0; chi_alias = None; clip_dois = set()
            rev = chi_reverse.get(clip_md.stem)
            if rev:
                chi_path, chi_alias, method, score = rev[0], rev[1], 'reverse', 1.0
            elif clip_src and clip_src in by_source:
                chi_path, method, score = by_source[clip_src], 'source', 1.0
            elif clip_fr and clip_fr in by_first_ref:
                chi_path, method, score = by_first_ref[clip_fr], 'first_ref', 1.0
            else:
                clip_dois = _extract_doi_set(clip_refs)
                for chi_p, chi_dois in chi_doi_sets.items():
                    s = _jaccard(clip_dois, chi_dois)
                    if s > score:
                        score, chi_path = s, chi_p
                if score >= threshold:
                    method = 'jaccard'
                else:
                    chi_path = None
            if chi_path and existing_pt and _link_target(existing_pt) == chi_path.stem:
                stats['pt']['skipped'] += 1
            elif chi_path:
                display = chi_alias or chi_display.get(chi_path) or chi_path.stem
                fm['paper-translate'] = f'[[{chi_path.stem}|{display}]]'
                stats['pt']['matched'] += 1; stats['pt']['methods'][method] += 1; any_changed = True
                print(f'[PT] {method:10s} (conf={score:.2f})  {clip_md.name} -> {chi_path.name}')
            elif not existing_pt:
                stats['pt']['failed'] += 1
                if verbose:
                    print(f'[PT] FAIL: {clip_md.name}')
                    for cand_p, cand_s in sorted(((p, _jaccard(clip_dois, d)) for p, d in chi_doi_sets.items()), key=lambda x: x[1], reverse=True)[:3]:
                        print(f'  jaccard={cand_s:.3f}  {cand_p.name}')
            else:
                stats['pt']['skipped'] += 1

        pa_result, pa_path = _match_pa(clip_md, fm, pa_index, pa_reverse, force)
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
    print(f'[PT] Matched: {stats["pt"]["matched"]}  Skipped: {stats["pt"]["skipped"]}  Failed: {stats["pt"]["failed"]}  Methods: reverse={stats["pt"]["methods"]["reverse"]} source={stats["pt"]["methods"]["source"]} first_ref={stats["pt"]["methods"]["first_ref"]} jaccard={stats["pt"]["methods"]["jaccard"]}')
    print(f'[PA] Matched: {stats["pa"]["matched"]}  Skipped: {stats["pa"]["skipped"]}  Failed: {stats["pa"]["failed"]}')
    print(f'[FE] Matched: {stats["fe"]["matched"]}  Skipped: {stats["fe"]["skipped"]}  Failed: {stats["fe"]["failed"]}')
    return stats['pt']['matched'] + stats['pa']['matched'] + stats['fe']['matched'] > 0
