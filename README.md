![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue) ![License](https://img.shields.io/badge/license-MIT-green)

**Author:** Li Kan <lik1453529@163.com>

---

# Obsidian-Paper-Tools 2.0 — 卢布林合并

> **卢布林合并 (Union of Lublin, 1569)** — 波兰王冠与立陶宛大公国结束近两百年松散共主，合并为单一联邦：一个君主、一个议会、一种货币。本项目正是 [MinerU-Crossref-4-Obsidian](https://github.com/GLADOS67/MinerU-Crossref-4-Obsidian)（PDF→MD 流水线）与 [DOI-for-Obsidian](https://github.com/GLADOS67/Digital-Object-Identifier-DOI-for-Obsidian)（引用图谱建造器）的卢布林时刻——两套独立系统自此合为统一工具链。

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
> *— Cloud & local PDF-to-Markdown · DOI citation graph · Crossref/PubMed API · PyMuPDF rename · note matching & archiving*

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
| `rename-pdf` | PyMuPDF title extraction → auto-rename PDFs | PyMuPDF 提取标题 → 自动重命名 PDF |
| `markdown` | Build global DOI citation graph across .md files | 建立全目录 DOI 引用图谱 |
| `crossref` | Crossref reference lookup (4 modes) | Crossref 参考文献查询（4种模式） |
| `match` | Match Clippings ↔ PT/PA/FE via 3 strategies | 匹配 Clippings 到翻译/分析/图表（3级策略） |
| `trash` | Archive subdirectories to dated folder | 归档子目录到日期文件夹 |
| `remove-doi` | Remove wrong DOI wikilinks from all .md | 从所有 .md 中删除错误 DOI |
| `cited-by` | Query PubMed for papers citing a given DOI | 查询 PubMed 引用某 DOI 的论文 |
| `archive` | Hardlink/copy a note + dependent files to target vault | 硬链接/复制笔记及其依赖文件到目标库 |

---

## Usage

### `pdf2md` — MinerU PDF Batch Processing / MinerU PDF 批处理

| Arg | Type | Default | Description |
| --- | --- | --- | --- |
| `--path_pdf` | str | `C:\Vault\PDF` | PDF source directory |
| `--path_zip` | str | `C:\Vault\ZIP` | ZIP download directory |
| `--path_md0` | str | `C:\Vault\Claude\MDfrPDF` | Markdown output directory |
| `--enable_api_references` | bool | True | Fetch Crossref references for each paper |
| `--enable_cited_by` | bool | True | Fetch PubMed cited-by data |
| `--cited_by_max` | int | 10 | Max cited-by results per paper |

Uploads PDFs in batches (≤45 per batch) to MinerU API, downloads extracted .zip, unpacks `full.md` + images, enriches frontmatter with DOIs, Crossref references, and PubMed cited-by data. Processed PDFs are renamed with a `完成_` prefix.

```bash
vaultools pdf2md
vaultools pdf2md --cited_by_max 20 --enable_api_references false
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

Offline PDF-to-Markdown using pdfplumber — no cloud upload, suitable for sensitive documents. Extracts text, converts tables to Markdown tables, auto-detects section headings, enriches frontmatter with DOIs, Crossref references, and PubMed cited-by data. Processed PDFs are renamed with a `完成_` prefix.

```bash
vaultools pdf2md-local
vaultools pdf2md-local --cited_by_max 20 --enable_api_references false
```

> **Use `pdf2md-local` when:** privacy matters, you're offline, or MinerU API is unavailable.

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

## Configuration

Edit `config.py` before first use:

```python
CROSSREF_CACHE = Path(r'D:\ResearchFront\DATA\API\crossref_cache.json')
MINERU_TOKEN = Path(r'C:\ResearchFront\DATA\API\MinerU.txt')
OBSIDIAN_ROOT = Path(r'C:\Vault')
DEFAULT_PDF_PATH = Path(r'C:\Vault\PDF')
DEFAULT_ZIP_PATH = Path(r'C:\Vault\ZIP')
DEFAULT_MD_PATH = Path(r'C:\Vault\Claude\MDfrPDF')
```

**MinerU Token:** Obtain from [mineru.net](https://mineru.net), save the raw token string as a single line in `MinerU.txt`.

**Crossref Cache:** JSON file auto-created on first API call. Stores citation lookups and reference lists to avoid redundant API requests.

---

## Project Structure

```
├── cli.py                 # Entry point (argparse)
├── config.py              # Global path constants
├── pyproject.toml
├── commands/
│   ├── pdf2md.py          # MinerU batch pipeline
│   ├── pdf2md_local.py    # pdfplumber offline pipeline
│   ├── rename_pdf.py      # PyMuPDF title rename
│   ├── markdown_graph.py  # DOI citation graph builder
│   ├── crossref.py        # Crossref reference tool
│   ├── match.py           # PA/PT/FE matcher
│   ├── trash.py           # Directory archiver
│   ├── remove_doi.py      # DOI removal
│   ├── cited_by.py        # PubMed cited-by query
│   └── archive.py         # Vault-to-vault archiver
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

### 7. What is the difference between `pdf2md` and `pdf2md-local`? / `pdf2md` 和 `pdf2md-local` 有什么区别？

`pdf2md` uploads PDFs to MinerU cloud API — best quality, supports complex formulas and embedded tables. `pdf2md-local` uses pdfplumber offline — no data leaves your machine, good for sensitive documents, tables converted to Markdown, formulas extracted as plain text.

### 8. How does `rename-pdf` extract titles? / `rename-pdf` 如何提取标题？

First attempts PDF metadata (`dc:title`). If junk or absent, falls back to first-page layout analysis: identifies the largest font block in the upper half of the page, filters out junk (Untitled, status markers, degree suffixes), and cleans to a safe filename (≤250 chars, no special characters). Requires `pip install pymupdf`.

---

## License

MIT

---

---

**作者：** Li Kan <lik1453529@163.com>

# Obsidian-Paper-Tools 2.0 — 卢布林合并

> **卢布林合并 (1569)** — 波兰王冠与立陶宛大公国结束近两百年松散共主，合并为单一联邦：一个君主、一个议会、一种货币。本项目正是 [MinerU-Crossref-4-Obsidian](https://github.com/GLADOS67/MinerU-Crossref-4-Obsidian)（PDF→MD 流水线）与 [DOI-for-Obsidian](https://github.com/GLADOS67/Digital-Object-Identifier-DOI-for-Obsidian)（引用图谱建造器）的卢布林时刻——两套独立系统自此合为统一工具链。

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
> *— 云端与本地 PDF 转 Markdown · DOI 引用图谱 · Crossref/PubMed API · PyMuPDF 重命名 · 笔记匹配与归档*

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
| `rename-pdf` | PyMuPDF 提取标题 → 自动重命名 PDF | PyMuPDF title extraction → auto-rename PDFs |
| `markdown` | 建立全目录 DOI 引用图谱 | Build global DOI citation graph across .md files |
| `crossref` | Crossref 参考文献查询（4种模式） | Crossref reference lookup (4 modes) |
| `match` | 匹配 Clippings 到翻译/分析/图表（3级策略） | Match Clippings ↔ PT/PA/FE via 3 strategies |
| `trash` | 归档子目录到日期文件夹 | Archive subdirectories to dated folder |
| `remove-doi` | 从所有 .md 中删除错误 DOI | Remove wrong DOI wikilinks from all .md |
| `cited-by` | 查询 PubMed 引用某 DOI 的论文 | Query PubMed for papers citing a given DOI |
| `archive` | 硬链接/复制笔记及其依赖文件到目标库 | Hardlink/copy a note + dependent files to target vault |

---

## 用法

### `pdf2md` — MinerU PDF 批处理

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--path_pdf` | str | `C:\Vault\PDF` | PDF 源目录 |
| `--path_zip` | str | `C:\Vault\ZIP` | ZIP 下载目录 |
| `--path_md0` | str | `C:\Vault\Claude\MDfrPDF` | Markdown 输出目录 |
| `--enable_api_references` | bool | True | 拉取 Crossref 参考文献 |
| `--enable_cited_by` | bool | True | 拉取 PubMed 引用数据 |
| `--cited_by_max` | int | 10 | 每篇最多引用篇数 |

将 PDF 分批上传至 MinerU API（每批 ≤45），下载解包 `full.md` + 图片，自动提取 DOI 并写入 frontmatter 的 `reference` 字段，同时拉取 Crossref 参考文献和 PubMed cited-by 数据。已处理的 PDF 会被重命名为 `完成_` 前缀。

```bash
vaultools pdf2md
vaultools pdf2md --cited_by_max 20 --enable_api_references false
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

使用 pdfplumber 本地离线转换 — 无需上传至云端，适合涉密文档。自动提取正文、表格转 Markdown、检测章节标题，并提取 DOI、拉取 Crossref 参考文献和 PubMed cited-by 数据。已处理 PDF 会被重命名为 `完成_` 前缀。

```bash
vaultools pdf2md-local
vaultools pdf2md-local --cited_by_max 20 --enable_api_references false
```

> **使用时机：** 隐私优先、离线环境、或 MinerU API 不可用时。

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

## 配置

首次使用前编辑 `config.py`：

```python
CROSSREF_CACHE = Path(r'D:\ResearchFront\DATA\API\crossref_cache.json')
MINERU_TOKEN = Path(r'C:\ResearchFront\DATA\API\MinerU.txt')
OBSIDIAN_ROOT = Path(r'C:\Vault')
DEFAULT_PDF_PATH = Path(r'C:\Vault\PDF')
DEFAULT_ZIP_PATH = Path(r'C:\Vault\ZIP')
DEFAULT_MD_PATH = Path(r'C:\Vault\Claude\MDfrPDF')
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
│   ├── pdf2md_local.py    # pdfplumber 本地管道
│   ├── rename_pdf.py      # PyMuPDF 标题重命名
│   ├── markdown_graph.py  # DOI 引用图谱构建
│   ├── crossref.py        # Crossref 参考文献工具
│   ├── match.py           # PA/PT/FE 匹配器
│   ├── trash.py           # 目录归档器
│   ├── remove_doi.py      # DOI 移除
│   ├── cited_by.py        # PubMed cited-by 查询
│   └── archive.py         # Vault 间归档
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

### 7. `pdf2md` 和 `pdf2md-local` 有什么区别？

`pdf2md` 将 PDF 上传至 MinerU 云端 API — 质量最优，支持复杂公式和内嵌表格。`pdf2md-local` 使用 pdfplumber 在本地离线转换 — 数据不离开本机，适合涉密文档，表格转为 Markdown，公式提取为纯文本。

### 8. `rename-pdf` 如何提取标题？

首先尝试 PDF 元数据 (`dc:title`)。若为无效或缺失，则回退到首页排版分析：在页面上半部分识别最大字号文本块，过滤无效标题（Untitled、状态标记、学位后缀），清洗为安全文件名（≤250 字符，无特殊字符）。需要 `pip install pymupdf`。

---

## 许可证

MIT

---

## 增量对比 (vs v1.0)

对 `Obsidian-Paper-Tools - 1`（v1.0）与 `Obsidian-Paper-Tools - 2`（v2.0）两个项目的 `*.py`、`*.toml`、`*.md` 全部文件逐行比对结果。

**文件级变化：**

| 维度 | v1.0 | v2.0 |
| --- | --- | --- |
| **新增文件** | — | `commands/pdf2md_local.py`、`commands/rename_pdf.py`、`core/refs.py` |
| **移除文件** | 无 | — |
| **cli.py** | 8 个命令；无本地转换与重命名入口 | 新增 `pdf2md-local`（`--path_pdf`/`--path_md0`/`--enable_api_references`/`--enable_cited_by`/`--cited_by_max`）与 `rename-pdf`（positional `directory`，默认 `.`）两个子命令、参数及分发分支；模块导入增加 `run_pdf2md_local`、`run_rename_pdf` |
| **config.py** | 无变化 | 与 v1.0 完全一致（13 行） |
| **pyproject.toml** | description 仅提 MinerU | description 补充 pdfplumber 与 PyMuPDF rename；`dependencies`、版本号、entry-point 均未变（PyMuPDF 未加入依赖） |
| **README.md** | 仅覆盖 MinerU 云转换的 8 个命令 | 命令概览/用法/FAQ 新增 `pdf2md-local`、`rename-pdf`；FAQ 新增 7、8；项目结构新增两命令与 `refs.py`；外部依赖新增 PyMuPDF/pdfplumber；英中文镜像同步 |
| **commands/__init__.py** | 文档字符串列 8 个模块 | 新增 `pdf2md_local`、`rename_pdf` 两条说明（12 行） |
| **commands/pdf2md.py** | 本地重复实现 `process_existing_references`/`_build_existing_dois`；单一大 `_process_md_content`；`完成_` 版 PDF 无条件移入 TRASH | 改为引用 `core.refs`；`_process_md_content` 拆分出 `_collect_all_dois`/`_extract_pdf_text`/`_update_cited_by`/`_merge_new_dois`/`_pin_main_doi`；新增 `_build_clippings_index`/`_find_clippings_md`（SequenceMatcher≥0.85）；`完成_` 版 PDF 先执行 `run_match(force=True)`，成功才移入 TRASH；`clippings_doi_set` 批量预计算 |
| **commands/markdown_graph.py** | 内联 `_split_wikilink`/`_parse_cited_by_entry` | 改用 `core.refs.split_wikilink`（241 行，少 4 行） |
| **commands/crossref.py** | 本地 `process_existing_references`（48-74 行） | 改用 `core.refs.process_existing_references`/`split_wikilink`；`_build_ref_list` 用 `split_wikilink` 构建去重集合（346 行，少 29 行） |
| **commands/match.py** | 本地 `DOI_RE = re.compile(...)` 常量；`run_match` 无返回值 | `DOI_RE` 改为导入 `core.doi.PATTERN_DOI`；`run_match` 返回布尔值（`pt+pa+fe matched > 0`），目录缺失返回 `False` |
| **commands/cited_by.py** | 手写 wikilink 判断 | `_wikilink_doi` 改用 `core.refs.split_wikilink` |
| **core/__init__.py** | 无 refs 条目 | 新增 `refs` 模块说明（8 行） |
| **core/doi.py** | `PATTERN_SAFE_DOI` 无注释 | 新增【勿改】注释（14-18 行），说明全角 `￥` 为刻意设计（Obsidian 将 `/` 视为路径分隔符） |

**逐行一致（无变化）文件：** `config.py`、`commands/trash.py`、`commands/remove_doi.py`、`commands/archive.py`、`core/crossref_api.py`、`core/frontmatter.py`、`core/markdown_utils.py`、`core/obsidian_path.py`

### 关键变化

- **新增 `pdf2md-local`（离线本地转换）**：基于 pdfplumber 纯本地 PDF→Markdown，无需上传云端、适合涉密文档；自动段落合并（`_merge_paragraphs`）、表格转 Markdown（`_table_to_md`）、章节标题检测（`_detect_heading`），复用 `_process_md_content` 做 Crossref/PubMed frontmatter 增强，`ThreadPoolExecutor`（≤4 并发）处理。
- **新增 `rename-pdf`（PyMuPDF 重命名）**：优先取元数据 `dc:title`，无效则做首页排版分析（最大字号 + 上半页位置）提取标题；过滤垃圾标题（状态标记、学位后缀、机构、MSID、DOI 文本），清洗为合法文件名（≤250 字符）并处理重名；未安装 PyMuPDF 时提示 `pip install pymupdf`。
- **新增 `core/refs.py`**：把原先在 `pdf2md.py`、`crossref.py` 中重复的 wikilink 解析（`split_wikilink`）、去重规范化（`process_existing_references`）、DOI 集合构建（`build_existing_dois`）统一抽取；`markdown_graph.py`、`cited_by.py` 也改为复用，消除重复代码。
- **`pdf2md` 重构为小函数**：单一大 `_process_md_content` 拆分为 `_collect_all_dois`（DOI 收集 + sslocal URL 修复）、`_extract_pdf_text`、`_update_cited_by`、`_merge_new_dois`、`_pin_main_doi`；cited-by 的 `clippings_doi_set` 改为在整个批次开始前预计算并传入，避免逐文件重复扫描。
- **PDF 重处理逻辑升级**：发现 `完成_` 版本 PDF 时，先通过 `_build_clippings_index`/`_find_clippings_md` 在 `OBSIDIAN_ROOT` 下各 Vault 的 `Clippings` 中定位对应笔记（stem 归一化精确匹配或 SequenceMatcher ≥0.85 模糊匹配），执行 `run_match(force=True)` 补齐 PT/PA/FE 链接，成功后才把旧 PDF 移入 TRASH（替代 v1.0 的无条件移入）。
- **`run_match` 返回布尔值**：以“本次是否产生新的匹配”为返回值，供 `pdf2md`/`pdf2md-local` 的 TRASH 决策使用；目录缺失时返回 `False` 而非隐式 `None`。
- **`core/doi.py` 增加【勿改】注释**：明确 `PATTERN_SAFE_DOI` 中的全角 `￥` 是刻意设计而非笔误，用于区分“安全文件名形式”（含 `￥`）与“特殊引用”（含裸 `/`）。
- **无文件被移除**：v1.0 的全部 20 个文件在 v2.0 中均保留。
