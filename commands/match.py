"""/s: Fuzzy matcher linking Clippings notes to PA (paper-analyze) / PT (paper-translate) / FE (figure-extractor).
3 strategies: source field exact → first_ref DOI exact → Jaccard similarity on DOI sets.
"""
import re
from pathlib import Path
from typing import Dict, Optional

from core.doi import PATTERN_DOI as DOI_RE
from core.frontmatter import parse_frontmatter_file, dump_frontmatter

WIKILINK_RE = re.compile(r'\[\[([^|]+)\|([^]]+)\]\]')
LINK_TARGET_RE = re.compile(r'\[\[\s*([^|\]]+)')
JACCARD_THRESHOLD = 0.85


def _extract_doi_set(ref_list: list) -> set:
    if not ref_list:
        return set()
    dois = set()
    for ref in ref_list:
        if not isinstance(ref, str):
            continue
        ref_clean = ref.replace('\n', ' ')
        m = WIKILINK_RE.search(ref_clean)
        if m:
            dois.update(DOI_RE.findall(m.group(2)))
        else:
            dois.update(DOI_RE.findall(ref_clean))
    return dois


def _first_ref_target(ref_list: list) -> Optional[str]:
    if not ref_list:
        return None
    ref0 = ref_list[0].replace('\n', ' ').strip() if isinstance(ref_list[0], str) else str(ref_list[0]).replace('\n', ' ').strip()
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


def _match_prop(fm, prop, display, index_map, stem, clip_name, force):
    existing = fm.get(prop)
    path = index_map.get(stem)
    if existing and (not force or not path or _link_target(existing) == path.stem):
        return 'skipped', None
    if not path:
        return 'failed', None
    fm[prop] = f'[[{path.stem}]]'
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
    print(f'Chi: {len(by_source)} src, {len(by_first_ref)} first-ref, {len(chi_doi_sets)} total\n')

    pa_index: Dict[str, Path] = {}
    fe_index: Dict[str, Path] = {}
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
        print(f'Claude: {len(pa_index)} PA, {len(fe_index)} FE\n')

    pt_matched = pt_skipped = pt_failed = 0
    pt_methods = {'source': 0, 'first_ref': 0, 'jaccard': 0}
    pa_matched = pa_skipped = pa_failed = 0
    fe_matched = fe_skipped = fe_failed = 0

    for clip_md in sorted(clip_dir.rglob('*.md')):
        fm, body = parse_frontmatter_file(clip_md)
        if not fm:
            print(f'SKIP (no fm): {clip_md.name}')
            pt_skipped += 1; pa_skipped += 1; fe_skipped += 1
            continue
        underscore_stem = clip_md.stem.replace(' ', '_')
        any_changed = False

        existing_pt = fm.get('paper-translate')
        if existing_pt and not force:
            pt_skipped += 1
        else:
            clip_src = (fm.get('source') or '').strip().lower().rstrip('/')
            clip_refs = fm.get('reference', [])
            clip_fr = _first_ref_target(clip_refs)
            clip_dois = None
            chi_path = None; method = ''; score = 0.0
            if clip_src and clip_src in by_source:
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
                pt_skipped += 1
            elif chi_path:
                display = chi_display.get(chi_path) or chi_path.stem
                fm['paper-translate'] = f'[[{chi_path.stem}|{display}]]'
                pt_matched += 1; pt_methods[method] += 1; any_changed = True
                print(f'[PT] {method:10s} (conf={score:.2f})  {clip_md.name} -> {chi_path.name}')
            elif existing_pt:
                pt_skipped += 1
            else:
                pt_failed += 1
                if verbose:
                    print(f'[PT] FAIL: {clip_md.name}')
                    for cand_p, cand_s in sorted(((p, _jaccard(clip_dois, d)) for p, d in chi_doi_sets.items()), key=lambda x: x[1], reverse=True)[:3]:
                        print(f'  jaccard={cand_s:.3f}  {cand_p.name}')

        pa_result, _ = _match_prop(fm, 'paper-analyze', 'PA', pa_index, underscore_stem, clip_md.name, force)
        if pa_result == 'matched': pa_matched += 1; any_changed = True
        elif pa_result == 'skipped': pa_skipped += 1
        else: pa_failed += 1

        fe_result, _ = _match_prop(fm, 'figure-extractor', 'FE', fe_index, underscore_stem, clip_md.name, force)
        if fe_result == 'matched': fe_matched += 1; any_changed = True
        elif fe_result == 'skipped': fe_skipped += 1
        else: fe_failed += 1

        if any_changed and not dry_run:
            clip_md.write_text(dump_frontmatter(fm, body), encoding='utf-8')

    print(f'\n=== Results ===')
    print(f'[PT] Matched: {pt_matched}  Skipped: {pt_skipped}  Failed: {pt_failed}  Methods: source={pt_methods["source"]} first_ref={pt_methods["first_ref"]} jaccard={pt_methods["jaccard"]}')
    print(f'[PA] Matched: {pa_matched}  Skipped: {pa_skipped}  Failed: {pa_failed}')
    print(f'[FE] Matched: {fe_matched}  Skipped: {fe_skipped}  Failed: {fe_failed}')
    return pt_matched + pa_matched + fe_matched > 0
