"""/s: Global path & API token configuration for Obsidian-Paper-Tools.
- MinerU API (mineru.net): Cloud PDF-to-Markdown extraction with formula & table detection.
- Crossref API (api.crossref.org): DOI metadata, reference lists, citation text → DOI resolution.
- PubMed E-utilities (eutils.ncbi.nlm.nih.gov): Cited-by lookup via pubmed_pubmed_citedin.
- IMAGE: Centralized image store scanned by clean_images for garbage collection.
"""
from pathlib import Path

CROSSREF_CACHE = Path(r'D:\ResearchFront\DATA\API\crossref_cache.json')
MINERU_TOKEN = Path(r'C:\ResearchFront\DATA\API\MinerU.txt')
OBSIDIAN_ROOT = Path(r'C:\Vault')
DEFAULT_PDF_PATH = Path(r'C:\Vault\PDF')
DEFAULT_ZIP_PATH = Path(r'C:\Vault\ZIP')
DEFAULT_MD_PATH = Path(r'C:\Vault\PENDING\Clippings')
DEFAULT_IMAGE_PATH = Path(r'C:\Vault\IMAGE')
