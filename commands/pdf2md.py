"""/s: MinerU PDF batch-to-Markdown pipeline with DOI / Crossref / PubMed enrichment."""

import json
import os
import re
import shutil
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests

from core.crossref_api import (fetch_references, get_doi_from_citation,
                               get_cited_by_pubmed, get_issued_year,
                               load_cache, save_cache)
from core.doi import (PATTERN_DOI, find_plausible_dois, get_main_doi, make_wikilink,
                       normalize_unicode_dashes, process_doi, repair_doi_text)
from core.frontmatter import (build_doi_set, cited_by_fresh, dump_frontmatter,
                               parse_frontmatter_str)
from core.markdown_utils import clean_markdown_body
from core.refs import build_existing_dois, canonicalize_stem, new_doi_wikilinks, process_existing_references
from core import try_copy, is_vault_dir
from core.pdf_extractor import convert_pdf_to_md, extract_dois_from_pdf
from config import (DEFAULT_IMAGE_PATH, DEFAULT_MD_PATH, DEFAULT_PDF_PATH,
                    DEFAULT_ZIP_PATH, MINERU_TOKEN, OBSIDIAN_ROOT)


URL_PATTERN = re.compile(
    r'https?://[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)',
    re.IGNORECASE
)


def _build_clippings_index(vault_root: Path) -> dict:
    index = {}
    for vault_dir in sorted(vault_root.iterdir()):
        if not is_vault_dir(vault_dir):
            continue
        clips = vault_dir / 'Clippings'
        if not clips.is_dir():
            continue
        for md in clips.rglob('*.md'):
            if md.stem not in index:
                index[md.stem] = md
    return index


def extract_text(obj):
    stack = [obj]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            content = item.get('content')
            if isinstance(content, str):
                yield content
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, str):
            yield item


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


def _append_crossref_refs(fm, rest, main_doi, crossref_cache, md_name):
    """拉取Crossref参考文献合并进 fm['reference']；正文中无参考文献段时返回待追加的段落。"""
    if not main_doi:
        return None
    references = fetch_references(main_doi, crossref_cache)
    if not references:
        return None
    ref_dois = new_doi_wikilinks((r['doi'] for r in references if r['doi']),
                                 build_existing_dois(fm.get('reference', [])))
    if ref_dois:
        fm['reference'] = fm.get('reference', []) + ref_dois
    if '## 参考文献' in rest:
        return None
    lines = [f'{i}. {r.get("text","")}{" DOI: "+r.get("doi","") if r.get("doi") else ""}'
             for i, r in enumerate(references, 1) if r.get('text') or r.get('doi')]
    if not lines:
        return None
    print(f'已将 {len(references)} 条参考文献添加到 {md_name}')
    return '\n\n## 参考文献\n' + '\n'.join(lines)


def _extract_json_data(json_src):
    if not (json_src and json_src.exists()):
        return set(), []
    try:
        content_data = json.loads(json_src.read_text(encoding='utf-8'))
    except Exception as e:
        print(f'读取/解析JSON失败 {json_src}: {e}')
        return set(), []
    dois = set()
    urls = []
    try:
        for page in content_data:
            for block in page:
                for text in extract_text(block):
                    text = normalize_unicode_dashes(text)
                    dois.update(find_plausible_dois(repair_doi_text(text)))
                    urls.extend(URL_PATTERN.findall(text))
    except Exception as e:
        print(f'解析 JSON 内容时出错 {json_src}: {e}')
    return dois, urls


def _replace_urls(content, urls):
    if not urls:
        return content
    unique_urls = sorted(set(urls), key=len, reverse=True)
    escaped = '|'.join(re.escape(u) for u in unique_urls)
    return re.sub(
        rf'(?<!\]\()({escaped})',
        r'[\1](sslocal://flow/file_open?url=%5C1&flow_extra=eyJsaW5rX3R5cGUiOiJjb2RlX2ludGVycHJldGVyIn0=)',
        content
    )



def _update_cited_by(fm, main_doi, crossref_cache, cited_by_max, clippings_doi_set):
    if cited_by_fresh(fm):
        return
    count, citing_dois = get_cited_by_pubmed(main_doi, crossref_cache, clippings_doi_set, cited_by_max)
    fm.pop('cited_by_count', None)
    fm['cited_by_date'] = datetime.now().strftime('%Y-%m-%d')
    if citing_dois:
        fm['cited_by'] = [make_wikilink(process_doi(d)[0]) for d in citing_dois]


def _merge_new_dois(fm, all_dois, md_name):
    unique_dois = {doi.lower(): doi for doi in all_dois}
    if not unique_dois:
        print(f'文件 {md_name} 无有效DOI，跳过reference更新')
        return
    new_refs = new_doi_wikilinks(unique_dois.values(), build_existing_dois(fm.get('reference', [])))
    if new_refs:
        fm['reference'] = fm.get('reference', []) + new_refs
        print(f'已将{len(new_refs)}个唯一DOI添加到 {md_name} 的reference')


def _pin_main_doi(fm, main_doi, md_stem):
    lower = main_doi.lower()
    refs = [r for r in fm.get('reference', [])
            if not (r.startswith('[[') and r.endswith(']]') and '|' in r
                    and r[2:-2].split('|', 1)[1].strip().lower() == lower)]
    refs.insert(0, f'[[{md_stem}|{main_doi}]]')
    fm['reference'] = refs


def _process_md_content(md_dst, json_src, pdf_path, enable_api_refs, crossref_cache,
                        enable_cited_by=False, cited_by_max=10, images_dir=None,
                        clippings_doi_set=None, ref_max_age=15):
    if not md_dst.exists():
        return False
    try:
        content = normalize_unicode_dashes(md_dst.read_text(encoding='utf-8'))
    except Exception as e:
        print(f'读取MD文件失败 {md_dst}: {e}')
        return False

    dois_md = set(find_plausible_dois(repair_doi_text(content)))
    json_dois, urls = _extract_json_data(json_src)
    dois_pdf = extract_dois_from_pdf(pdf_path) if pdf_path else set()

    all_dois = dois_md | json_dois | dois_pdf
    if urls:
        content = _replace_urls(content, urls)
    fm, rest = parse_frontmatter_str(content)
    main_doi = get_main_doi(fm, content, all_dois)

    if main_doi is None and enable_api_refs and not all_dois:
        result = get_doi_from_citation(fm.get('title', md_dst.stem), crossref_cache)
        main_doi = process_doi(result[0])[0] if result else None
        print(f'Crossref标题回退{"确认主DOI" if result else "无结果"}: {fm.get("title", md_dst.stem)}')

    if enable_cited_by and main_doi:
        if clippings_doi_set is None:
            clippings_doi_set = build_doi_set(md_dst.parent)
        _update_cited_by(fm, main_doi, crossref_cache, cited_by_max, clippings_doi_set)

    existing_refs = fm.get('reference', [])
    if existing_refs:
        fm['reference'] = process_existing_references(existing_refs)

    year = get_issued_year(main_doi, crossref_cache) if main_doi else None
    add_refs = year is None or datetime.now().year - year <= ref_max_age
    if not add_refs:
        print(f'超{ref_max_age}年({year})，仅添加主DOI: {md_dst.name}')

    if add_refs:
        _merge_new_dois(fm, all_dois, md_dst.name)
        if enable_api_refs:
            ref_section = _append_crossref_refs(fm, rest, main_doi, crossref_cache, md_dst.name)
            if ref_section:
                rest += ref_section
    if main_doi:
        _pin_main_doi(fm, main_doi, md_dst.stem)

    rest = clean_markdown_body(rest)
    if images_dir:
        rest = re.sub(r'\]\(images/', f']({images_dir.resolve().as_posix()}/', rest)
    fm.pop('特殊引用数', None)
    try:
        md_dst.write_text(dump_frontmatter(fm, rest), encoding='utf-8')
    except Exception as e:
        print(f'更新MD文件失败 {md_dst}: {e}')
        return False
    return True


def _download_zip(zip_url, zip_path, file_name, idx):
    if zip_path.exists():
        print(f'[{idx}] ZIP已存在: {file_name}')
        return idx, True
    print(f'[{idx}] 下载: {file_name}')
    try:
        r = requests.get(zip_url, stream=True, timeout=120)
        r.raise_for_status()
        zip_path.write_bytes(r.content)
        return idx, True
    except Exception as e:
        print(f'[{idx}] 下载失败: {e}')
        return idx, False


def _poll_batch_completion(batch_id, token, max_wait=1800, expected_count=None):
    url = f'https://mineru.net/api/v4/extract-results/batch/{batch_id}'
    headers = {'Authorization': f'Bearer {token}'}
    start = time.time()
    while time.time() - start < max_wait:
        try:
            resp = requests.get(url, headers=headers, timeout=30)
        except Exception:
            seconds = time.time() - start
            print(f'查询请求异常({seconds:.0f}s)，等待重试')
            time.sleep(10)
            continue
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
        done = [f for f in files if f['state'] == 'done']
        failed = sum(1 for f in files if f['state'] == 'failed')
        target = expected_count or len(files)
        print(f'完成: {len(done)}/{len(files)}  失败: {failed}  目标: {target}')
        if len(done) + failed >= target:
            return done
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



def _mark_pdf_done(pdf_file_path: Path, trash_dir: Path = None):
    time.sleep(0.5)
    try:
        pdf_file_path.rename(pdf_file_path.parent / f'完成_{pdf_file_path.name}')
    except Exception:
        if trash_dir is None:
            trash_dir = pdf_file_path.parent.parent / 'TRASH'
        trash_dir.mkdir(exist_ok=True)
        shutil.move(str(pdf_file_path), str(trash_dir / pdf_file_path.name))


def _run_local_batch(pdf_files, path_md0, enable_api_refs,
                     crossref_cache, enable_cited_by, cited_by_max,
                     images_dir, clippings_doi_set, ref_max_age=15):
    pm = Path(path_md0)
    cache_lock = threading.Lock()

    def _process_one(pdf_path, idx):
        print(f'[{idx}/{len(pdf_files)}] {pdf_path.name}')
        md_content = convert_pdf_to_md(pdf_path)
        if not md_content:
            print('  转换失败，跳过')
            return None
        md_dst = pm / f'{canonicalize_stem(pdf_path.stem)}.md'
        fm = {'title': pdf_path.stem, 'pdf_path': str(pdf_path)}
        try:
            md_dst.write_text(dump_frontmatter(fm, md_content), encoding='utf-8')
        except Exception as e:
            print(f'  写入失败: {e}')
            return None
        with cache_lock:
            success = _process_md_content(
                md_dst, None, pdf_path, enable_api_refs,
                crossref_cache, enable_cited_by, cited_by_max,
                images_dir, clippings_doi_set, ref_max_age,
            )
        if success:
            _mark_pdf_done(pdf_path)
        return md_dst.name

    with ThreadPoolExecutor(max_workers=min(4, len(pdf_files))) as ex:
        futures = {ex.submit(_process_one, pf, i): pf for i, pf in enumerate(pdf_files, 1)}
        for fut in as_completed(futures):
            name = fut.result()
            if name:
                print(f'  完成 -> {name}')


def download_and_process_batch(batch_id, path_zip, path_md0, token, path_pdf,
                               enable_api_refs, crossref_cache, enable_cited_by=False,
                               cited_by_max=10, batch_files=None, images_output=None,
                               ref_max_age=15):
    name_to_path = {Path(f).name: Path(f) for f in (batch_files or [])}
    images_output = images_output or DEFAULT_IMAGE_PATH
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

    clippings_doi_set = build_doi_set(path_md0) if enable_cited_by else None
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
                md_dst = path_md0 / f'{canonicalize_stem(Path(file_name).stem)}.md'
                shutil.move(str(md_src), str(md_dst))
            if img_src:
                for img_file in img_src.glob('*'):
                    try:
                        shutil.copy2(img_file, images_output / img_file.name)
                    except Exception:
                        pass
            if md_dst:
                pdf_file_path = name_to_path.get(file_name, path_pdf / file_name)
                if _process_md_content(md_dst, json_src, pdf_file_path, enable_api_refs,
                                       crossref_cache, enable_cited_by, cited_by_max,
                                       images_output, clippings_doi_set, ref_max_age):
                    _mark_pdf_done(pdf_file_path)
        except Exception as e:
            print(f'处理失败: {e}')
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    print(f'批次 {batch_id} 处理完成！Markdown: {path_md0}，图片: {images_output}')


def _upload_one(f, u):
    try:
        with open(f, 'rb') as fh:
            r = requests.put(u, data=fh, timeout=60)
        # 用 with 确保上传后立即关闭文件句柄，避免占用导致后续标记完成失败
        if r.status_code == 200:
            return f
        print(f'上传失败：{f} | 状态码：{r.status_code}')
    except Exception as e:
        print(f'上传异常：{f} | 错误：{e}')
    return None


def run_pdf2md(path_pdf: str = None, path_zip: str = None, path_md0: str = None,
               enable_api_refs: bool = True, enable_cited_by: bool = True,
               cited_by_max: int = 10, token_path: str = None,
               local: bool = False, path_images: str = None,
               ref_max_age: int = 15) -> None:
    token_path = token_path or MINERU_TOKEN
    path_pdf = path_pdf or DEFAULT_PDF_PATH
    path_zip = path_zip or DEFAULT_ZIP_PATH
    path_md0 = path_md0 or DEFAULT_MD_PATH

    crossref_cache = load_cache()
    pp = Path(path_pdf)
    pm = Path(path_md0)
    for p in (pp, pm):
        p.mkdir(parents=True, exist_ok=True)

    images_dir = Path(path_images) if path_images else DEFAULT_IMAGE_PATH
    images_dir.mkdir(exist_ok=True)
    trash_dir = pp.parent / 'TRASH'
    trash_dir.mkdir(exist_ok=True)

    pdf_files = sorted({f.absolute() for f in pp.rglob('*.pdf') if '完成' not in f.name})
    filtered = []
    global_index = _build_clippings_index(OBSIDIAN_ROOT)
    print(f'全库已索引: {len(global_index)} 个MD')
    for pdf_file in pdf_files:
        done_path = pdf_file.parent / f'完成_{pdf_file.name}'
        if not done_path.exists():
            filtered.append(pdf_file)
            continue
        md_path = global_index.get(pdf_file.stem)
        if md_path and md_path.exists():
            print(f'[A] 已完成: {pdf_file.name}')
            if md_path.resolve() == (pm / f'{pdf_file.stem}.md').resolve():
                print(f'    MD已就位: {md_path}')
            else:
                print(f'    发现跨vault MD: {md_path.parent.parent.parent.name}')
                dst = pm / f'{pdf_file.stem}.md'
                if try_copy(md_path, dst):
                    print(f'    硬链接成功: {dst.name}')
                else:
                    print(f'    硬链接失败(目标已存在)')
            try:
                shutil.move(str(pdf_file), str(trash_dir / pdf_file.name))
                print(f'    PDF → TRASH')
            except Exception as e:
                print(f'    PDF移入TRASH失败: {e}')
        else:
            print(f'[B] 无MD记录: {pdf_file.name}  重处理中')
            filtered.append(pdf_file)
            try:
                shutil.move(str(done_path), str(trash_dir / done_path.name))
                print(f'    完成标记 → TRASH')
            except Exception as e:
                print(f'    完成标记移入TRASH失败: {e}')
    pdf_files = filtered
    if not pdf_files:
        print('未找到需处理PDF')
        return

    print(f'共发现 {len(pdf_files)} 个PDF待处理')

    if local:
        clippings_doi_set = build_doi_set(pm) if enable_cited_by else None
        _run_local_batch(pdf_files, path_md0, enable_api_refs,
                        crossref_cache, enable_cited_by, cited_by_max,
                        images_dir, clippings_doi_set, ref_max_age)
        save_cache(crossref_cache)
        print(f'\n全部完成！共处理 {len(pdf_files)} 个PDF，输出到 {pm}')
        return

    try:
        token = Path(token_path).read_text(encoding='utf-8').strip()
    except Exception as e:
        print(f'无法读取API Token: {e}')
        return

    pz = Path(path_zip)
    pz.mkdir(parents=True, exist_ok=True)

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

        with ThreadPoolExecutor(max_workers=5) as ex:
            uploaded_files = [f for f in ex.map(_upload_one, batch_files, url_result['upload_urls']) if f]
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
                                   batch_file_map.get(bid, []), images_output=images_dir,
                                   ref_max_age=ref_max_age)
    save_cache(crossref_cache)
