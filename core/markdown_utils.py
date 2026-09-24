import re
from core.doi import PATTERN_DOI

PATTERN_IMAGE = re.compile(r'!\[([^\]]*)\]\(([^)]*)\)', re.IGNORECASE)
PATTERN_WRONG_CLICKABLE_IMAGE = re.compile(
    r'\[\s*((?:!\[[^\]]*\]\([^)]+\)|!\([^)]+\))[^\]]*?)\]\s*\(([^)]+)\)',
    re.IGNORECASE
)
COMBINED_LINK_PATTERN = re.compile(
    r'(?P<clean>\s*(?<!!)(?<![\\])\[(?!!)(?:[^\]]*?)\]\((?:(?:[^)]*?(?:login|article|md5=|journal|author)[^)]*)|(?:\#.*?))\)\s*)'
    r'|(?P<link>\s*(?<!!)\[(?!!)(?P<text>[^\]]*)\]\((?P<url>[^)]+)\)\s*)',
    re.IGNORECASE | re.DOTALL
)
PATTERN_BRACKET_LINKS = re.compile(r'((?<!!)\[(?!!)[^\]]+\]\([^)]+\)|\[\[[^\]]+\]\])')
ARTIFACT_TAGS = re.compile(r'</?(?:lcel|nl)>', re.IGNORECASE)
H1_RE = re.compile(r'^#\s+(.+)$', re.MULTILINE)


def _fix_img(m: re.Match) -> str:
    alt, link = m.group(1), m.group(2).strip()
    link = f'https://{link[2:]}' if link.startswith('//') else link
    return f'![{alt}]({link})' if link.startswith(('images/', 'https://', 'C:/')) else f'!({link})'


def _fix_combined_link(m: re.Match) -> str:
    if m.lastgroup == 'clean':
        return m.group(0).replace('[', '(', 1).replace(']', ')', 1)
    text = m.group('text')
    doi_in_text = PATTERN_DOI.search(text)
    if doi_in_text:
        return f' {text} '
    doi_in_url = PATTERN_DOI.search(m.group('url'))
    return f' {doi_in_url.group(0)} ' if doi_in_url else m.group(0)


def _fix_bracket_link(m: re.Match) -> str:
    g = m.group(0)
    return g[1:-1] if g.startswith('[[') else g.replace('[', '(', 1).replace(']', ')', 1)


_PIPELINE = (
    (ARTIFACT_TAGS, ''),
    (PATTERN_IMAGE, _fix_img),
    (PATTERN_WRONG_CLICKABLE_IMAGE, r'\1(\2)'),
    (COMBINED_LINK_PATTERN, _fix_combined_link),
    (PATTERN_BRACKET_LINKS, _fix_bracket_link),
)


def clean_markdown_body(body: str) -> str:
    for pattern, repl in _PIPELINE:
        body = pattern.sub(repl, body)
    return body
