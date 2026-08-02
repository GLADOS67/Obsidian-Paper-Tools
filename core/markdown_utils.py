"""/s: Obsidian markdown body cleaner — fixes image links, strips artifact tags (<lcel>, <nl>),
normalizes bracket-link syntax for wikilink-based citation graphs.
"""
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


def clean_markdown_body(body: str) -> str:
    def fix_img(m: re.Match) -> str:
        alt, link = m.group(1), m.group(2).strip()
        link = f'https://{link[2:]}' if link.startswith('//') else link
        is_local = link.startswith(('images/', 'https://', 'C:/'))
        return f'![{alt}]({link})' if is_local else f'!({link})'

    def handle_combined_link(m: re.Match) -> str:
        if m.lastgroup == 'clean':
            return m.group(0).replace('[', '(', 1).replace(']', ')', 1)
        doi_in_text = PATTERN_DOI.search(m.group('text'))
        if doi_in_text:
            return f' {m.group("text")} '
        doi_in_url = PATTERN_DOI.search(m.group('url'))
        return f' {doi_in_url.group(0)} ' if doi_in_url else m.group(0)

    def handle_bracket_link(m: re.Match) -> str:
        g = m.group(0)
        return g[1:-1] if g.startswith('[[') else g.replace('[', '(', 1).replace(']', ')', 1)

    body = ARTIFACT_TAGS.sub('', body)
    body = PATTERN_IMAGE.sub(fix_img, body)
    body = PATTERN_WRONG_CLICKABLE_IMAGE.sub(r'\1(\2)', body)
    body = COMBINED_LINK_PATTERN.sub(handle_combined_link, body)
    body = PATTERN_BRACKET_LINKS.sub(handle_bracket_link, body)
    return body
