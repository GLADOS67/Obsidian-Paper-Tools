"""/s: Global path constants: MinerU token, Crossref cache, Obsidian Vault."""

from pathlib import Path

MINERU_TOKEN = Path(r'C:\ResearchFront\DATA\API\MinerU.txt')
OBSIDIAN_ROOT = Path(r'C:\Vault')
DEFAULT_PDF_PATH = Path(r'C:\Vault\PDF')
DEFAULT_ZIP_PATH = Path(r'C:\Vault\ZIP')
DEFAULT_MD_PATH = Path(r'C:\Vault\PENDING\Clippings')
DEFAULT_IMAGE_PATH = Path(r'C:\Vault\IMAGE')
CROSSREF_CACHE = Path(r'D:\ResearchFront\DATA\API\crossref_cache.json')  # 【勿改】强制硬编码路径
CROSSREF_MAILTO = 'lik1453529@wmu.edu.cn'
