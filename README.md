![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue) ![License](https://img.shields.io/badge/license-MIT-green)

**Author:** Li Kan <lik1453529@163.com>

---

# Obsidian-Paper-Tools 3.1 — 织命者卡洛斯

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
> *— Cloud & local PDF-to-Markdown · Image GC · Reconcile PA/PT/FE links · DOI citation graph · PubMed API · Unicode symbol unification · note matching & archiving*

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
│   └── unify_symbols.py   # Unicode→ASCII symbol unification / 字符统一
├── core/
│   ├── crossref_api.py    # Crossref + PubMed E-utilities API
│   ├── doi.py             # DOI regex / repair / canonicalization
│   ├── frontmatter.py     # YAML frontmatter parse/dump
│   ├── markdown_utils.py  # Markdown body cleaning
│   ├── obsidian_path.py   # Obsidian URI resolution
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

# Obsidian-Paper-Tools 3.1 — 织命者卡洛斯

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
> *— 云端与本地 PDF 转 Markdown · 图片垃圾回收 · DOI 引用图谱 · Crossref 缓存清洗 · PubMed API · PyMuPDF 重命名 · 字符统一 · 笔记匹配与归档*

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
│   └── unify_symbols.py   # 字符统一
├── core/
│   ├── crossref_api.py    # Crossref + PubMed E-utilities API
│   ├── doi.py             # DOI 正则 / 修复 / 规范化
│   ├── frontmatter.py     # YAML frontmatter 解析/写入
│   ├── markdown_utils.py  # Markdown 正文清理
│   ├── obsidian_path.py   # Obsidian URI 解析
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

## 增量对比 (vs v3.0)

| 维度 | v3.0 | v3.1 |
| --- | --- | --- |
| **新增文件** | — | `commands/unify_symbols.py`（新增 unify-symbols 命令） |
| **移除文件** | 无（v3.1 保留 v3.0 全部 23 个文件） | — |
| **cli.py** | 121 行 | 121 行 · 新增 `unify-symbols` 子命令；`match args.command:` 重构为 handlers 字典分发 |
| **config.py** | 10 行 | 10 行 · 仅 docstring 精简：`Path & API config — ...` → `Global path constants` |
| **core/__init__.py** | 2 行 | 24 行 · 新增 `is_vault_dir()`（识别 Clippings/Claude/Chi）与 `try_copy()`（硬链接→复制） |
| **core/refs.py** | 55 行 | 143 行 · 新增 `canonicalize_stem`（Unicode 破折号/引号→ASCII）及从 match/reconcile 迁移的 wikilink 工具函数 |
| **core/obsidian_path.py** | 85 行 | 85 行 · 仅 docstring 精简 |
| **core/markdown_utils.py** | 48 行 | 48 行 · 仅 docstring 精简 |
| **core/frontmatter.py** | 88 行 | 88 行 · 仅 docstring 精简 |
| **core/doi.py** | 105 行 | 130 行 · `is_plausible_doi` 增加长度/双DOI/`doi:`标签/统计CI/引用尾过滤；`get_main_doi` 改为优先正文首个 DOI |
| **core/crossref_api.py** | 195 行 | 221 行 · 缺失 DOI 的参考文献改为线程池并发补全，缓存读写加锁 |
| **commands/match.py** | 349 行 | 328 行 · 复用 `core.refs` 工具；`_match_pa` 传入 DOI 缓存参数；新增 `_pa_by_doi` |
| **commands/markdown_graph.py** | 209 行 | 222 行 · 文件处理改为线程池并发 |
| **commands/crossref.py** | 295 行 | 295 行 · 仅 docstring 精简 |
| **commands/clean_images.py** | 69 行 | 69 行 · 仅 docstring 精简 |
| **commands/cited_by.py** | 91 行 | 108 行 · 批处理改为线程池并发 |
| **commands/archive.py** | 131 行 | 111 行 · 辅助函数内联；`_copy_status` → `_copy_file` |
| **commands/remove_doi.py** | 24 行 | 40 行 · 改为线程池并发 |
| **commands/reconcile.py** | 284 行 | 244 行 · 引用文件（`*_citations`）强制保留；重复文件检测；移动目标冲突时改移入 TRASH |
| **commands/pdf2md.py** | 658 行 | 647 行 · 输出文件名 `canonicalize_stem` 规范化；PDF 提取 DOI 前去除换行；轮询请求失败重试；`_mark_pdf_done` 内联移除 |
| **commands/trash.py** | 88 行 | 88 行 · 仅 docstring 精简 |
| **commands/rename_pdf.py** | 231 行 | 246 行 · `fitz` 移至顶层导入；重命名改为线程池并发 |
| **commands/__init__.py** | 2 行 | 2 行 · docstring 加入 unify_symbols |
| **pyproject.toml** | 20 行 | 21 行 · 新增依赖 `PyMuPDF`；描述加入 unify-symbols |
| **README.md** | 836 行 | 846 行 · 新增 unify-symbols 命令章节/命令表/项目结构；删除末尾「增量对比 (vs v3.0)」章节 |

### 关键变化

- **新增 `unify-symbols` 命令（唯一新文件 `commands/unify_symbols.py`）**：扫描全库（Claude/Chi/Clippings）`.md`，将文件名与 wikilink 中的 Unicode 特殊字符（智能引号、破折号等）统一为 ASCII 等价物；默认 dry-run，`--force` 实际执行（重命名文件 + 更新链接）。
- **Unicode 规范化下沉至 `core.refs.canonicalize_stem`**：`match.py` / `reconcile.py` / `pdf2md.py` / `unify_symbols.py` 共用同一规范化表；`core/doi.py` 的 `SMART_QUOTE_TABLE` 同步改为按典化引号映射 + ASCII 破折号。
- **并发改造（本轮最大主题）**：`markdown_graph`、`cited_by`、`remove_doi`、`rename_pdf` 及 `crossref_api.fetch_references`（缺失 DOI 补全）改为 `ThreadPoolExecutor` 并发；共享缓存/集合用 `threading.Lock` 保护。
- **`cli.py` 重构**：`match args.command:` 匹配式改为 `handlers` 字典 + `handlers.get(...)()` 分发，并注册 `unify-symbols`。
- **`reconcile` 增强**：`*_citations` 引用文件强制保留（`[citation]` 标记）；`foo 2.md` 类重复文件检测（`[duplicate]` 标记）；移动目标冲突时不再 `[SKIP]`，而是将源文件移入 TRASH 并统计 `dupes_trashed`。
- **`pdf2md` 完善**：PDF 文本提取 DOI 前 `\n`→空格修复跨行 DOI；MinerU 批量轮询遇请求异常时等待重试而非直接失败；输出 MD 文件名经 `canonicalize_stem` 规范化；`_mark_pdf_done` 内联删除。
- **`doi.is_plausible_doi` 过滤增强**：>200 字符、含双 DOI、含 `.doi:` 标签、统计量/置信区间、引用尾缀等候选一律拒绝，显著降低误检。
- **依赖变更**：`pyproject.toml` 新增 `PyMuPDF` 依赖（原为可选运行时导入，现声明为必需）。
- **docstring 全面统一重写**：`config.py`、`core/obsidian_path.py`、`core/markdown_utils.py`、`core/frontmatter.py`、`commands/crossref.py`、`commands/clean_images.py`、`commands/trash.py` 仅此差异。
- **README**：新增 unify-symbols 命令说明（中英双语）、命令表与项目结构条目；删除 v3.0 末尾「增量对比 (vs v3.0)」章节（v3.1 不保留历史对比）。
