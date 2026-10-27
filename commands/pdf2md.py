import re
import shutil
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from core.cache import map_parallel
from core.title_cache import (load_doi_title_cache, lookup_doi_by_title,
                              put_doi_title, save_doi_title_cache,
                              verify_doi_title)
from core.web_services import (fetch_references, get_doi_from_citation,
                               load_cite_by_cache, refresh_cited_by,
                               save_cite_by_cache)
from core.doi import (find_plausible_dois, get_main_doi,
                       normalize_unicode_dashes, process_doi, repair_doi_text)
from core.frontmatter import (build_doi_set, dump_frontmatter,
                               parse_frontmatter_str)
from core.http import get_session
from core.markdown_utils import clean_markdown_body
from core.refs import (build_existing_dois, canonicalize_stem, new_doi_wikilinks,
                       pin_main_doi, process_existing_references)
from core import try_copy, iter_vault_dirs
from core.mineru import (MINERU_API_BASE, URL_PATTERN, IMAGES_PATH_PATTERN,
                         apply_upload_urls, download_zip, extract_json_data,
                         find_extracted_files, first_main_doi_from_json,
                         poll_batch_completion, replace_urls, upload_one)
from core.pdf_extractor import convert_pdf_to_md, extract_dois_from_pdf
from config import (CPU_CORES, DEFAULT_IMAGE_PATH, DEFAULT_MD_PATH, DEFAULT_PDF_PATH,
                    DEFAULT_ZIP_PATH, MINERU_TOKEN, OBSIDIAN_ROOT)

_http = get_session()


def _append_crossref_refs(fm, rest, main_doi, references, md_name):
    """合并Crossref参考文献进 fm['reference']；正文中无参考文献段时返回待追加的段落。"""
    if not main_doi or not references:
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


def _merge_new_dois(fm, all_dois, md_name):
    unique_dois = {doi.lower(): doi for doi in all_dois}
    if not unique_dois:
        print(f'文件 {md_name} 无有效DOI，跳过reference更新')
        return
    new_refs = new_doi_wikilinks(unique_dois.values(), build_existing_dois(fm.get('reference', [])))
    if new_refs:
        fm['reference'] = fm.get('reference', []) + new_refs
    print(f'已将{len(new_refs)}个唯一DOI添加到 {md_name} 的reference')


def _process_md_content(md_dst, json_src, pdf_path, enable_api_refs, doi_title_cache,
                        cite_by_cache, enable_cited_by=False, cited_by_max=10,
                        images_dir=None, clippings_doi_set=None, ref_max_age=15,
                        content=None):
    if content is None:
        if not md_dst.exists():
            return False
        try:
            content = normalize_unicode_dashes(md_dst.read_text(encoding='utf-8'))
        except Exception as e:
            print(f'读取MD文件失败 {md_dst}: {e}')
            return False

    dois_md = set(find_plausible_dois(repair_doi_text(content)))
    json_dois, urls = extract_json_data(json_src)
    if pdf_path:
        dois_pdf, pdf_first_doi = extract_dois_from_pdf(pdf_path, with_first=True)
    else:
        dois_pdf, pdf_first_doi = set(), None

    all_dois = dois_md | json_dois | dois_pdf
    if urls:
        content = replace_urls(content, urls)
    fm, rest = parse_frontmatter_str(content)
    title = fm.get('title') or md_dst.stem
    main_doi = source = None
    md_cand = None
    json_cand = None

    # 主DOI定级：缓存 → 缓存交叉验证(MD/JSON/PDF) → MD → JSON → PDF → API
    if (main_doi := lookup_doi_by_title(title, doi_title_cache)):
        source = '缓存'
    if main_doi is None:
        md_cand = get_main_doi(fm, content)
        json_cand = first_main_doi_from_json(json_src)
        for cand in (md_cand, json_cand, pdf_first_doi):
            if cand and verify_doi_title(cand, title, doi_title_cache):
                main_doi, source = cand, '缓存验证'
                break
    if main_doi is None and md_cand:
        main_doi, source = md_cand, 'MD'
    if main_doi is None and json_cand:
        main_doi, source = json_cand, 'JSON'
    if main_doi is None and pdf_first_doi:
        main_doi, source = pdf_first_doi, 'PDF'
    if main_doi is None and enable_api_refs:
        result = get_doi_from_citation(title, doi_title_cache)
        main_doi = process_doi(result[0])[0] if result else None
        source = result[2] if result else '未匹配'
    if main_doi:
        main_doi = process_doi(main_doi)[0]
        print(f'论文DOI来源: {source} | {main_doi}')
    if main_doi:
        fm['doi'] = main_doi
        put_doi_title(doi_title_cache, main_doi, title)

    if enable_cited_by and main_doi:
        if clippings_doi_set is None:
            clippings_doi_set = build_doi_set(md_dst.parent)
        refresh_cited_by(fm, main_doi, cite_by_cache, doi_title_cache,
                         clippings_doi_set, cited_by_max)

    if existing_refs := fm.get('reference', []):
        fm['reference'] = process_existing_references(existing_refs)

    year = fm.get('published')
    year = year if isinstance(year, int) else None
    refs = None
    if main_doi and year is None:
        refs, year = fetch_references(main_doi, doi_title_cache)
        if year:
            fm['published'] = year
    add_refs = year is None or datetime.now().year - year <= ref_max_age
    if add_refs:
        _merge_new_dois(fm, all_dois, md_dst.name)
        if enable_api_refs:
            if refs is None:
                refs, _ = fetch_references(main_doi, doi_title_cache)
            if ref_section := _append_crossref_refs(fm, rest, main_doi, refs, md_dst.name):
                rest += ref_section
    else:
        print(f'超{ref_max_age}年({year})，仅添加主DOI: {md_dst.name}')
    if main_doi:
        pin_main_doi(fm, main_doi, md_dst.stem)

    rest = clean_markdown_body(rest)
    if images_dir:
        rest = IMAGES_PATH_PATTERN.sub(f']({images_dir.resolve().as_posix()}/', rest)
    fm.pop('特殊引用数', None)
    try:
        md_dst.write_text(dump_frontmatter(fm, rest), encoding='utf-8')
    except Exception as e:
        print(f'更新MD文件失败 {md_dst}: {e}')
        return False
    return True


def _move_to_trash(p: Path, trash_dir: Path, label: str) -> None:
    try:
        shutil.move(str(p), str(trash_dir / p.name))
        print(f'    {label} → TRASH')
    except Exception as e:
        print(f'    {label}移入TRASH失败: {e}')


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
                     doi_title_cache, cite_by_cache, enable_cited_by, cited_by_max,
                     images_dir, clippings_doi_set, ref_max_age=15):
    pm = Path(path_md0)

    def _process_one(pdf_path, idx):
        print(f'[{idx}/{len(pdf_files)}] {pdf_path.name}')
        md_content = convert_pdf_to_md(pdf_path)
        if not md_content:
            print('  转换失败，跳过')
            return None
        md_dst = pm / f'{canonicalize_stem(pdf_path.stem)}.md'
        fm = {'pdf_path': str(pdf_path)}
        content = dump_frontmatter(fm, md_content)
        try:
            md_dst.write_text(content, encoding='utf-8')
        except Exception as e:
            print(f'  写入失败: {e}')
            return None
        success = _process_md_content(
            md_dst, None, pdf_path, enable_api_refs,
            doi_title_cache, cite_by_cache, enable_cited_by, cited_by_max,
            images_dir, clippings_doi_set, ref_max_age, content=content,
        )
        if success:
            _mark_pdf_done(pdf_path)
        return md_dst.name

    with ThreadPoolExecutor(max_workers=min(CPU_CORES, len(pdf_files))) as ex:
        futures = {ex.submit(_process_one, pf, i): pf for i, pf in enumerate(pdf_files, 1)}
        for fut in as_completed(futures):
            name = fut.result()
            if name:
                print(f'  完成 -> {name}')


def _process_downloaded_one(idx, f_info, path_zip, path_md0, name_to_path, path_pdf,
                            images_output, enable_api_refs, doi_title_cache, cite_by_cache,
                            enable_cited_by, cited_by_max, clippings_doi_set, ref_max_age):
    """单个 MinerU 结果：解压→移MD→拷图→补全引用→标记完成。各文件独立，供线程池并行。"""
    file_name = f_info['file_name']
    data_id = f_info['data_id']
    zip_path_ = path_zip / f'{data_id}.zip'
    if not zip_path_.exists():
        return
    print(f'[{idx}] 处理: {file_name}')
    temp_dir = path_zip / f'temp_{data_id}'
    temp_dir.mkdir(exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path_, 'r') as z:
            z.extractall(temp_dir)
        md_src, img_src, json_src = find_extracted_files(temp_dir)
        md_dst = None
        if md_src:
            md_dst = path_md0 / f'{canonicalize_stem(Path(file_name).stem)}.md'
            shutil.move(str(md_src), str(md_dst))
        if img_src:
            for img_file in img_src.glob('*'):
                dst_img = images_output / img_file.name
                if not dst_img.exists() and try_copy(img_file, dst_img):
                    continue  # 硬链接优先（免整图拷贝），目标已存在或失败回退 copy2（保留覆盖语义）
                try:
                    shutil.copy2(img_file, dst_img)
                except Exception:
                    pass
        if md_dst:
            pdf_file_path = name_to_path.get(file_name, path_pdf / file_name)
            if _process_md_content(md_dst, json_src, pdf_file_path, enable_api_refs,
                                   doi_title_cache, cite_by_cache, enable_cited_by,
                                   cited_by_max, images_output, clippings_doi_set,
                                   ref_max_age):
                _mark_pdf_done(pdf_file_path)
    except Exception as e:
        print(f'处理失败: {e}')
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def download_and_process_batch(batch_id, path_zip, path_md0, token, path_pdf,
                               enable_api_refs, doi_title_cache, cite_by_cache,
                               enable_cited_by=False, cited_by_max=10, batch_files=None,
                               images_output=None, ref_max_age=15,
                               clippings_doi_set=None):
    name_to_path = {Path(f).name: Path(f) for f in (batch_files or [])}
    images_output = images_output or DEFAULT_IMAGE_PATH
    images_output.mkdir(exist_ok=True)
    files = poll_batch_completion(batch_id, token, expected_count=len(batch_files or []))
    if files is None:
        return
    print(f'批次 {batch_id} 找到 {len(files)} 个文件，所有文件已处理完成')
    download_tasks = [
        (f_info['full_zip_url'], path_zip / f"{f_info['data_id']}.zip",
         f_info['file_name'], idx)
        for idx, f_info in enumerate(files, 1)
    ]
    with ThreadPoolExecutor(max_workers=min(CPU_CORES * 2, 5)) as executor:
        futures = {executor.submit(download_zip, *task): task[3] for task in download_tasks}
        for future in as_completed(futures):
            future.result()

    with ThreadPoolExecutor(max_workers=min(CPU_CORES * 2, 4)) as ex:
        futures = [
            ex.submit(_process_downloaded_one, idx, f_info, path_zip, path_md0,
                      name_to_path, path_pdf, images_output, enable_api_refs,
                      doi_title_cache, cite_by_cache, enable_cited_by, cited_by_max,
                      clippings_doi_set, ref_max_age)
            for idx, f_info in enumerate(files, 1)
        ]
        for fut in futures:
            fut.result()
    print(f'批次 {batch_id} 处理完成！Markdown: {path_md0}，图片: {images_output}')


def run_pdf2md(path_pdf: str = None, path_zip: str = None, path_md0: str = None,
               enable_api_refs: bool = True, enable_cited_by: bool = True,
               cited_by_max: int = 10, token_path: str = None,
               local: bool = False, path_images: str = None,
               ref_max_age: int = 15) -> None:
    token_path = token_path or MINERU_TOKEN
    path_pdf = path_pdf or DEFAULT_PDF_PATH
    path_zip = path_zip or DEFAULT_ZIP_PATH
    path_md0 = path_md0 or DEFAULT_MD_PATH

    doi_title_cache = load_doi_title_cache()
    cite_by_cache = load_cite_by_cache()
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
    global_index = {}
    clip_dirs = [c for v in iter_vault_dirs(OBSIDIAN_ROOT) if (c := v / 'Clippings').is_dir()]
    for mds in map_parallel(lambda c: list(c.rglob('*.md')), clip_dirs):  # 各 vault Clippings 并行 rglob
        for md in mds:
            global_index.setdefault(md.stem, md)
    print(f'全库已索引: {len(global_index)} 个MD')
    for pdf_file in pdf_files:
        done_path = pdf_file.parent / f'完成_{pdf_file.name}'
        if not done_path.exists():
            filtered.append(pdf_file)
            continue
        md_path = global_index.get(pdf_file.stem)
        if not (md_path and md_path.exists()):
            print(f'[B] 无MD记录: {pdf_file.name}  重处理中')
            filtered.append(pdf_file)
            _move_to_trash(done_path, trash_dir, '完成标记')
            continue
        print(f'[A] 已完成: {pdf_file.name}')
        if md_path.resolve() == (pm / f'{pdf_file.stem}.md').resolve():
            print(f'    MD已就位: {md_path}')
        else:
            print(f'    发现跨vault MD: {md_path.parent.parent.parent.name}')
            dst = pm / f'{pdf_file.stem}.md'
            print(f'    硬链接成功: {dst.name}' if try_copy(md_path, dst) else '    硬链接失败(目标已存在)')
        _move_to_trash(pdf_file, trash_dir, 'PDF')
    pdf_files = filtered
    if not pdf_files:
        print('未找到需处理PDF')
        return

    print(f'共发现 {len(pdf_files)} 个PDF待处理')

    # 全库 DOI 集合一次构建，local/各批次共享（原实现每个批次重复扫描，重复磁盘 I/O）
    clippings_doi_set = build_doi_set(pm) if enable_cited_by else None

    if local:
        _run_local_batch(pdf_files, path_md0, enable_api_refs,
                        doi_title_cache, cite_by_cache, enable_cited_by, cited_by_max,
                        images_dir, clippings_doi_set, ref_max_age)
        save_doi_title_cache(doi_title_cache)
        save_cite_by_cache(cite_by_cache)
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
    url = f'{MINERU_API_BASE}/file-urls/batch'
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

        with ThreadPoolExecutor(max_workers=min(CPU_CORES * 2, 5)) as ex:
            uploaded_files = [f for f in ex.map(upload_one, batch_files, url_result['upload_urls']) if f]
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
                                   doi_title_cache, cite_by_cache, enable_cited_by,
                                   cited_by_max, batch_file_map.get(bid, []),
                                   images_output=images_dir, ref_max_age=ref_max_age,
                                   clippings_doi_set=clippings_doi_set)
    save_doi_title_cache(doi_title_cache)
    save_cite_by_cache(cite_by_cache)
