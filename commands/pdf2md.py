"""/s: MinerU API batch PDF-to-Markdown pipeline.
Uploads PDFs to MinerU (mineru.net), downloads extracted Markdown + images,
enriches frontmatter with Crossref API references & PubMed cited-by data.
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
            if 'content' in item and isinstance(item['content'], str):
                yield item['content']
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, str):
            yield item


def process_existing_references(refs):
    processed, seen = [], set()

    def keep(item):
        if item not in seen:
            seen.add(item)
            processed.append(item)

    for ref in refs:
        ref = ref.strip()
        inner = ref[2:-2] if ref.startswith('[[') and ref.endswith(']]') else ''
        if '|' not in inner:
            keep(ref)
            continue
        s, d = (x.strip() for x in inner.split('|', 1))
        if not d:
            keep(ref)
            continue
        if d.lower() in seen:
            continue
        seen.add(d.lower())
        processed.append(f'[[{s.replace("/", "￥")}|{d}]]')
    return processed


def _build_existing_dois(references):
    existing = set()
    for ref in references:
        if ref.startswith('[[') and ref.endswith(']]') and '|' in ref:
            existing.add(ref[2:-2].split('|', 1)[1].strip().lower())
    return existing


def _build_clippings_all_doi_set(md_dir):
    existing = set()
    for md_file in md_dir.glob('*.md'):
        try:
            fm, _ = parse_frontmatter_str(md_file.read_text(encoding='utf-8'))
            doi = fm.get('doi')
            if isinstance(doi, list) and doi:
                doi = doi[0]
            if isinstance(doi, str) and (m := PATTERN_DOI.search(doi)):
                existing.add(process_doi(m.group(0))[0].lower())
        except Exception:
            pass
    return existing


def apply_upload_urls(token, files_info, url):
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
    data = {'files': files_info, 'model_version': 'vlm', 'enable_formula': True,
            'enable_table': True, 'language': 'ch'}
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        status = response.status_code
        result = response.json()
    except requests.exceptions.JSONDecodeError:
        return {'success': False, 'error': f'JSON解析失败 (HTTP {status})'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    if not isinstance(result, dict):
        return {'success': False, 'error': f'API返回类型异常'}
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
    existing_dois = _build_existing_dois(fm.get('reference', []))
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
            pieces.append(f'{i}. {text}')
            if doi_str:
                pieces[-1] += f' DOI: {doi_str}'
        elif doi_str:
            pieces.append(f'{i}. DOI: {doi_str}')
        else:
            continue
        pieces[-1] += '\n'
    print(f'已将 {len(references)} 条参考文献添加到 {md_name}')
    return main_doi, ''.join(pieces)


def _process_md_content(md_dst, json_src, pdf_path, enable_api_refs, crossref_cache,
                        enable_cited_by=False, cited_by_max=10, images_dir=None):
    content = normalize_unicode_dashes(read_text_file(md_dst)) if md_dst.exists() else None
    if content is None:
        return
    all_dois = set()
    all_dois.update(PATTERN_DOI.findall(repair_doi_text(content)))
    if json_src and json_src.exists():
        content_data = read_json_file(json_src)
        if content_data is not None:
            urls_found = []
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
    pdf_text = None
    if pdf_path and pdf_path.exists():
        try:
            with pdfplumber.open(pdf_path) as pdf:
                pages_text = []
                for page in pdf.pages:
                    text = normalize_unicode_dashes(page.extract_text() or '')
                    pages_text.append(text)
                    all_dois.update(set(PATTERN_DOI.findall(repair_doi_text(text))))
                pdf_text = '\n'.join(pages_text)
        except Exception as e:
            print(f'从PDF提取DOI失败 {pdf_path.name}: {e}')
    fm, rest = parse_frontmatter_str(content)
    main_doi = _get_main_doi(pdf_path, content, fm, pdf_text)
    if main_doi is None and enable_api_refs:
        title = fm.get('title', md_dst.stem)
        result = get_doi_from_citation(title, crossref_cache)
        if result:
            main_doi = process_doi(result[0])[0]
            print(f'Crossref标题回退确认主DOI: {main_doi}')
    if enable_cited_by and main_doi:
        cited_by_date = fm.get('cited_by_date')
        skip_cited_by = False
        if cited_by_date:
            try:
                last = datetime.strptime(str(cited_by_date)[:10], '%Y-%m-%d')
                if (datetime.now() - last).days < 30:
                    skip_cited_by = True
            except ValueError:
                pass
        if not skip_cited_by:
            existing_dois = _build_clippings_all_doi_set(md_dst.parent)
            count, citing_dois = get_cited_by_pubmed(main_doi, crossref_cache, existing_dois, cited_by_max)
            fm.pop('cited_by_count', None)
            fm['cited_by_date'] = datetime.now().strftime('%Y-%m-%d')
            if citing_dois:
                fm['cited_by'] = [f'[[{safe}|{display}]]'
                                  for display, safe in (process_doi(d) for d in citing_dois)]
    existing_refs = fm.get('reference', [])
    if existing_refs:
        fm['reference'] = process_existing_references(existing_refs)
    unique_dois = {doi.lower(): doi for doi in all_dois}
    if unique_dois:
        new_refs = []
        existing_dedup = _build_existing_dois(fm.get('reference', []))
        for doi_raw in unique_dois.values():
            display_doi, safe_filename = process_doi(doi_raw)
            if display_doi.lower() not in existing_dedup:
                new_refs.append(f'[[{safe_filename}|{display_doi}]]')
                existing_dedup.add(display_doi.lower())
        if new_refs:
            fm['reference'] = fm.get('reference', []) + new_refs
            print(f'已将{len(new_refs)}个唯一DOI添加到 {md_dst.name} 的reference')
    else:
        print(f'文件 {md_dst.name} 无有效DOI，跳过reference更新')
    if enable_api_refs:
        _, ref_section = _append_crossref_refs(fm, rest, main_doi, crossref_cache, md_dst.name)
        if ref_section:
            rest += ref_section
    if main_doi:
        refs = fm.get('reference', [])
        refs = [r for r in refs if not (r.startswith('[[') and r.endswith(']]') and '|' in r
                 and r[2:-2].split('|', 1)[1].strip().lower() == main_doi.lower())]
        refs.insert(0, f'[[{md_dst.stem}|{main_doi}]]')
        fm['reference'] = refs
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
                                    crossref_cache, enable_cited_by, cited_by_max, images_output)
                _mark_pdf_done(pdf_file_path)
        except Exception as e:
            print(f'处理失败: {e}')
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    print(f'批次 {batch_id} 处理完成！Markdown: {path_md0}，图片: {images_output}')


def run_pdf2md(path_pdf: str = None, path_zip: str = None, path_md0: str = None,
               enable_api_refs: bool = True, enable_cited_by: bool = True,
               cited_by_max: int = 10, token_path: str = None) -> None:
    if token_path is None:
        token_path = r'C:\ResearchFront\DATA\API\MinerU.txt'
    if path_pdf is None:
        path_pdf = r'C:\Vault\PDF'
    if path_zip is None:
        path_zip = r'C:\Vault\ZIP'
    if path_md0 is None:
        path_md0 = r'C:\Vault\Claude\MDfrPDF'

    token_content = read_text_file(Path(token_path))
    if not token_content:
        print('无法读取API Token')
        return
    token = token_content.strip()

    crossref_cache = load_cache()
    pp = Path(path_pdf)
    pz = Path(path_zip)
    pm = Path(path_md0)
    for p in [pp, pz, pm]:
        p.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(set(
        f.absolute() for ext in ['.pdf']
        for f in pp.rglob(f'*{ext}') if '完成' not in f.name
    ))
    trash_dir = pp.parent / 'TRASH'
    trash_dir.mkdir(exist_ok=True)
    filtered = []
    for pdf_file in pdf_files:
        done_path = pdf_file.parent / f'完成_{pdf_file.name}'
        if done_path.exists():
            print(f'已存在完成版本，移入TRASH: {pdf_file.name}')
            try:
                shutil.move(str(pdf_file), str(trash_dir / pdf_file.name))
            except Exception as e:
                print(f'移入TRASH失败: {e}')
        else:
            filtered.append(pdf_file)
    pdf_files = filtered
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
        batch_success = len(uploaded_files)
        total_success += batch_success
        print(f'批次 {batch_idx} 上传完成 | 成功：{batch_success}/{len(batch_files)}')

    print(f'所有批次上传完成！总成功：{total_success}/{len(pdf_files)}')
    if batch_ids:
        print('\n开始下载并处理结果...')
        for bid in batch_ids:
            download_and_process_batch(bid, pz, pm, token, pp, enable_api_refs,
                                       crossref_cache, enable_cited_by, cited_by_max,
                                       batch_file_map.get(bid, []))
    else:
        print('没有成功申请的批次，无需下载。')
    save_cache(crossref_cache)
