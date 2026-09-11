"""/s: PubMed MeSH Concept Explorer - queries PubMed E-utilities for MeSH terms and codes."""

import html
import random
import re
import time
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from pathlib import Path

import requests

from core.doi import (PATTERN_DOI, PATTERN_FS_INVALID, find_plausible_dois,
                      normalize_unicode_dashes, process_doi)
from commands.markdown_graph import run_markdown_graph

USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0')
EUPMC_BASE = 'https://www.ebi.ac.uk/europepmc/webservices/rest'
XLINK = '{http://www.w3.org/1999/xlink}href'

PATTERN_PMID_LABELED = re.compile(r'PMID:?\s*(\d{6,9})', re.IGNORECASE)
PATTERN_PMC_ID = re.compile(r'PMC\d+', re.IGNORECASE)
PATTERN_BARE_NUM = re.compile(r'(?<![\d.])(\d{7,9})(?![\d.])')
PATTERN_LINE_JUNK = re.compile(r'[|\[\]()*#-]')
PATTERN_HTML_TAG = re.compile(r'<[^>]+>')
PATTERN_INLINE_DOI = re.compile(r'\s*doi:\s*10\.\d{4,9}/[-A-Za-z0-9._;()/:]+', re.IGNORECASE)
_TITLE_SIM = 0.5
_CHUNK = 40


# ── 输入解析 ──────────────────────────────────────────────

def _read_input(input_arg):
    if input_arg:
        try:
            p = Path(input_arg.strip('"'))
            if p.is_file():
                for enc in ('utf-8', 'gbk'):
                    try:
                        return p.read_text(encoding=enc)
                    except UnicodeDecodeError:
                        continue
        except (OSError, ValueError):
            pass
        return input_arg
    print('请粘贴输入（DOI/PMID/标题混合，空行结束）:')
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip():
            break
        lines.append(line)
    return '\n'.join(lines)


def _title_candidate(line):
    cand = PATTERN_LINE_JUNK.sub(' ', line).strip()
    words = [w for w in cand.split() if len(w) >= 4 and w[0].isascii() and w[0].isalpha()]
    return cand if len(words) >= 3 and 20 <= len(cand) <= 300 else None


def _extract_identifiers(text):
    items, seen = [], set()

    def _add(kind, val):
        key = f'{kind}:{val.lower()}'
        if key not in seen:
            seen.add(key)
            items.append((kind, val))

    for raw in find_plausible_dois(text):
        _add('doi', process_doi(raw)[0])
    rest = PATTERN_PMC_ID.sub(' ', PATTERN_DOI.sub(' ', text))
    for m in PATTERN_PMID_LABELED.finditer(rest):
        _add('pmid', m.group(1))
    for m in PATTERN_BARE_NUM.finditer(rest):
        _add('pmid', m.group(1))
    for line in text.splitlines():
        stripped = PATTERN_PMC_ID.sub(' ', line)
        if PATTERN_DOI.search(line) or PATTERN_PMID_LABELED.search(line) or PATTERN_BARE_NUM.search(stripped):
            continue
        if cand := _title_candidate(line):
            _add('title', cand)
    return items


# ── EuropePMC API ─────────────────────────────────────────

def _eupmc_get(url, params=None, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=60,
                             headers={'User-Agent': USER_AGENT})
            if r.status_code == 200:
                return r
            if r.status_code not in (429, 500, 502, 503, 504):
                return None
            wait = int(r.headers.get('Retry-After', 10 * (attempt + 1)))
        except Exception as e:
            if attempt == retries - 1:
                print(f'请求异常: {e}')
            wait = 10 * (attempt + 1)
        time.sleep(wait)
    return None


def _query_clause(kind, val):
    if kind == 'pmid':
        return f'ext_id:{val}'
    if kind == 'doi':
        return f'DOI:"{val}"'
    return f'TITLE:"{val}"'


def _fetch_metadata(items):
    results = []
    for i in range(0, len(items), _CHUNK):
        chunk = items[i:i + _CHUNK]
        resp = _eupmc_get(f'{EUPMC_BASE}/search', {
            'query': ' OR '.join(_query_clause(k, v) for k, v in chunk),
            'format': 'json', 'resultType': 'core', 'pageSize': 100,
        })
        if resp is None:
            print(f'元数据批次 {i // _CHUNK + 1} 请求失败')
            continue
        results.extend(resp.json().get('resultList', {}).get('result', []))
        if i + _CHUNK < len(items):
            time.sleep(random.uniform(1.0, 2.0))
    return results


def _match_one(results, kind, val):
    if kind == 'pmid':
        return next((r for r in results if r.get('id') == val), None)
    if kind == 'doi':
        lv = val.lower()
        return next((r for r in results if r.get('doi', '').lower() == lv), None)
    best, best_score = None, 0.0
    for r in results:
        score = SequenceMatcher(None, (r.get('title') or '').lower(), val.lower()).ratio()
        if score > best_score:
            best, best_score = r, score
    return best if best_score >= _TITLE_SIM else None


def _fetch_fulltext_xml(pmcid):
    resp = _eupmc_get(f'{EUPMC_BASE}/{pmcid}/fullTextXML')
    return resp.text if resp is not None else None


# ── JATS XML → MD ─────────────────────────────────────────

def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _iter(elem, name):
    return (c for c in elem if _local(c.tag) == name)


def _first(elem, name):
    return next(_iter(elem, name), None)


def _inline(elem, skip_label=False, skip_tags=frozenset()):
    parts = [elem.text or '']
    for child in elem:
        tag = _local(child.tag)
        if (tag == 'label' and skip_label) or tag in skip_tags:
            pass
        elif tag == 'italic':
            parts.append(f'*{_inline(child)}*')
        elif tag == 'bold':
            parts.append(f'**{_inline(child)}**')
        elif tag == 'sub':
            parts.append(f'~{_inline(child)}~')
        elif tag == 'sup':
            parts.append(f'^{_inline(child)}^')
        elif tag == 'surname':
            parts.append(_inline(child) + ' ')
        else:
            parts.append(_inline(child, skip_label, skip_tags))
        parts.append(child.tail or '')
    return ''.join(parts)


def _para(elem):
    return ' '.join(_inline(elem).split())


def _blocks_md(container, level, pmcid, lines):
    for el in container:
        tag = _local(el.tag)
        if tag == 'sec':
            if _first(el, 'ref-list') is None:
                _sec_md(el, level, pmcid, lines)
        elif tag == 'p':
            lines.append(_para(el))
        elif tag == 'table-wrap':
            lines.extend(_table_md(el))
        elif tag == 'fig':
            lines.extend(_fig_md(el, pmcid))
        elif tag == 'list':
            lines.extend(_list_md(el))
        elif tag in ('disp-quote', 'boxed-text'):
            lines.append('> ' + _para(el))


def _sec_md(sec, level, pmcid, lines):
    title = _first(sec, 'title')
    if title is not None:
        lines.append(f'{"#" * min(level, 6)} {_para(title)}')
    _blocks_md(sec, level + 1, pmcid, lines)


def _table_md(tw):
    lines = []
    label = _first(tw, 'label')
    caption = _first(tw, 'caption')
    if label is not None:
        head = f'**{_para(label)}**'
        lines.append(head + (f' {_para(caption)}' if caption is not None else ''))
    table = _first(tw, 'table')
    if table is None:
        return lines
    rows = [[' '.join(_inline(c).split()) for c in tr if _local(c.tag) in ('td', 'th')]
            for tr in table.iter() if _local(tr.tag) == 'tr']
    rows = [r for r in rows if any(r)]
    if not rows:
        return lines
    width = max(len(r) for r in rows)
    rows = [r + [''] * (width - len(r)) for r in rows]
    lines.append('| ' + ' | '.join(rows[0]) + ' |')
    lines.append('|' + ' --- |' * width)
    lines += ['| ' + ' | '.join(r) + ' |' for r in rows[1:]]
    return lines


def _fig_md(fig, pmcid):
    graphic = next((g for g in fig.iter() if _local(g.tag) == 'graphic'), None)
    href = graphic.get(XLINK) if graphic is not None else None
    label = _first(fig, 'label')
    caption = _first(fig, 'caption')
    alt = _para(label) if label is not None else 'Figure'
    lines = []
    if href:
        lines.append(f'![{alt}](https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/bin/{href}.jpg)')
    if caption is not None:
        lines.append(f'**{alt}** {_para(caption)}')
    return lines


def _list_md(lst):
    ordered = lst.get('list-type') == 'order'
    return [f'{i}. {_para(item)}' if ordered else f'- {_para(item)}'
            for i, item in enumerate(_iter(lst, 'list-item'), 1)]


def _ref_doi(ref):
    doi = next((p.text.strip() for p in ref.iter()
                if _local(p.tag) == 'pub-id' and p.get('pub-id-type') == 'doi' and p.text), None)
    if doi is None:
        doi = next((e.get(XLINK) for e in ref.iter()
                    if _local(e.tag) == 'ext-link' and e.get('ext-link-type') == 'doi'
                    and e.get(XLINK)), None)
    return doi


def _refs_md(root):
    lines = []
    for ref_list in (el for el in root.iter() if _local(el.tag) == 'ref-list'):
        title = _first(ref_list, 'title')
        lines.append(f'## {_para(title) if title is not None else "参考文献"}')
        for i, ref in enumerate(_iter(ref_list, 'ref'), 1):
            cite = next((c for c in ref if _local(c.tag) in
                         ('mixed-citation', 'element-citation', 'citation', 'nlm-citation')), None)
            text = ' '.join(_inline(cite if cite is not None else ref,
                                    skip_label=True, skip_tags={'pub-id'}).split())
            doi = _ref_doi(ref)
            if doi is None:
                m = PATTERN_DOI.search(text)
                doi = process_doi(m.group(0))[0] if m else None
            text = PATTERN_INLINE_DOI.sub('', text)
            text = re.sub(r'\.\s*\.', '.', text).strip()
            lines.append(f'{i}. {text}' + (f' DOI: {doi}' if doi else ''))
    return lines


def _compose_md(meta, xml_text):
    root = ET.fromstring(xml_text)
    front = _first(root, 'front')
    body = _first(root, 'body')
    floats = _first(root, 'floats-group')
    year = meta.get('firstPublicationDate') or meta.get('journalInfo', {}).get('yearOfPublication', '')
    lines = [f'# {html.unescape(meta["title"])}', '',
             f'来源: https://pmc.ncbi.nlm.nih.gov/articles/{meta["pmcid"]}/',
             f'作者: {meta.get("authorString", "")}',
             f'DOI: {meta.get("doi", "")}',
             f'发表: {year}']
    abstract = None
    if front is not None and (am := _first(front, 'article-meta')) is not None:
        abstract = _first(am, 'abstract')
    if abstract is not None:
        lines += ['', '## Abstract']
        ps = [_para(p) for p in _iter(abstract, 'p')]
        lines.extend(ps or [_para(abstract)])
    if body is not None:
        lines.append('')
        _blocks_md(body, 2, meta['pmcid'], lines)
    if floats is not None:
        lines.append('')
        _blocks_md(floats, 2, meta['pmcid'], lines)
    refs = _refs_md(root)
    if refs:
        lines.append('')
        lines.extend(refs)
    return normalize_unicode_dashes('\n\n'.join(l for l in lines if l)) + '\n'


# ── 主流程 ────────────────────────────────────────────────

def _plain_stem(meta):
    raw = PATTERN_HTML_TAG.sub('', html.unescape(meta.get('title') or ''))
    title = re.sub(r'\s+', ' ', PATTERN_FS_INVALID.sub('', raw).replace('/', ' ')).strip('. ')
    return title[:150] or meta['pmcid']


def _print_non_oa(non_oa):
    if not non_oa:
        return
    print(f'\n非OA文章（{len(non_oa)}篇）:')
    for m in non_oa:
        print(f'  {m.get("doi") or "无DOI"}  {html.unescape(m.get("title", ""))}')


def run_pmce(input_arg, path, no_graph=False, dry_run=False):
    pending = Path(path)
    pending.mkdir(parents=True, exist_ok=True)
    text = _read_input(input_arg)
    items = _extract_identifiers(text)
    n_doi = sum(1 for k, _ in items if k == 'doi')
    n_pmid = sum(1 for k, _ in items if k == 'pmid')
    n_title = sum(1 for k, _ in items if k == 'title')
    print(f'识别标识 {len(items)} 个（DOI {n_doi} / PMID {n_pmid} / 标题 {n_title}）')
    if not items:
        return

    results = _fetch_metadata(items)
    print(f'EuropePMC返回 {len(results)} 条元数据')
    jobs, non_oa, seen_ids = [], [], set()
    for kind, val in items:
        meta = _match_one(results, kind, val)
        if meta is None:
            print(f'未匹配: [{kind}] {val[:60]}')
            continue
        if meta.get('id') in seen_ids:
            continue
        seen_ids.add(meta.get('id'))
        if meta.get('pmcid') and meta.get('isOpenAccess') == 'Y':
            jobs.append(meta)
        else:
            non_oa.append(meta)
    print(f'OA可抓 {len(jobs)} 篇 / 非OA {len(non_oa)} 篇')
    if dry_run:
        _print_non_oa(non_oa)
        return

    used = set()
    written = []
    for i, meta in enumerate(jobs, 1):
        stem = _plain_stem(meta)
        target = pending / f'{stem}.md'
        if target.exists():
            print(f'[{i}/{len(jobs)}] 跳过已存在: {target.name}')
            continue
        if stem.lower() in used:
            target = pending / f'{stem}_{meta["pmcid"]}.md'
        used.add(stem.lower())
        xml = _fetch_fulltext_xml(meta['pmcid'])
        if xml is None:
            non_oa.append(meta)
            continue
        try:
            target.write_text(_compose_md(meta, xml), encoding='utf-8')
            written.append(target)
            print(f'[{i}/{len(jobs)}] {target.name}')
        except Exception as e:
            print(f'解析失败 {meta.get("id")}: {e}')
        time.sleep(random.uniform(2.0, 4.0))

    _print_non_oa(non_oa)
    print(f'\n写入 {len(written)} 个MD → {pending}')
    if written and not no_graph:
        print('建立引用图谱...')
        run_markdown_graph(str(pending.parent))
