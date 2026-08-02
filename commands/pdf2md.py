"""/s: MinerU API batch PDF-to-Markdown pipeline.
Uploads PDFs to MinerU (mineru.net) in batches ≤45, downloads extracted Markdown +
formula/table images, enriches frontmatter with Crossref API references &
PubMed cited-by data.
"""
import json
import os
import re
import shutil
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import pdfplumber
import requests

from core.crossref_api import (fetch_references, get_doi_from_citation,
                               get_cited_by_pubmed, load_cache, save_cache)
from core.doi import (PATTERN_DOI, normalize_unicode_dashes, process_doi, repair_doi_text)
from core.frontmatter import dump_frontmatter, parse_frontmatter_str
from core.markdown_utils import clean_markdown_body
from config import OBSIDIAN_ROOT
from core.refs import build_existing_dois, process_existing_references
from difflib import SequenceMatcher
from commands.match import run_match

_CHAR_MAP = str.maketrans({
    '\u201c': '"', '\u201d': '"', '\u2018': "'", '\u2019': "'",
    '\u2013': '-', '\u2014': '-',
    '\u2026': '...',
})


def _normalize_stem(s):
    s = s.translate(_CHAR_MAP)
    return re.sub(r'\s+', ' ', s.strip())


def _build_clippings_index():
    idx = {}
    for d in OBSIDIAN_ROOT.iterdir():
        if not d.is_dir() or d.name.startswith('.') or d.name in ('PDF', 'ZIP', 'TRASH'):
            continue
        clip = d / 'Clippings'
        if not clip.is_dir():
            continue
        for md in clip.rglob('*.md'):
            key = _normalize_stem(md.stem).lower()
            idx.setdefault(key, []).append((md, d))
    return idx


def _find_clippings_md(pdf_stem, idx):
    norm = _normalize_stem(pdf_stem).lower()
    if norm in idx:
        return idx[norm][0]
    best_score = 0.0
    best_entry = None
    sm = SequenceMatcher()
    for key, entries in idx.items():
        sm.set_seqs(norm, key)
        if sm.quick_ratio() < 0.7:
            continue
        score = sm.ratio()
        if score > best_score:
            best_score = score
            best_entry = entries[0]
    return best_entry if best_score >= 0.85 else (None, None)


URL_PATTERN = re.compile(
    r'https?://[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)',
    re.IGNORECASE
)


def read_text_file(path: Path, encoding='utf-8'):
    try:
        with open(path, 'r', encoding=encoding) as f:
            return f.read()
    except Exception as e:
        print(f'读取文件失败 {path}: {e}')
        return None


def read_json_file(path: Path, encoding='utf-8'):
    content = read_text_file(path, encoding)
    if content is None:
        return None
    try:
        return json.loads(content)
    except Exception as e:
        print(f'解析JSON失败 {path}: {e}')
        return None


def extract_text(obj):
    stack = [obj]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if isinstance(item.get('content'), str):
                yield item['content']
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, str):
            yield item


def _build_clippings_all_doi_set(md_dir):
    existing = set()
    for md_file in md_dir.glob('*.md'):
        try:
            fm, _ = parse_frontmatter_str(md_file.read_text(encoding='utf-8'))
        except Exception:
            continue
        doi = fm.get('doi')
        if isinstance(doi, list) and doi:
            doi = doi[0]
        if isinstance(doi, str) and (m := PATTERN_DOI.search(doi)):
            existing.add(process_doi(m.group(0))[0].lower())
    return existing


def apply_upload_urls(token, files_info, url):
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
    data = {'files': files_info, 'model_version': 'vlm', 'enable_formula': True,
            'enable_table': True, 'language': 'ch'}
    status = None
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        status = response.status_code
        result = response.json()
    except requests.exceptions.JSONDecodeError:
        return {'success': False, 'error': f'JSON解析失败 (HTTP {status})'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    if not isinstance(result, dict):
        return {'success': False, 'error': 'API返回类型异常'}
    if result.get('code') != 0:
        return {'success': False, 'error': result.get('msg', '未知错误')}
    return {'success': True, 'batch_id': result['data']['batch_id'],
            'upload_urls': result['data']['file_urls']}


def upload_file(upload_url, file_path):
    try:
        with open(file_path, 'rb') as f:
            res = requests.put(upload_url, data=f, timeout=60)
        if res.status_code == 200:
            return True
        print(f'上传失败：{file_path} | 状态码：{res.status_code}')
    except Exception as e:
        print(f'上传异常：{file_path} | 错误：{str(e)}')
    return False


def _get_main_doi(pdf_path, content, fm, pdf_text=None):
    fm_doi = fm.get('doi')
    if isinstance(fm_doi, list) and fm_doi:
        fm_doi = fm_doi[0]
    if isinstance(fm_doi, str) and (m := PATTERN_DOI.search(fm_doi)):
        return process_doi(m.group(0))[0]
    if pdf_text:
        if dois_found := PATTERN_DOI.findall(repair_doi_text(pdf_text)):
            return process_doi(dois_found[0])[0]
    elif pdf_path and pdf_path.exists():
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = normalize_unicode_dashes(page.extract_text() or '')
                    if dois_found := PATTERN_DOI.findall(repair_doi_text(text)):
                        return process_doi(dois_found[0])[0]
        except Exception as e:
            print(f'PDF提取主DOI失败: {e}')
    doi_line = next((l for l in content.splitlines() if l.strip().lower().startswith('doi:')), None)
    if doi_line and (m := PATTERN_DOI.search(doi_line)):
        return process_doi(m.group(0))[0]
    if dois := PATTERN_DOI.findall(content):
        return process_doi(dois[0])[0]
    return None


def _append_crossref_refs(fm, rest, main_doi, crossref_cache, md_name):
    if not main_doi:
        return main_doi, None
    references = fetch_references(main_doi, crossref_cache)
    if not references:
        return main_doi, None
    ref_dois = []
    existing_dois = build_existing_dois(fm.get('reference', []))
    for ref in references:
        if not ref['doi']:
            continue
        display_doi, safe_filename = process_doi(ref['doi'])
        if display_doi.lower() not in existing_dois:
            ref_dois.append(f'[[{safe_filename}|{display_doi}]]')
            existing_dois.add(display_doi.lower())
    if ref_dois:
        fm['reference'] = fm.get('reference', []) + ref_dois
    if '## 参考文献' in rest:
        return main_doi, None
    pieces = ['\n\n## 参考文献\n']
    for i, ref in enumerate(references, 1):
        text = ref.get('text', '')
        doi_str = ref.get('doi', '')
        if text:
            line = f'{i}. {text}'
            if doi_str:
                line += f' DOI: {doi_str}'
        elif doi_str:
            line = f'{i}. DOI: {doi_str}'
        else:
            continue
        pieces.append(line + '\n')
    print(f'已将 {len(references)} 条参考文献添加到 {md_name}')
    return main_doi, ''.join(pieces)


def _collect_all_dois(content, json_src):
    all_dois = set(PATTERN_DOI.findall(repair_doi_text(content)))
    urls_found = []
    if not (json_src and json_src.exists()):
        return all_dois, urls_found, content
    content_data = read_json_file(json_src)
    if content_data is None:
        return all_dois, urls_found, content
    try:
        for page in content_data:
            for block in page:
                for text in extract_text(block):
                    text = normalize_unicode_dashes(text)
                    all_dois.update(PATTERN_DOI.findall(repair_doi_text(text)))
                    urls_found.extend(URL_PATTERN.findall(text))
    except Exception as e:
        print(f'解析 JSON 内容时出错 {json_src}: {e}')
    if urls_found:
        unique_urls = sorted(set(urls_found), key=len, reverse=True)
        escaped = '|'.join(re.escape(u) for u in unique_urls)
        content = re.sub(
            rf'(?<!\]\()({escaped})',
            r'[\1](sslocal://flow/file_open?url=%5C1&flow_extra=eyJsaW5rX3R5cGUiOiJjb2RlX2ludGVycHJldGVyIn0=)',
            content
        )
    return all_dois, urls_found, content


def _extract_pdf_text(pdf_path, all_dois):
    if not (pdf_path and pdf_path.exists()):
        return None
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_text = []
            for page in pdf.pages:
                text = normalize_unicode_dashes(page.extract_text() or '')
                pages_text.append(text)
                all_dois.update(PATTERN_DOI.findall(repair_doi_text(text)))
        return '\n'.join(pages_text)
    except Exception as e:
        print(f'从PDF提取DOI失败 {pdf_path.name}: {e}')
        return None


def _update_cited_by(fm, main_doi, crossref_cache, cited_by_max, clippings_doi_set):
    cited_by_date = fm.get('cited_by_date')
    if cited_by_date:
        try:
            last = datetime.strptime(str(cited_by_date)[:10], '%Y-%m-%d')
            if (datetime.now() - last).days < 30:
                return
        except ValueError:
            pass
    count, citing_dois = get_cited_by_pubmed(main_doi, crossref_cache, clippings_doi_set, cited_by_max)
    fm.pop('cited_by_count', None)
    fm['cited_by_date'] = datetime.now().strftime('%Y-%m-%d')
    if citing_dois:
        fm['cited_by'] = [f'[[{safe}|{display}]]'
                          for display, safe in (process_doi(d) for d in citing_dois)]


def _merge_new_dois(fm, all_dois, md_name):
    unique_dois = {doi.lower(): doi for doi in all_dois}
    if not unique_dois:
        print(f'文件 {md_name} 无有效DOI，跳过reference更新')
        return
    new_refs = []
    existing_dedup = build_existing_dois(fm.get('reference', []))
    for doi_raw in unique_dois.values():
        display_doi, safe_filename = process_doi(doi_raw)
        if display_doi.lower() not in existing_dedup:
            new_refs.append(f'[[{safe_filename}|{display_doi}]]')
            existing_dedup.add(display_doi.lower())
    if new_refs:
        fm['reference'] = fm.get('reference', []) + new_refs
        print(f'已将{len(new_refs)}个唯一DOI添加到 {md_name} 的reference')


def _pin_main_doi(fm, main_doi, md_stem):
    refs = [r for r in fm.get('reference', [])
            if not (r.startswith('[[') and r.endswith(']]') and '|' in r
                    and r[2:-2].split('|', 1)[1].strip().lower() == main_doi.lower())]
    refs.insert(0, f'[[{md_stem}|{main_doi}]]')
    fm['reference'] = refs


def _process_md_content(md_dst, json_src, pdf_path, enable_api_refs, crossref_cache,
                        enable_cited_by=False, cited_by_max=10, images_dir=None,
                        clippings_doi_set=None):
    content = normalize_unicode_dashes(read_text_file(md_dst)) if md_dst.exists() else None
    if content is None:
        return

    all_dois, _urls, content = _collect_all_dois(content, json_src)
    pdf_text = _extract_pdf_text(pdf_path, all_dois)

    fm, rest = parse_frontmatter_str(content)
    main_doi = _get_main_doi(pdf_path, content, fm, pdf_text)
    if main_doi is None and enable_api_refs:
        title = fm.get('title', md_dst.stem)
        result = get_doi_from_citation(title, crossref_cache)
        if result:
            main_doi = process_doi(result[0])[0]
            print(f'Crossref标题回退确认主DOI: {main_doi}')

    if enable_cited_by and main_doi:
        if clippings_doi_set is None:
            clippings_doi_set = _build_clippings_all_doi_set(md_dst.parent)
        _update_cited_by(fm, main_doi, crossref_cache, cited_by_max, clippings_doi_set)

    existing_refs = fm.get('reference', [])
    if existing_refs:
        fm['reference'] = process_existing_references(existing_refs)
    _merge_new_dois(fm, all_dois, md_dst.name)

    if enable_api_refs:
        _, ref_section = _append_crossref_refs(fm, rest, main_doi, crossref_cache, md_dst.name)
        if ref_section:
            rest += ref_section
    if main_doi:
        _pin_main_doi(fm, main_doi, md_dst.stem)

    rest = clean_markdown_body(rest)
    if images_dir:
        rest = re.sub(r'\]\(images/', f']({images_dir.resolve().as_posix()}/', rest)
    fm.pop('特殊引用数', None)
    try:
        with open(md_dst, 'w', encoding='utf-8') as f:
            f.write(dump_frontmatter(fm, rest))
    except Exception as e:
        print(f'更新MD文件失败 {md_dst}: {e}')


def _download_zip(zip_url, zip_path, file_name, idx):
    if zip_path.exists():
        print(f'[{idx}] ZIP已存在: {file_name}')
        return idx, True
    print(f'[{idx}] 下载: {file_name}')
    try:
        r = requests.get(zip_url, stream=True, timeout=120)
        r.raise_for_status()
        with open(zip_path, 'wb') as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return idx, True
    except Exception as e:
        print(f'[{idx}] 下载失败: {e}')
        return idx, False


def _poll_batch_completion(batch_id, token, max_wait=1800, expected_count=None):
    url = f'https://mineru.net/api/v4/extract-results/batch/{batch_id}'
    headers = {'Authorization': f'Bearer {token}'}
    TERMINAL = {'done', 'failed'}
    files = []
    start = time.time()
    while time.time() - start < max_wait:
        try:
            resp = requests.get(url, headers=headers, timeout=30)
        except Exception as e:
            print(f'查询请求异常: {str(e)}')
            return None
        if resp.status_code != 200:
            print(f'查询失败，状态码: {resp.status_code}')
            return None
        data = resp.json()
        if data.get('code') != 0:
            print(f"查询失败: {data.get('msg', '未知错误')}")
            return None
        files = data['data']['extract_result']
        if not files:
            print('批次无文件数据')
            return None
        states = [f['state'] for f in files]
        done_count = states.count('done')
        terminal_count = sum(1 for s in states if s in TERMINAL)
        target = expected_count if expected_count else len(files)
        print(f'目前状态: {states} | 完成数: {done_count}/{len(files)} | 目标: {target}')
        if terminal_count >= target:
            return [f for f in files if f['state'] == 'done']
        time.sleep(10)
    print('轮询批次超时，返回已完成文件')
    return [f for f in files if f['state'] == 'done']


def _find_extracted_files(temp_dir):
    md_src = img_src = json_src = None
    for root, dirs, files_in_dir in os.walk(temp_dir):
        if not md_src and 'full.md' in files_in_dir:
            md_src = Path(root) / 'full.md'
        if not img_src and 'images' in dirs:
            img_src = Path(root) / 'images'
        if not json_src and 'content_list_v2.json' in files_in_dir:
            json_src = Path(root) / 'content_list_v2.json'
        if md_src and img_src and json_src:
            break
    return md_src, img_src, json_src


def _mark_pdf_done(pdf_path):
    try:
        pdf_path.rename(pdf_path.parent / f'完成_{pdf_path.name}')
    except Exception:
        shutil.move(str(pdf_path), str(pdf_path.parent.parent / 'TRASH' / pdf_path.name))


def download_and_process_batch(batch_id, path_zip, path_md0, token, path_pdf,
                               enable_api_refs, crossref_cache, enable_cited_by=False,
                               cited_by_max=10, batch_files=None):
    name_to_path = {Path(f).name: Path(f) for f in (batch_files or [])}
    images_output = path_md0 / 'images'
    images_output.mkdir(exist_ok=True)
    files = _poll_batch_completion(batch_id, token, expected_count=len(batch_files or []))
    if files is None:
        return
    print(f'批次 {batch_id} 找到 {len(files)} 个文件，所有文件已处理完成')
    download_tasks = [
        (f_info['full_zip_url'], path_zip / f"{f_info['data_id']}.zip",
         f_info['file_name'], idx)
        for idx, f_info in enumerate(files, 1)
    ]
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_download_zip, *task): task[3] for task in download_tasks}
        for future in as_completed(futures):
            future.result()

    clippings_doi_set = _build_clippings_all_doi_set(path_md0) if enable_cited_by else None
    for idx, f_info in enumerate(files, 1):
        file_name = f_info['file_name']
        data_id = f_info['data_id']
        zip_path_ = path_zip / f'{data_id}.zip'
        if not zip_path_.exists():
            continue
        print(f'[{idx}] 处理: {file_name}')
        temp_dir = path_zip / f'temp_{data_id}'
        temp_dir.mkdir(exist_ok=True)
        try:
            with zipfile.ZipFile(zip_path_, 'r') as z:
                z.extractall(temp_dir)
            md_src, img_src, json_src = _find_extracted_files(temp_dir)
            md_dst = None
            if md_src:
                md_dst = path_md0 / f'{Path(file_name).stem}.md'
                shutil.move(str(md_src), str(md_dst))
            if img_src:
                for img_file in img_src.glob('*'):
                    try:
                        shutil.copy2(img_file, images_output / img_file.name)
                    except Exception:
                        pass
            if md_dst:
                pdf_file_path = name_to_path.get(file_name, path_pdf / file_name)
                _process_md_content(md_dst, json_src, pdf_file_path, enable_api_refs,
                                    crossref_cache, enable_cited_by, cited_by_max,
                                    images_output, clippings_doi_set)
                _mark_pdf_done(pdf_file_path)
        except Exception as e:
            print(f'处理失败: {e}')
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    print(f'批次 {batch_id} 处理完成！Markdown: {path_md0}，图片: {images_output}')


def run_pdf2md(path_pdf: str = None, path_zip: str = None, path_md0: str = None,
               enable_api_refs: bool = True, enable_cited_by: bool = True,
               cited_by_max: int = 10, token_path: str = None) -> None:
    token_path = token_path or r'C:\ResearchFront\DATA\API\MinerU.txt'
    path_pdf = path_pdf or r'C:\Vault\PDF'
    path_zip = path_zip or r'C:\Vault\ZIP'
    path_md0 = path_md0 or r'C:\Vault\Claude\MDfrPDF'

    token_content = read_text_file(Path(token_path))
    if not token_content:
        print('无法读取API Token')
        return
    token = token_content.strip()

    clippings_idx = _build_clippings_index()
    crossref_cache = load_cache()
    pp = Path(path_pdf)
    pz = Path(path_zip)
    pm = Path(path_md0)
    for p in (pp, pz, pm):
        p.mkdir(parents=True, exist_ok=True)

    trash_dir = pp.parent / 'TRASH'
    trash_dir.mkdir(exist_ok=True)
    pdf_files = []
    for pdf_file in sorted({f.absolute() for f in pp.rglob('*.pdf') if '完成' not in f.name}):
        done_path = pdf_file.parent / f'完成_{pdf_file.name}'
        if not done_path.exists():
            pdf_files.append(pdf_file)
            continue
        print(f'已存在完成版本: {pdf_file.name}')
        md_path, domain_dir = _find_clippings_md(pdf_file.stem, clippings_idx)
        if md_path:
            print(f'  找到已归档: {md_path.relative_to(OBSIDIAN_ROOT)}')
            print(f'  执行MATCH: {domain_dir}')
            match_ok = run_match(str(domain_dir), force=True)
            if match_ok:
                print(f'  MATCH成功，移入TRASH: {pdf_file.name}')
                try:
                    shutil.move(str(pdf_file), str(trash_dir / pdf_file.name))
                except Exception as e:
                    print(f'  移入TRASH失败: {e}')
            else:
                print(f'  MATCH无结果，跳过TRASH')
        else:
            print(f'  未找到对应.md，跳过TRASH')
    if not pdf_files:
        print('未找到需处理PDF')
        return

    batch_limit = 45
    batches = [pdf_files[i:i + batch_limit] for i in range(0, len(pdf_files), batch_limit)]
    print(f'共拆分为 {len(batches)} 个批次（每批 ≤ {batch_limit} 个文件）')

    total_success = 0
    batch_ids = []
    batch_file_map = {}
    url = 'https://mineru.net/api/v4/file-urls/batch'
    for batch_idx, batch_files in enumerate(batches, 1):
        print(f'处理批次 {batch_idx}/{len(batches)}')
        files_info = [{'name': Path(f).name, 'data_id': str(uuid.uuid4()), 'is_ocr': False}
                      for f in batch_files]
        url_result = apply_upload_urls(token, files_info, url)
        if not url_result['success']:
            print(f"批次 {batch_idx} 申请链接失败：{url_result['error']}")
            continue
        bid = url_result['batch_id']
        batch_ids.append(bid)
        print(f'批次 {batch_idx} 申请链接成功 | batch_id：{bid}')
        uploaded_files = [f for f, u in zip(batch_files, url_result['upload_urls'])
                          if upload_file(u, f)]
        batch_file_map[bid] = uploaded_files
        total_success += len(uploaded_files)
        print(f'批次 {batch_idx} 上传完成 | 成功：{len(uploaded_files)}/{len(batch_files)}')

    print(f'所有批次上传完成！总成功：{total_success}/{len(pdf_files)}')
    if not batch_ids:
        print('没有成功申请的批次，无需下载。')
        return
    print('\n开始下载并处理结果...')
    for bid in batch_ids:
        download_and_process_batch(bid, pz, pm, token, pp, enable_api_refs,
                                   crossref_cache, enable_cited_by, cited_by_max,
                                   batch_file_map.get(bid, []))
    save_cache(crossref_cache)
