"""MinerU v4 API 客户端 + content_list_v2.json 产物解析层。

线上服务层：
  - 申请上传链接（apply_upload_urls）→ PUT 上传（upload_one）
  - 轮询批次提取结果（poll_batch_completion）→ 下载结果 zip（download_zip）
  - 解压产物定位（find_extracted_files）
  - content_list_v2.json 解析：DOI/URL 收集（extract_json_data）、主DOI定级（first_main_doi_from_json）
"""

import json
import os
import re
import time
import zipfile
from functools import lru_cache
from itertools import chain
from pathlib import Path

from requests.exceptions import JSONDecodeError

from core.doi import find_plausible_dois, normalize_unicode_dashes
from core.http import get_session

MINERU_API_BASE = 'https://mineru.net/api/v4'

_http = get_session()

URL_PATTERN = re.compile(
    r'https?://[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)',
    re.IGNORECASE
)
IMAGES_PATH_PATTERN = re.compile(r'\]\(images/')


@lru_cache(maxsize=256)
def _parse_content_json(json_key: str):
    """按路径缓存 JSON 解析结果：pdf2md 对同一 content_list_v2.json 的
    extract_json_data + first_main_doi_from_json 双调用免二次读盘/解码（大文件可达数 MB）。
    解析失败不缓存（调用方各自捕获并打印，与原始错误语义一致）。"""
    return json.loads(Path(json_key).read_text(encoding='utf-8'))


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
        response = _http.post(url, headers=headers, json=data, timeout=30)
        status = response.status_code
        result = response.json()
    except JSONDecodeError:
        return {'success': False, 'error': f'JSON解析失败 (HTTP {status})'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    if not isinstance(result, dict):
        return {'success': False, 'error': 'API返回类型异常'}
    if result.get('code') != 0:
        return {'success': False, 'error': result.get('msg', '未知错误')}
    return {'success': True, 'batch_id': result['data']['batch_id'],
            'upload_urls': result['data']['file_urls']}


# ── content_list_v2.json 解析 ──────────────────────────────────

def extract_json_data(json_src):
    if not (json_src and json_src.exists()):
        return set(), []
    try:
        content_data = _parse_content_json(str(json_src))
    except Exception as e:
        print(f'读取/解析JSON失败 {json_src}: {e}')
        return set(), []
    dois = set()
    urls = []
    try:
        blocks = (block for page in content_data for block in page)
        for text in chain.from_iterable(extract_text(b) for b in blocks):
            text = normalize_unicode_dashes(text)
            dois.update(find_plausible_dois(text))
            urls.extend(URL_PATTERN.findall(text))
    except Exception as e:
        print(f'解析 JSON 内容时出错 {json_src}: {e}')
    return dois, urls


_MAIN_DOI_BLOCK_TYPES = ('page_footnote', 'page_header', 'page_footer')
_FRONT_BLOCK_TYPES = ('paragraph', 'title')
_FRONT_BLOCK_LIMIT = 30


def first_main_doi_from_json(json_src):
    """JSON 路主DOI候选：块类型加权（页脚注/页眉含 DOI 元数据 → 首页前部段落/标题），
    list 块（参考文献，实测占 DOI 出现 85%+）永远排除。
    仅遍历 content 子树、逐文本项提取（JSON 结构化文本无断行，不需 repair 拼接）。"""
    if not (json_src and json_src.exists()):
        return None
    try:
        content_data = _parse_content_json(str(json_src))
    except Exception as e:
        print(f'读取/解析JSON失败 {json_src}: {e}')
        return None
    if not isinstance(content_data, list):
        return None

    def _first_doi(block):
        content = block.get('content') if isinstance(block, dict) else None
        if content is None:
            return '', None
        texts = [t for t in extract_text(content) if isinstance(t, str) and t.strip()]
        if not texts:
            return '', None
        for t in texts:
            if d := find_plausible_dois(t):
                return t, d[0]
        return ' '.join(texts), None

    try:
        for page in content_data:
            if not isinstance(page, list):
                continue
            for block in page:
                if not isinstance(block, dict) or block.get('type') not in _MAIN_DOI_BLOCK_TYPES:
                    continue
                text, d = _first_doi(block)
                if d and 'doi' in text.lower():
                    return d
        if content_data and isinstance(content_data[0], list):
            for block in content_data[0][:_FRONT_BLOCK_LIMIT]:
                if not isinstance(block, dict) or block.get('type') not in _FRONT_BLOCK_TYPES:
                    continue
                text, d = _first_doi(block)
                if d and 'doi' in text.lower():
                    return d
    except Exception as e:
        print(f'解析JSON主DOI失败 {json_src}: {e}')
    return None


def replace_urls(content, urls):
    if not urls:
        return content
    unique_urls = sorted(set(urls), key=len, reverse=True)
    escaped = '|'.join(re.escape(u) for u in unique_urls)
    return re.sub(
        rf'(?<!\]\()({escaped})',
        r'[\1](sslocal://flow/file_open?url=%5C1&flow_extra=eyJsaW5rX3R5cGUiOiJjb2RlX2ludGVycHJldGVyIn0=)',
        content
    )


# ── 上传/轮询/下载/解压 ─────────────────────────────────────────

def download_zip(zip_url, zip_path, file_name, idx):
    if zip_path.exists():
        print(f'[{idx}] ZIP已存在: {file_name}')
        return idx, True
    print(f'[{idx}] 下载: {file_name}')
    try:
        r = _http.get(zip_url, stream=True, timeout=120)
        r.raise_for_status()
        with open(zip_path, 'wb') as fh:  # 流式写盘，避免整包常驻内存
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
        return idx, True
    except Exception as e:
        print(f'[{idx}] 下载失败: {e}')
        return idx, False


def poll_batch_completion(batch_id, token, max_wait=1800, expected_count=None):
    url = f'{MINERU_API_BASE}/extract-results/batch/{batch_id}'
    headers = {'Authorization': f'Bearer {token}'}
    start = time.time()
    files = []
    while time.time() - start < max_wait:
        try:
            resp = _http.get(url, headers=headers, timeout=30)
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


def find_extracted_files(temp_dir):
    md_src = img_src = json_src = None
    for root, dirs, files_in_dir in os.walk(temp_dir):
        if not md_src and 'full.md' in files_in_dir:
            md_src = Path(root) / 'full.md'
        if not img_src and 'images' in dirs:
            img_src = Path(root) / 'images'
        if not json_src:
            for f in files_in_dir:
                if f.endswith('content_list_v2.json'):
                    json_src = Path(root) / f
                    break
        if md_src and img_src and json_src:
            break
    return md_src, img_src, json_src


def upload_one(f, u):
    try:
        with open(f, 'rb') as fh:
            r = _http.put(u, data=fh, timeout=60)
        # 用 with 确保上传后立即关闭文件句柄，避免占用导致后续标记完成失败
        if r.status_code == 200:
            return f
        print(f'上传失败：{f} | 状态码：{r.status_code}')
    except Exception as e:
        print(f'上传异常：{f} | 错误：{e}')
    return None
