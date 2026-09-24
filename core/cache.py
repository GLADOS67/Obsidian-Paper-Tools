"""通用 JSON 缓存与文本读取工具（跨模块共享的公共 IO 逻辑）。"""

import json
from pathlib import Path

_ENC_AUTO = ('utf-8', 'gbk')


def load_cache(path: Path) -> dict:
    """读取 JSON 缓存文件，异常或非 dict 返回空 dict。"""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_cache(path: Path, cache: dict) -> None:
    """写 JSON 缓存（确保父目录存在），异常静默。"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass


def read_text_auto(path: Path) -> str:
    """依次尝试 utf-8/gbk 解码（去 BOM），全部失败用 utf-8 替换错误字符。"""
    data = Path(path).read_bytes()
    for enc in _ENC_AUTO:
        try:
            return data.decode(enc).lstrip('\ufeff')
        except UnicodeDecodeError:
            continue
    return data.decode('utf-8', errors='replace')


def read_text_safe(path: Path, encoding: str = 'utf-8') -> str:
    """读取文本，任何异常返回空串（与空文件统一为空串语义）。"""
    try:
        return Path(path).read_text(encoding=encoding)
    except Exception:
        return ''
