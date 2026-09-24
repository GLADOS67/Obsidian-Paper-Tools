import random
import time

import requests

from config import USER_AGENT

_session = None


def get_session() -> requests.Session:
    """模块级单例会话（连接池复用，线程内安全发送）。"""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({'User-Agent': USER_AGENT})
    return _session


def polite_sleep(lo: float = 1.0, hi: float = 2.0) -> None:
    """API 礼貌随机延迟，避免高频请求被封。"""
    time.sleep(random.uniform(lo, hi))
