![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue) ![License](https://img.shields.io/badge/license-MIT-green)

**Author:** Li Kan <lik1453529@163.com>

---

# Obsidian-Paper-Tools 3.4 — 织命者卡洛斯

> Obsidian. Our Vault. 🔗 Links. 🧠 Graph. 📂 Open formats.
> Our way of research.
>
> But knowledge doesn't organize itself.
>
> (📄😨💥 Scattered PDFs... 📑 duplicate DOIs... 🔗💔 broken citations...)
> (😨🧎 No... Sweet bibliography... NOOOOO)
>
> *INVASION*
>
> (🕺 haha) Look familiar?
> Scenes like these are happening in every researcher's Vault, right now! 🤷‍♂️
>
> 👉 You 👉 could 👉 be 👉 next.
>
> That is — unless you make the most important decision of your workflow.
> Prove to yourself that you have the strength 💪 and the courage 🧠 to bring ORDER.
>
> (👆 *snap*)
> (⌨️🐍⛑️) Join... the VaultTools.
>
> Become part of an elite paper management force. (⚡⌨️)
> See exotic new DOIs from distant journals. (🔬🚀✨)
> And spread Managed Bibliography throughout your Vault. (📊🌐)
>
> Become a hero. (🦸)
> Become a legend. (🛩️🛩️🛩️)
>
> BECOME A VAULTTOOLER.
>
> *— Cloud & local PDF-to-Markdown · PDF metadata extraction · Image GC · Reconcile PA/PT/FE links · DOI citation graph · PubMed API · PubMed MeSH Concept Explorer · Crossref/PubMed HTTP session · Unicode symbol unification · note matching & archiving*

---

## Installation

**Prerequisites:** Python ≥ 3.10

```bash
pip install .
```

**External dependencies:**

- [MinerU](https://mineru.net) API token — required by `pdf2md` (cloud)
- [PyMuPDF](https://pypi.org/project/PyMuPDF/) — required by `rename-pdf` and `pdf2md-local`
- [pdfplumber](https://pypi.org/project/pdfplumber/) — required by `pdf2md-local` (offline)
- Recommended vault directory layout (see [Configuration](#configuration))

---

## Commands Overview

| Command | Description | 说明 |
| --- | --- | --- |
| `pdf2md` | MinerU PDF batch → Markdown + DOI enrichment | MinerU PDF 批处理 → Markdown + DOI 增强 |
| `pdf2md-local` | pdfplumber offline PDF → Markdown (no cloud) | pdfplumber 本地 PDF → Markdown（无需上传） |
| `clean-images` | Remove unreferenced images from IMAGE/ dir | 清理 IMAGE/ 中未被引用的图片 |
| `reconcile` | Audit PA/PT/FE frontmatter links → content | 审计并修复 PA/PT/FE 跨笔记链接 |
| `rename-pdf` | PyMuPDF title extraction → auto-rename PDFs | PyMuPDF 提取标题 → 自动重命名 PDF |
| `markdown` | Build global DOI citation graph across .md files | 建立全目录 DOI 引用图谱 |
| `crossref` | Crossref reference lookup (4 modes) | Crossref 参考文献查询（4种模式） |
| `match` | Match Clippings ↔ PT/PA/FE via 3 strategies | 匹配 Clippings 到翻译/分析/图表（3级策略） |
| `trash` | Archive subdirectories to dated folder | 归档子目录到日期文件夹 |
| `remove-doi` | Remove wrong DOI wikilinks from all .md | 从所有 .md 中删除错误 DOI |
| `cited-by` | Query PubMed for papers citing a given DOI | 查询 PubMed 引用某 DOI 的论文 |
| `archive` | Hardlink/copy a note + dependent files to target vault | 硬链接/复制笔记及其依赖文件到目标库 |
| `unify-symbols` | Replace Unicode special chars with ASCII across vault .md | 统一全库 .md 的 Unicode 特殊字符为 ASCII |
| `pmce` | PubMed MeSH Concept Explorer (DOI/title → MeSH terms) | PubMed MeSH 概念探索器（DOI/标题 → MeSH 词条） |

---

## Usage

### `pdf2md` — MinerU PDF Batch Processing / MinerU PDF 批处理

| Arg | Type | Default | Description |
| --- | --- | --- | --- |
| `--path_pdf` | str | `C:\Vault\PDF` | PDF source directory |
| `--path_zip` | str | `C:\Vault\ZIP` | ZIP download directory (cloud only) |
| `--path_md0` | str | `C:\Vault\Claude\MDfrPDF` | Markdown output directory |
| `--path_images` | str | None | Custom images directory (auto if None) |
| `--enable_api_references` | bool | True | Fetch Crossref references for each paper |
| `--enable_cited_by` | bool | True | Fetch PubMed cited-by data |
| `--cited_by_max` | int | 10 | Max cited-by results per paper |
| `--local` | flag | — | Use pdfplumber offline extraction instead of MinerU cloud |

Uploads PDFs in batches (≤45 per batch) to MinerU API, downloads extracted .zip, unpacks `full.md` + images, enriches frontmatter with DOIs, Crossref references, and PubMed cited-by data. With `--local`, uses pdfplumber offline — no cloud upload, suitable for sensitive documents. Processed PDFs are renamed with a `完成_` prefix.

```bash
vaultools pdf2md
vaultools pdf2md --local
vaultools pdf2md --cited_by_max 20
```

---

### `pdf2md-local` — Offline PDF-to-Markdown / 本地 PDF 转 Markdown

| Arg | Type | Default | Description |
| --- | --- | --- | --- |
| `--path_pdf` | str | `C:\Vault\PDF` | PDF source directory |
| `--path_md0` | str | `C:\Vault\Claude\MDfrPDF` | Markdown output directory |
| `--enable_api_references` | bool | True | Fetch Crossref references for each paper |
| `--enable_cited_by` | bool | True | Fetch PubMed cited-by data |
| `--cited_by_max` | int | 10 | Max cited-by results per paper |

Shortcut for `pdf2md --local`. Offline PDF-to-Markdown using pdfplumber — no cloud upload, suitable for sensitive documents. Extracts text, converts tables to Markdown tables, auto-detects section headings, enriches frontmatter with DOIs, Crossref references, and PubMed cited-by data.

```bash
vaultools pdf2md-local
vaultools pdf2md-local --cited_by_max 20
```

> **Equivalent to:** `vaultools pdf2md --local`

---

### `clean-images` — Image Garbage Collector / 图片垃圾回收

| Arg | Type | Default | Description |
| --- | --- | --- | --- |
| `path_vault` | str | `C:\Vault` | Vault root to scan for .md files |
| `path_images` | str | `C:\Vault\IMAGE` | Image directory to check |
| `path_trash` | str | `C:\Vault\TRASH\Image` | Destination for unreferenced images |

Scans all .md files in the vault, builds a set of referenced image filenames, compares with files in `IMAGE/`, moves unreferenced images to `TRASH/Image/`.

```bash
vaultools clean-images
```

---

### `reconcile` — Reconcile PA/PT/FE Links / PA/PT/FE 链接审计

| Arg | Type | Default | Description |
| --- | --- | --- | --- |
| `path_vault` | str | **Required** | Vault root to scan |

Scans all .md files in the vault, reads `paper-analyze`, `paper-translate`, `figure-extractor` frontmatter wikilinks, resolves them to the actual target file content, compares H1 headings with link display text, cleans PA filename prefixes. Reports:
- **Broken links** — target file doesn't exist
- **Mismatched display** — wikilink display text ≠ target H1
- **Duplicates** — same target referenced multiple times across notes

```bash
vaultools reconcile C:\Vault
```

> **Use after bulk MATCH operations** to verify all PA/PT/FE links resolve correctly.

---

| Arg | Type | Default | Description |
| --- | --- | --- | --- |
| `path_vault` | str | `C:\Vault` | Vault root to scan for .md files |
| `path_images` | str | `C:\Vault\IMAGE` | Image directory to check |
| `path_trash` | str | `C:\Vault\TRASH\Image` | Destination for unreferenced images |

Scans all .md files in the vault, builds a set of referenced image filenames from `![]()` markdown links, then compares with files in `IMAGE/`. Moves images not referenced by any .md to `TRASH/Image/` (hardlink + delete original).

```bash
vaultools clean-images
vaultools clean-images --path_images C:\Vault\IMAGE --path_trash C:\Vault\TRASH\Old
```

> **Safe by design:** only deletes images with NO references across the entire vault. Multi-threaded scan for speed.

---

### `rename-pdf` — Rename PDF by Title / 按标题重命名 PDF

| Arg | Type | Default | Description |
| --- | --- | --- | --- |
| `directory` | str | `.` | Directory containing PDF files |

Extracts the paper title from PDF metadata or the first-page heading using PyMuPDF (fitz). Cleans junk titles (status markers, degree suffixes, MSIDs), sanitizes to valid filenames, and renames PDFs. Skips files already prefixed with `完成_`.

```bash
vaultools rename-pdf C:\Vault\PDF
vaultools rename-pdf .
```

> **Titles are extracted from:** metadata `dc:title` → first-page layout analysis (largest font + position). Junk like "Untitled", "Microsoft Word", "Slide 1" is auto-filtered.

---

### `markdown` — Build DOI Citation Graph / 建立 DOI 引用图谱

| Arg | Description |
| --- | --- |
| `--path` | **Required.** Directory of .md files to scan |

Two-pass scan over all .md files:
1. **Collect phase:** Parse every file's `reference` and `cited_by` lists, build a global DOI→title mapping from wikilinks.
2. **Write-back phase:** Resolve all reference names using the global map, populate `被引` (cited by) with `[[stem]]` links, set `tags` to `正向` (cited by others) or `负向` (no external citations).

```bash
vaultools markdown --path C:\Vault\Clippings
```

> **Tags explained:** `正向` = at least one external paper cites this paper. `负向` = only self-references or no citations found.

---

### `crossref` — Crossref Reference Tool / Crossref 参考文献工具

| Arg | Description |
| --- | --- |
| `input` | File path / `local:path [doi:DOI]` / `doi:DOI` / `￥path` |

**4 modes:**

| Input | Behavior |
| --- | --- |
| `path/to/paper.md` | Extract DOI → fetch Crossref references → update `reference` in frontmatter |
| `￥path/to/paper.md` | Takeover: clear all old refs, search by title → fetch refs → rebuild `reference` |
| `local:path [doi:DOI]` | Parse `## 参考文献` section from body text, resolve DOIs, update frontmatter |
| `doi:10.1234/example` | Fetch refs for a DOI, then interactively choose which .md to import into |

Without arguments, enters interactive loop mode.

```bash
vaultools crossref paper.md
vaultools crossref "doi:10.1038/nature12345"
vaultools crossref "￥Untitled.md"
vaultools crossref "local:paper.md"
```

---

### `match` — Match PA/PT/FE Links / 匹配 PA/PT/FE

| Arg | Type | Default | Description |
| --- | --- | --- | --- |
| `base_dir` | str | **Required** | Vault root (contains `Clippings/`, `Chi/`, `Claude/`) |
| `--dry-run` | flag | — | Preview matches without writing |
| `--threshold` | float | 0.85 | Jaccard similarity threshold |
| `--force` | flag | — | Overwrite existing links |
| `-v, --verbose` | flag | — | Show failed-match details |

Three matching strategies, tried in order:
1. **source** — exact match on `source` field
2. **first_ref** — exact match on the first DOI in `reference`
3. **jaccard** — Jaccard similarity ≥ threshold on full DOI sets

Updates `paper-translate` (`→ Chi/`), `paper-analyze` (`→ Claude/`), `figure-extractor` (`→ Claude/*_figures.md`) fields in Clippings frontmatter.

```bash
vaultools match C:\Vault --dry-run
vaultools match C:\Vault --threshold 0.90 --verbose
```

---

### `trash` — Archive Subdirectories / 归档子目录

| Arg | Description |
| --- | --- |
| `path` | Directory whose subdirectories will be archived |

Moves all immediate subdirectories (except `.obsidian` and `TRASH`) into `trash/YYYYMMDD/`, then recreates empty shells.

```bash
vaultools trash C:\Vault\Clippings
```

---

### `remove-doi` — Remove Wrong DOI / 移除错误 DOI

| Arg | Description |
| --- | --- |
| `--path` | **Required.** Directory to scan recursively |
| `--doi` | DOI to remove (if omitted, prompts interactively) |

Scans all .md files under `--path`, removes lines containing the given DOI wikilink.

```bash
vaultools remove-doi --path C:\Vault\Clippings --doi 10.1234/wrong
vaultools remove-doi --path C:\Vault\Clippings
```

---

### `cited-by` — PubMed Cited-by Query / PubMed Cited-by 查询

| Arg | Description |
| --- | --- |
| `--path` | .md file or directory (enter `-` for interactive mode) |
| `--max` | Max citing papers to return (default 10) |

Queries PubMed's `pubmed_pubmed_citedin` link for papers citing the main DOI of each .md. Skips papers with `cited_by_date` < 30 days ago. Filters out DOIs already present in the directory.

```bash
vaultools cited-by --path C:\Vault\Clippings
vaultools cited-by --path paper.md --max 20
```

---

### `archive` — Archive Clippings / 归档 Clippings

| Arg | Description |
| --- | --- |
| `-s, --source` | **Required.** Source .md file path |
| `-t, --target` | **Required.** Target directory path |

Copies/hardlinks the source .md, its associated `paper-analyze` (→ Claude/), `paper-translate` (→ Chi/), and `*_figures.md` files to the target vault. Auto-fixes image paths and copies referenced images. Reports an action table to stdout.

```bash
vaultools archive -s note.md -t C:\Vault2\Clippings
```

> **Hardlink vs copy:** same volume = hardlink (zero extra disk). Cross-volume = fallback to copy.

---

### `unify-symbols` — Unicode Symbol Unification / 字符统一

| Arg | Type | Default | Description |
| --- | --- | --- | --- |
| `--vault` | str | `C:\Vault` | Vault root to scan for .md files |
| `--force` | flag | — | Actually apply changes (default is dry-run) |

Scans all .md files in the vault, replaces Unicode special characters (smart quotes, dashes, etc.) with ASCII equivalents in filenames and wikilinks.

```bash
vaultools unify-symbols
vaultools unify-symbols --vault C:\Vault --force
```

---

### `pmce` — PubMed MeSH Concept Explorer / PubMed MeSH 概念探索器

| Arg | Type | Default | Description |
| --- | --- | --- | --- |
| `input` | str | None | .md file path or pasted text (prompts if omitted) |
| `--path` | str | **Required** | Target Clippings\PENDING directory |
| `--no-graph` | flag | — | Skip automatic citation-graph rebuild |
| `--dry-run` | flag | — | Preview without writing |

Queries PubMed for MeSH terms and concept codes related to a paper's DOI/title, saving a structured note to the PENDING directory.

```bash
vaultools pmce --path C:\Vault\PENDING
vaultools pmce paper.md --path C:\Vault\PENDING
```

---

### `pdf_extractor` — PDF Metadata & First-Page Title Extraction / PDF 元数据与标题提取 (core)

`core/pdf_extractor.py` provides pdfplumber/PyMuPDF utilities reused by `pdf2md-local` and `rename-pdf`:

| Function | Purpose |
| --- | --- |
| `extract_text` | Extract all pages as normalized text |
| `extract_dois_from_pdf` | Multiprocessing-safe DOI extraction from PDF text |
| `extract_first_doi_from_pdf` | First-page DOI extraction |
| `table_to_md` | Convert pdfplumber tables to Markdown |
| `convert_pdf_to_md` | Full pdfplumber PDF → Markdown conversion |

---

### `http` — Shared Crossref/PubMed HTTP Session / 共享 Crossref/PubMed HTTP 会话 (core)

`core/http.py` provides a shared `requests.Session` with retry, rate-limit, and a unified user-agent, reused by all Crossref API and PubMed E-utilities calls to avoid throttling and duplicate connection setup.

| Function | Purpose |
| --- | --- |
| `make_session` | Create a shared session with a unified User-Agent |

---

## Configuration

Edit `config.py` before first use:

```python
CROSSREF_CACHE = Path(r'D:\ResearchFront\DATA\API\crossref_cache.json')
MINERU_TOKEN = Path(r'C:\ResearchFront\DATA\API\MinerU.txt')
OBSIDIAN_ROOT = Path(r'C:\Vault')
DEFAULT_PDF_PATH = Path(r'C:\Vault\PDF')
DEFAULT_ZIP_PATH = Path(r'C:\Vault\ZIP')
DEFAULT_MD_PATH = Path(r'C:\Vault\PENDING\Clippings')
DEFAULT_IMAGE_PATH = Path(r'C:\Vault\IMAGE')
```

**MinerU Token:** Obtain from [mineru.net](https://mineru.net), save the raw token string as a single line in `MinerU.txt`.

**Crossref Cache:** JSON file auto-created on first API call. Stores citation lookups and reference lists to avoid redundant API requests.

---

## Project Structure

```
├── cli.py                 # Entry point (argparse) / 入口
├── config.py              # Global path constants / 全局路径常量
├── pyproject.toml
├── commands/
│   ├── pdf2md.py          # MinerU batch pipeline / 批处理管道
│   ├── clean_images.py     # Image garbage collector / 图片垃圾回收
│   ├── rename_pdf.py      # PyMuPDF title rename / 标题重命名
│   ├── markdown_graph.py  # DOI citation graph builder / DOI 引用图谱
│   ├── crossref.py        # Crossref reference tool / Crossref 参考文献
│   ├── match.py           # PA/PT/FE matcher / PA/PT/FE 匹配器
│   ├── trash.py           # Directory archiver / 目录归档
│   ├── remove_doi.py      # DOI removal / DOI 移除
│   ├── cited_by.py        # PubMed cited-by query / PubMed cited-by
│   ├── archive.py         # Vault-to-vault archiver / Vault 间归档
│   ├── pmce.py            # PubMed MeSH Concept Explorer / PubMed MeSH 概念探索
│   └── unify_symbols.py   # Unicode→ASCII symbol unification / 字符统一
├── core/
│   ├── crossref_api.py    # Crossref + PubMed E-utilities API
│   ├── doi.py             # DOI regex / repair / canonicalization
│   ├── frontmatter.py     # YAML frontmatter parse/dump
│   ├── http.py            # Shared Crossref/PubMed HTTP session (retry, rate-limit, user-agent)
│   ├── markdown_utils.py  # Markdown body cleaning
│   ├── obsidian_path.py   # Obsidian URI resolution
│   ├── pdf_extractor.py   # pdfplumber/PyMuPDF PDF metadata & first-page title extraction
│   └── refs.py            # Wikilink reference utilities
└── scripts/               # .bat shortcuts for Windows
```

---

## FAQ

### 1. Can I change default paths? / 默认路径能改吗？

Yes. Edit `config.py` before first use. All paths are defined as constants at the module top. Command-line `--path_*` arguments override the defaults.

### 2. How to get a MinerU API token? / MinerU API Token 在哪获取？

Register at [mineru.net](https://mineru.net), copy your token, and save it as a single line in the file referenced by `config.MINERU_TOKEN` (default: `C:\ResearchFront\DATA\API\MinerU.txt`).

### 3. Why isn't my PDF being processed? / 为什么 PDF 没被处理？

- `pdf2md` skips files that already have a `完成_` prefix in the same directory (already processed).
- Only `.pdf` files are picked up.
- Batch size is ≤45; if you have more files, they are split into multiple batches.

### 4. What is the difference between the 4 `crossref` modes? / `crossref` 的四种模式有什么区别？

| Mode | Purpose |
| --- | --- |
| `path.md` | Standard: extract DOI from file → fetch Crossref refs → append to `reference` |
| `￥path.md` | Takeover: discard all existing `reference` entries, search by title for DOI, rebuild from scratch |
| `local:path` | Local: parse numbered entries under `## 参考文献` in body text, resolve each to DOI, write `reference` |
| `doi:10.xxx` | Import: fetch refs for a DOI, then choose a target .md to inject them into |

### 5. What do `正向` / `负向` tags mean? / `正向`/`负向` 标签是什么意思？

Set by the `markdown` command. `正向` means the paper is cited by at least one external paper (excluding special/non-DOI references). `负向` means no external citations were found.

### 6. How do the 3 `match` strategies work? / `match` 命令的三种匹配策略是如何工作的？

1. **source** — exact match of the `source` frontmatter field → fastest, most reliable.
2. **first_ref** — match the first DOI in `reference` → works when source differs.
3. **jaccard** — Jaccard similarity on the full DOI set → fallback for ambiguous cases. Threshold default 0.85.

### 7. What is the difference between `pdf2md` (cloud) and `pdf2md --local`? / `pdf2md`（云端）和 `pdf2md --local` 有什么区别？

`pdf2md` uploads PDFs to MinerU cloud API — best quality, supports complex formulas and embedded tables. `pdf2md --local` (or `pdf2md-local`) uses pdfplumber offline — no data leaves your machine, good for sensitive documents, tables converted to Markdown, formulas extracted as plain text.

### 8. How does `rename-pdf` extract titles? / `rename-pdf` 如何提取标题？

First attempts PDF metadata (`dc:title`). If junk or absent, falls back to first-page layout analysis: identifies the largest font block in the upper half of the page, filters out junk (Untitled, status markers, degree suffixes), and cleans to a safe filename (≤250 chars, no special characters). Requires `pip install pymupdf`.

---

## License

MIT

---

---

**作者：** Li Kan <lik1453529@163.com>

# Obsidian-Paper-Tools 3.4 — 织命者卡洛斯

> Obsidian。Our Vault。🔗 双向链接。🧠 关系图谱。📂 开放格式。
> 我们的科研之道。
>
> 但知识不会自己整理。
>
> (📄😨💥 PDF 散落... 📑 DOI 重复... 🔗💔 引用断裂...)
> (😨🧎 不... Sweet bibliography... NOOOOO)
>
> *INVASION*
>
> (🕺 haha) 眼熟吗？
> 这样的场景，此时此刻正在每位研究者的 Vault 中上演！ 🤷‍♂️
>
> 👉 下一个 👉 就是你。
>
> 除非——你做出工作流中最重要的决定。
> 证明你有将混沌化为秩序的力量 💪 和勇气 🧠。
>
> (👆 *snap*)
> (⌨️🐍⛑️) 加入……VaultTools。
>
> 成为精英论文管理部队的一员。(⚡⌨️)
> 邂逅远方期刊的新奇 DOI。(🔬🚀✨)
> 在整个 Vault 中传播 Managed Bibliography。(📊🌐)
>
> 成为英雄。(🦸)
> 成为传奇。(🛩️🛩️🛩️)
>
> 成为 VAULTTOOLER。
>
> *— 云端与本地 PDF 转 Markdown · PDF 元数据提取 · 图片垃圾回收 · DOI 引用图谱 · Crossref 缓存清洗 · PubMed API · PubMed MeSH 概念探索 · Crossref/PubMed HTTP 会话 · PyMuPDF 重命名 · 字符统一 · 笔记匹配与归档*

---

## 安装

**前置条件：** Python ≥ 3.10

```bash
pip install .
```

**外部依赖：**

- [MinerU](https://mineru.net) API token — `pdf2md` 命令必需（云）
- [PyMuPDF](https://pypi.org/project/PyMuPDF/) — `rename-pdf` 和 `pdf2md-local` 必需
- [pdfplumber](https://pypi.org/project/pdfplumber/) — `pdf2md-local` 必需（离线）
- 推荐的 Vault 目录结构（见[配置](#配置)）

---

## 命令概览

| 命令 | 说明 | Description |
| --- | --- | --- |
| `pdf2md` | MinerU PDF 批处理 → Markdown + DOI 增强 | MinerU PDF batch → Markdown + DOI enrichment |
| `pdf2md-local` | pdfplumber 本地 PDF → Markdown（无需上传） | pdfplumber offline PDF → Markdown (no cloud) |
| `clean-images` | 清理 IMAGE/ 中未被引用的图片 | Remove unreferenced images from IMAGE/ dir |
| `reconcile` | 审计并修复 PA/PT/FE 跨笔记链接 | Audit PA/PT/FE frontmatter links → content |
| `rename-pdf` | PyMuPDF 提取标题 → 自动重命名 PDF | PyMuPDF title extraction → auto-rename PDFs |
| `markdown` | 建立全目录 DOI 引用图谱 | Build global DOI citation graph across .md files |
| `crossref` | Crossref 参考文献查询（4种模式） | Crossref reference lookup (4 modes) |
| `match` | 匹配 Clippings 到翻译/分析/图表（3级策略） | Match Clippings ↔ PT/PA/FE via 3 strategies |
| `trash` | 归档子目录到日期文件夹 | Archive subdirectories to dated folder |
| `remove-doi` | 从所有 .md 中删除错误 DOI | Remove wrong DOI wikilinks from all .md |
| `cited-by` | 查询 PubMed 引用某 DOI 的论文 | Query PubMed for papers citing a given DOI |
| `archive` | 硬链接/复制笔记及其依赖文件到目标库 | Hardlink/copy a note + dependent files to target vault |
| `unify-symbols` | 统一全库 .md 的 Unicode 特殊字符为 ASCII | Replace Unicode special chars with ASCII across vault .md |
| `pmce` | PubMed MeSH 概念探索器（DOI/标题 → MeSH 词条） | PubMed MeSH Concept Explorer (DOI/title → MeSH terms) |

---

## 用法

### `pdf2md` — MinerU PDF 批处理

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--path_pdf` | str | `C:\Vault\PDF` | PDF 源目录 |
| `--path_zip` | str | `C:\Vault\ZIP` | ZIP 下载目录（仅云端） |
| `--path_md0` | str | `C:\Vault\Claude\MDfrPDF` | Markdown 输出目录 |
| `--enable_api_references` | bool | True | 拉取 Crossref 参考文献 |
| `--enable_cited_by` | bool | True | 拉取 PubMed 引用数据 |
| `--cited_by_max` | int | 10 | 每篇最多引用篇数 |
| `--local` | flag | — | 使用 pdfplumber 本地离线提取，不走 MinerU 云端 |

将 PDF 分批上传至 MinerU API（每批 ≤45），下载解包 `full.md` + 图片，自动提取 DOI、拉取 Crossref 参考文献和 PubMed cited-by 数据。加 `--local` 使用 pdfplumber 本地离线转换 — 无需上传云端，适合涉密文档。已处理 PDF 会被重命名为 `完成_` 前缀。

```bash
vaultools pdf2md
vaultools pdf2md --local
vaultools pdf2md --cited_by_max 20
```

---

### `pdf2md-local` — 本地 PDF 转 Markdown

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--path_pdf` | str | `C:\Vault\PDF` | PDF 源目录 |
| `--path_md0` | str | `C:\Vault\Claude\MDfrPDF` | Markdown 输出目录 |
| `--enable_api_references` | bool | True | 拉取 Crossref 参考文献 |
| `--enable_cited_by` | bool | True | 拉取 PubMed 引用数据 |
| `--cited_by_max` | int | 10 | 每篇最多引用篇数 |

`pdf2md --local` 的快捷命令。使用 pdfplumber 本地离线转换 — 无需上传至云端，适合涉密文档。自动提取正文、表格转 Markdown、检测章节标题，并提取 DOI、拉取 Crossref 参考文献和 PubMed cited-by 数据。

```bash
vaultools pdf2md-local
vaultools pdf2md-local --cited_by_max 20
```

> **等价于：** `vaultools pdf2md --local`

---

### `clean-images` — 图片垃圾回收

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `path_vault` | str | `C:\Vault` | Vault 根目录 |
| `path_images` | str | `C:\Vault\IMAGE` | 图片目录 |
| `path_trash` | str | `C:\Vault\TRASH\Image` | 未引用图片的目标目录 |

扫描 Vault 中所有 .md 文件，从 `![]()` markdown 链接中提取被引用的图片文件名，与 `IMAGE/` 目录中的实际文件比对。将未被任何 .md 引用的图片移至 `TRASH/Image/`（先硬链接再删除原文件）。多线程扫描。

```bash
vaultools clean-images
vaultools clean-images --path_images C:\Vault\IMAGE --path_trash C:\Vault\TRASH\Old
```

> **安全设计：** 仅删除在整个 Vault 中零引用的图片。

---

### `rename-pdf` — 按标题重命名 PDF

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `directory` | str | `.` | 包含 PDF 文件的目录 |

使用 PyMuPDF (fitz) 从 PDF 元数据或首页排版中提取论文标题，自动清除垃圾标题（状态标记、学位后缀、MSID 等），清洗为合法文件名后重命名 PDF。跳过已有 `完成_` 前缀的文件。

```bash
vaultools rename-pdf C:\Vault\PDF
vaultools rename-pdf .
```

> **标题来源：** 元数据 `dc:title` → 首页排版分析（最大字号 + 位置）。自动过滤 "Untitled"、"Microsoft Word"、"Slide 1" 等无效标题。

---

### `markdown` — 建立 DOI 引用图谱

| 参数 | 说明 |
| --- | --- |
| `--path` | **必填。** 待扫描的 .md 文件目录 |

两趟扫描全部 .md 文件：
1. **收集阶段：** 解析每个文件的 `reference` 和 `cited_by` 列表，从 wikilink 中构建全局 DOI→标题映射。
2. **回写阶段：** 利用全局映射解析所有 reference 名称，填充 `被引` 字段（以 `[[文件名]]` 链接表示），设置 `tags` 为 `正向`（被外部引用）或 `负向`（无外部引用）。

```bash
vaultools markdown --path C:\Vault\Clippings
```

> **标签说明：** `正向` = 至少有一篇外部论文引用了本文。`负向` = 仅有自引用或无引用。

---

### `crossref` — Crossref 参考文献工具

| 参数 | 说明 |
| --- | --- |
| `input` | 文件路径 / `local:路径 [doi:DOI]` / `doi:DOI` / `￥路径` |

**4 种模式：**

| 输入 | 行为 |
| --- | --- |
| `path/to/paper.md` | 提取 DOI → 拉取 Crossref 参考文献 → 更新 frontmatter `reference` |
| `￥path/to/paper.md` | 接管模式：清空旧引用，标题搜索 DOI，重建全部 `reference` |
| `local:路径 [doi:DOI]` | 本地模式：解析正文 `## 参考文献` 编号条目，补全 DOI，写入 frontmatter |
| `doi:10.1234/example` | 导入模式：拉取某 DOI 的参考文献，交互式选择导入目标 .md |

无参数时进入循环交互模式。

```bash
vaultools crossref paper.md
vaultools crossref "doi:10.1038/nature12345"
vaultools crossref "￥Untitled.md"
vaultools crossref "local:paper.md"
```

---

### `match` — 匹配 PA/PT/FE

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `base_dir` | str | **必填** | Vault 根目录（含 `Clippings/`、`Chi/`、`Claude/`） |
| `--dry-run` | flag | — | 预览匹配结果，不写入 |
| `--threshold` | float | 0.85 | Jaccard 相似度阈值 |
| `--force` | flag | — | 覆盖已有链接 |
| `-v, --verbose` | flag | — | 显示匹配失败的详细信息 |

三种匹配策略，按优先级执行：
1. **source** — `source` 字段精确匹配 → 最可靠
2. **first_ref** — `reference` 中第一个 DOI 精确匹配 → source 不一致时可用
3. **jaccard** — 全量 DOI 集合的 Jaccard 相似度 ≥ 阈值 → 兜底策略

在 Clippings 的 frontmatter 中更新 `paper-translate`（→ Chi/）、`paper-analyze`（→ Claude/）、`figure-extractor`（→ Claude/*_figures.md）字段。

```bash
vaultools match C:\Vault --dry-run
vaultools match C:\Vault --threshold 0.90 --verbose
```

---

### `trash` — 归档子目录

| 参数 | 说明 |
| --- | --- |
| `path` | 待归档子目录的父目录 |

将除 `.obsidian` 和 `TRASH` 外的所有一级子目录移动到 `trash/YYYYMMDD/`，原地重建空目录。

```bash
vaultools trash C:\Vault\Clippings
```

---

### `remove-doi` — 移除错误 DOI

| 参数 | 说明 |
| --- | --- |
| `--path` | **必填。** 递归扫描的目录 |
| `--doi` | 待删除的 DOI（如省略则交互式输入） |

递归扫描 `--path` 下所有 .md 文件，删除包含指定 DOI wikilink 的行。

```bash
vaultools remove-doi --path C:\Vault\Clippings --doi 10.1234/wrong
vaultools remove-doi --path C:\Vault\Clippings
```

---

### `cited-by` — PubMed Cited-by 查询

| 参数 | 说明 |
| --- | --- |
| `--path` | .md 文件或目录（输入 `-` 进入交互模式） |
| `--max` | 最多返回引用篇数（默认 10） |

通过 PubMed `pubmed_pubmed_citedin` 链接查询引用了各 .md 主 DOI 的论文。自动跳过 `cited_by_date` 距今不足 30 天的文件，并过滤目录中已存在的 DOI。

```bash
vaultools cited-by --path C:\Vault\Clippings
vaultools cited-by --path paper.md --max 20
```

---

### `archive` — 归档 Clippings

| 参数 | 说明 |
| --- | --- |
| `-s, --source` | **必填。** 源 .md 文件路径 |
| `-t, --target` | **必填。** 目标目录路径 |

将源 .md 及其关联的 `paper-analyze`（→ Claude/）、`paper-translate`（→ Chi/）、`*_figures.md` 文件复制/硬链接到目标 Vault。自动修正图片路径并拷贝图片。在 stdout 输出操作结果表。

```bash
vaultools archive -s note.md -t C:\Vault2\Clippings
```

> **硬链接 vs 复制：** 同卷 = 硬链接（不占额外磁盘空间）。跨卷 = 自动回退到复制。

---

### `unify-symbols` — 字符统一

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--vault` | str | `C:\Vault` | Vault 根目录 |
| `--force` | flag | — | 实际执行修改（默认为预览模式） |

扫描全库 .md 文件，将文件名与 wikilink 中的 Unicode 特殊字符（智能引号、破折号等）统一为 ASCII 等价字符。

```bash
vaultools unify-symbols
vaultools unify-symbols --vault C:\Vault --force
```

---

### `pmce` — PubMed MeSH 概念探索器

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `input` | str | 无 | .md 文件路径或粘贴文本（省略时提示输入） |
| `--path` | str | **必填** | 目标 Clippings\PENDING 目录 |
| `--no-graph` | flag | — | 跳过自动引用图谱重建 |
| `--dry-run` | flag | — | 预览而不写入 |

查询 PubMed，根据论文 DOI/标题返回相关 MeSH 词条与概念编码，生成结构化笔记到 PENDING 目录。

```bash
vaultools pmce --path C:\Vault\PENDING
vaultools pmce paper.md --path C:\Vault\PENDING
```

---

### `pdf_extractor` — PDF 元数据与首页标题提取（core）

`core/pdf_extractor.py` 提供 `pdf2md-local` 和 `rename-pdf` 复用的 pdfplumber/PyMuPDF 工具：

| 函数 | 用途 |
| --- | --- |
| `extract_text` | 提取全部页面为规范化文本 |
| `extract_dois_from_pdf` | 多进程安全的 PDF DOI 提取 |
| `extract_first_doi_from_pdf` | 首页 DOI 提取 |
| `table_to_md` | 将 pdfplumber 表格转为 Markdown |
| `convert_pdf_to_md` | 完整的 pdfplumber PDF → Markdown 转换 |

---

### `http` — 共享 Crossref/PubMed HTTP 会话（core）

`core/http.py` 提供带重试、限速与统一 User-Agent 的共享 `requests.Session`，供所有 Crossref API 与 PubMed E-utilities 调用复用，避免触发限流并减少重复建连。

| 函数 | 用途 |
| --- | --- |
| `make_session` | 创建带统一 User-Agent 的共享会话 |

---

## 配置

首次使用前编辑 `config.py`：

```python
CROSSREF_CACHE = Path(r'D:\ResearchFront\DATA\API\crossref_cache.json')
MINERU_TOKEN = Path(r'C:\ResearchFront\DATA\API\MinerU.txt')
OBSIDIAN_ROOT = Path(r'C:\Vault')
DEFAULT_PDF_PATH = Path(r'C:\Vault\PDF')
DEFAULT_ZIP_PATH = Path(r'C:\Vault\ZIP')
DEFAULT_MD_PATH = Path(r'C:\Vault\PENDING\Clippings')
DEFAULT_IMAGE_PATH = Path(r'C:\Vault\IMAGE')
```

**MinerU Token:** 从 [mineru.net](https://mineru.net) 获取，将原始 token 字符串保存为 `MinerU.txt` 中的一行。

**Crossref 缓存:** 首次 API 调用时自动创建 JSON 文件，缓存引用查询和参考文献列表以避免重复请求。

---

## 项目结构

```
├── cli.py                 # 入口 (argparse)
├── config.py              # 全局路径常量
├── pyproject.toml
├── commands/
│   ├── pdf2md.py          # MinerU 批处理管道
│   ├── clean_images.py     # 图片垃圾回收
│   ├── rename_pdf.py      # PyMuPDF 标题重命名
│   ├── markdown_graph.py  # DOI 引用图谱构建
│   ├── crossref.py        # Crossref 参考文献工具
│   ├── match.py           # PA/PT/FE 匹配器
│   ├── trash.py           # 目录归档器
│   ├── remove_doi.py      # DOI 移除
│   ├── cited_by.py        # PubMed cited-by 查询
│   ├── archive.py         # Vault 间归档
│   ├── pmce.py            # PubMed MeSH 概念探索
│   └── unify_symbols.py   # 字符统一
├── core/
│   ├── crossref_api.py    # Crossref + PubMed E-utilities API
│   ├── doi.py             # DOI 正则 / 修复 / 规范化
│   ├── frontmatter.py     # YAML frontmatter 解析/写入
│   ├── http.py            # Crossref/PubMed 共享 HTTP 会话（重试、限速、UA）
│   ├── markdown_utils.py  # Markdown 正文清理
│   ├── obsidian_path.py   # Obsidian URI 解析
│   ├── pdf_extractor.py   # pdfplumber/PyMuPDF PDF 元数据与首页标题提取
│   └── refs.py            # Wikilink 引用工具
├── scripts/               # Windows .bat 快捷方式
└── tests/
```

---

## 常见问题

### 1. 默认路径能改吗？

可以。首次使用前编辑 `config.py`，所有路径均为模块顶层常量。命令行 `--path_*` 参数优先于默认值。

### 2. MinerU API Token 在哪获取？

在 [mineru.net](https://mineru.net) 注册，复制 token，保存为单行到 `config.MINERU_TOKEN` 指向的文件（默认：`C:\ResearchFront\DATA\API\MinerU.txt`）。

### 3. 为什么 PDF 没被处理？

- `pdf2md` 会跳过所在目录已有 `完成_` 前缀的同名文件（已处理过）。
- 仅处理 `.pdf` 文件。
- 每批最多 45 个文件，超过则自动分批。

### 4. `crossref` 的四种模式有什么区别？

| 模式 | 用途 |
| --- | --- |
| `路径.md` | 标准：提取文件 DOI → 拉取 Crossref 参考文献 → 追加到 `reference` |
| `￥路径.md` | 接管：丢弃全部旧引用，标题搜索 DOI，从零重建 |
| `local:路径` | 本地：解析正文 `## 参考文献` 下的编号条目，逐条补全 DOI，写入 `reference` |
| `doi:10.xxx` | 导入：拉取某 DOI 的参考文献，交互式选择导入目标 |

### 5. `正向`/`负向` 标签是什么意思？

由 `markdown` 命令设置。`正向` = 该论文被至少一篇外部论文引用（不含特殊/非 DOI 引用）。`负向` = 未发现外部引用。

### 6. `match` 命令的三种匹配策略如何工作？

1. **source** — `source` 字段精确匹配，最快最可靠。
2. **first_ref** — `reference` 第一个 DOI 精确匹配，用于 source 不一致的情况。
3. **jaccard** — 全量 DOI 集合的 Jaccard 相似度 ≥ 阈值（默认 0.85），作为兜底策略。

### 7. `pdf2md`（云端）和 `pdf2md --local` 有什么区别？

`pdf2md` 将 PDF 上传至 MinerU 云端 API — 质量最优，支持复杂公式和内嵌表格。`pdf2md --local`（或 `pdf2md-local`）使用 pdfplumber 在本地离线转换 — 数据不离开本机，适合涉密文档，表格转为 Markdown，公式提取为纯文本。

### 8. `rename-pdf` 如何提取标题？

首先尝试 PDF 元数据 (`dc:title`)。若为无效或缺失，则回退到首页排版分析：在页面上半部分识别最大字号文本块，过滤无效标题（Untitled、状态标记、学位后缀），清洗为安全文件名（≤250 字符，无特殊字符）。需要 `pip install pymupdf`。

---

## 许可证

MIT

---

## 增量对比 (vs v3.3)

对比范围：`*.py` / `*.toml` / `*.md`（排除 `__pycache__` 字节码产物）。v3.3 全部源文件在 v3.4 中均保留，**无移除文件**；v3.4 新增 1 个文件（`core/http.py`）；其余 21 个源文件内容发生改动。

| 维度 | v3.3 | v3.4 |
| --- | --- | --- |
| **新增文件** | — | `core/http.py`（共享 Crossref/PubMed HTTP 会话） |
| **移除文件** | 无 | — |
| **cli.py** | `markdown` 命令仅 `--path`；`match --threshold` 硬编码 0.85 | 新增 `--depth`（分文件夹统计深度，默认 0）；阈值改用 `JACCARD_THRESHOLD` 常量；`run_markdown_graph(args.path, args.depth)` |
| **pyproject.toml** | description 提及 "pmce (PubMed MeSH Concept Explorer)" | description 改为 "shared HTTP session (retry/rate-limit)" |
| **core/__init__.py** | docstring 不含 http | docstring 加入 http 模块 |
| **core/doi.py** | `is_plausible_doi` 无缓存 | 加 `@lru_cache(maxsize=16384)` |
| **core/frontmatter.py** | 提供 `read_fm()` 辅助 | 删除 `read_fm()`，`_collect_file_dois` 内联 `parse_frontmatter_file(...)[0] or {}` |
| **core/obsidian_path.py** | 候选元组 for 循环 | 简化为单一 `candidate` 变量判断 |
| **core/pdf_extractor.py** | 含 `extract_text()` | 删除未使用的 `extract_text()` |
| **core/crossref_api.py** | 本地 `requests.Session` + 直接 `import requests`；strptime 解析出版日期 | 改用 `make_session()`；新增 `_parse_pubdate()` 正则解析（非法输入返回 None，等价且更快） |
| **core/http.py** | 不存在 | 新增：`make_session()` 返回带统一 User-Agent 的共享 `requests.Session` |
| **commands/archive.py** | 重复 `dst_dir/src.name` 计算、局部 `src_vault_sub/'Claude'` | 复用 `dst_md`/`src_claude`/`figs_dst` 变量 |
| **commands/clean_images.py** | `actual_files` 集合推导内联 | 提取 `image_names()` 辅助函数，供 run_clean_images 与 trash 复用 |
| **commands/crossref.py** | `process_file`/`_handle_takeover_mode` 各自解析后缀/内容 | 提取 `_load_md_or_pdf()` 统一读取 .md/.pdf |
| **commands/markdown_graph.py** | 仅全局统计；`_update_doi_map` 不返回值 | `_update_doi_map` 返回 entry；新增 `FolderStats` 类按 `--depth` 分文件夹统计；微调 trophy 打印（去掉多余空行） |
| **commands/match.py** | PA/DOI 全文扫描无记忆；Chi/Claude 串行 IO | 新增 `doi_memo` 缓存避免重复扫描；ThreadPoolExecutor 并行读取；`_apply_found` 统一 PA/FE 落地逻辑；`FUZZY_THRESHOLD = SM_QUICK` |
| **commands/pdf2md.py** | 直接 `requests.get/post/put`；`extract_text` 嵌套循环 | 改用共享 `make_session()`；JSONDecodeError 导入路径修正；生成器 + `chain.from_iterable` 展平块 |
| **commands/pmce.py** | 本地 `requests.Session`；`_fetch_fulltext_xml` 辅助；手写三项计数；`_print_non_oa` 在图前 | 改用 `make_session()`；删除辅助并内联；`Counter` 统计；`_print_non_oa` 移到图建立之后 |
| **commands/reconcile.py** | 解析串行；PA 逻辑内联于循环 | ThreadPoolExecutor 并行解析 frontmatter/PA/PT；`pa_targets` 预计算字典 |
| **commands/rename_pdf.py** | `re.sub` 内联；`fitz.open` 手动 close | 预编译 `ET_AL_RE`/`WS_RE`；`with fitz.open()` 上下文管理 |
| **commands/trash.py** | `_scan_referenced`/内联集合推导 | 删除辅助，`run_trash` 内联；改用 `image_names()` |
| **commands/unify_symbols.py** | 串行读改写 | 提取 `_fix_one()` + ThreadPoolExecutor 并行读写 |
| **README.md** | 文末含「增量对比 (vs v3.3)」章节 | 删除该章节，文末止于「许可证 / MIT」；新增 `http` 章节与目录结构条目；本对比为其后追加 |

### 关键变化

- **新增 `core/http.py`**：全项目统一 HTTP 入口 `make_session()`，统一 User-Agent，crossref_api / pmce / pdf2md 全部改用共享会话（连接池复用、避免限流）。
- **并行 IO 提速**：match / reconcile / unify_symbols 用 `ThreadPoolExecutor` 并行读取与解析（字典更新保持串行保序）；pdf2md 的 `_extract_json_data` 用生成器 + `chain` 展平。
- **DOI 全文查找记忆化**：match 的 `_pa_by_doi` 新增 `doi_memo`，同一 DOI 只做一次全量扫描。
- **`is_plausible_doi` 加缓存**：`@lru_cache(maxsize=16384)` 避免重复正则校验。
- **出版日期解析优化**：crossref_api 用 `_parse_pubdate` 正则替代 `strptime`，非法输入返回 None 继续处理（不再抛异常跳过）。
- **markdown 命令支持 `--depth`**：按文件夹层级输出各子目录引用图谱统计（`FolderStats`）。
- **删除死代码**：frontmatter `read_fm`、pdf_extractor `extract_text`、pmce `_fetch_fulltext_xml`、trash `_scan_referenced` 等辅助函数被移除或内联。
- **Bug/健壮性**：rename_pdf 改用 `with fitz.open()` 确保关闭；pmce 将 `_print_non_oa` 移到图谱建立后，避免图构建失败时遗漏输出。
- **README**：移除上一轮「vs v3.3」章节，文末恢复为纯「许可证 MIT」，并在英中两处新增 `http` 模块文档；本对比章节为新增内容。

> 注：`scripts/存档/PMCE.bat` 在 v3.4 也有改动（不在 `*.py`/`*.toml`/`*.md` 对比范围内，未详列）。
