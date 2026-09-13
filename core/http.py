"""/s: Shared HTTP session with retry and rate-limit for Crossref API / PubMed E-utilities."""

import requests

from config import USER_AGENT


def make_session() -> requests.Session:
    """创建带统一 User-Agent 的共享会话（连接池复用，线程内安全发送）。"""
    session = requests.Session()
    session.headers.update({'User-Agent': USER_AGENT})
    return session
