![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue) ![License](https://img.shields.io/badge/license-MIT-green)

**Author:** Li Kan <lik1453529@163.com>

---

# Obsidian-Paper-Tools 2.2 — 卢布林合并

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
> *— Cloud & local PDF-to-Markdown · DOI citation graph · Crossref cache cleaner · PubMed API · PyMuPDF rename · note matching & archiving*

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
├── cli.py                 # Entry point (argparse) / 入口
├── config.py              # Global path constants / 全局路径常量
├── clean_cache.py         # Crossref cache cleaner / Crossref 缓存清洗
├── pyproject.toml
├── commands/
│   ├── pdf2md.py          # MinerU batch pipeline / 批处理管道
│   ├── rename_pdf.py      # PyMuPDF title rename / 标题重命名
│   ├── markdown_graph.py  # DOI citation graph builder / DOI 引用图谱
│   ├── crossref.py        # Crossref reference tool / Crossref 参考文献
│   ├── match.py           # PA/PT/FE matcher / PA/PT/FE 匹配器
│   ├── trash.py           # Directory archiver / 目录归档
│   ├── remove_doi.py      # DOI removal / DOI 移除
│   ├── cited_by.py        # PubMed cited-by query / PubMed cited-by
│   └── archive.py         # Vault-to-vault archiver / Vault 间归档
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

# Obsidian-Paper-Tools 2.2 — 卢布林合并

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
> *— 云端与本地 PDF 转 Markdown · DOI 引用图谱 · Crossref 缓存清洗 · PubMed API · PyMuPDF 重命名 · 笔记匹配与归档*

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
├── clean_cache.py         # Crossref 缓存清洗
├── pyproject.toml
├── commands/
│   ├── pdf2md.py          # MinerU 批处理管道
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

### 7. `pdf2md`（云端）和 `pdf2md --local` 有什么区别？

`pdf2md` 将 PDF 上传至 MinerU 云端 API — 质量最优，支持复杂公式和内嵌表格。`pdf2md --local`（或 `pdf2md-local`）使用 pdfplumber 在本地离线转换 — 数据不离开本机，适合涉密文档，表格转为 Markdown，公式提取为纯文本。

### 8. `rename-pdf` 如何提取标题？

首先尝试 PDF 元数据 (`dc:title`)。若为无效或缺失，则回退到首页排版分析：在页面上半部分识别最大字号文本块，过滤无效标题（Untitled、状态标记、学位后缀），清洗为安全文件名（≤250 字符，无特殊字符）。需要 `pip install pymupdf`。

---

## 许可证

MIT

---

## 增量对比 (vs v2.1)

v2.1 → v2.2 对 `*.py`、`*.toml`、`*.md` 文件逐行对比结果。**无新增文件、无移除文件**；20 个 Python 文件中 7 个逐字一致（`config.py`、`commands/remove_doi.py`、`commands/trash.py`、`commands/__init__.py`、`core/markdown_utils.py`、`core/obsidian_path.py`、`core/__init__.py`），`pyproject.toml` 逐字一致。核心主题：**文献年代闸门（`ref_max_age`）**、公共 DOI/wikilink 工具函数下沉复用。

| 维度 | v2.1 | v2.2 |
| --- | --- | --- |
| **新增文件** | — | 无 |
| **移除文件** | 无 | — |
| **commands/pdf2md.py** | 顺序上传；无条件添加 reference/cited_by；内置 Clippings 模糊匹配索引；内联 DOI→wikilink 转换 | 新增 `--ref_max_age`（默认15年）「首发日期闸门」：老论文只钉主 DOI 不膨胀引用；上传改 `ThreadPoolExecutor(max_workers=5)` 并行；删除 Clippings 模糊匹配索引（约50行）；复用 `find_plausible_dois`/`new_doi_wikilinks`/`cited_by_fresh`/`doi_wikilink` |
| **commands/cited_by.py** | 内联 freshness 检查 + 内联 DOI→wikilink 构建 | 改用 `cited_by_fresh()` 与 `doi_wikilink()`；`_get_main_doi_from_md` 改用 `doi_from_doi_line()`；移除 `timedelta` 导入 |
| **commands/crossref.py** | 内联引用 wikilink 循环；重复构建翻译表 | `_build_ref_list` 改用 `new_doi_wikilinks()`；提取模块级 `_DASH_TABLE`；PDF/正文 DOI 提取改用 `find_plausible_dois`/`doi_from_doi_line` |
| **commands/markdown_graph.py** | `Slot`/`DoiEntry` 元组结构；`_process_references`+`_resolve_refs_final` 双函数 | `DoiEntry` 改为 `List`+dict 型 stems；合并为单一 `_rebuild_reference_list()`（支持可选 `citing_stem` 最终解析）；`_update_doi_map` 改用 dict 去重；删除 `_resolve_refs_final` |
| **commands/match.py** | 无条件计算 `clip_dois` | `run_match` 返回类型 `None`→`bool`；`clip_dois` 惰性计算（仅在 jaccard 兜底分支需要时提取） |
| **commands/archive.py** | `PATTERN_IMG_ABS` + `PATTERN_IMG_REL` 双正则两次替换 | 合并为单一 `PATTERN_IMG`（绝对/相对路径二选一），单次 `.sub` 替换 |
| **commands/rename_pdf.py** | 每个字号循环内重复过滤上半页 | 提前提取 `top_spans`（y<0.55 页高），循环复用（等效性能微优化） |
| **core/doi.py** | 内联 re.sub 清理；散落各处重复的「筛选+plausible 判定」逻辑 | 新增 `find_plausible_dois()`、`doi_from_doi_line()`、`doi_wikilink()`；清理正则预编译为 `_RE_URL_SPLIT`/`_RE_ID_TAIL`/`_RE_YEAR_OR_DOTS_TAIL` |
| **core/refs.py** | 仅 wikilink 解析/去重工具 | 新增 `new_doi_wikilinks(dois, seen)` 统一「DOI→去重→wikilink」；删除文档字符串；引入 `process_doi` 依赖 |
| **core/frontmatter.py** | 无 freshness 工具 | 新增 `cited_by_fresh(fm, days=30)`（原散落在 pdf2md.py/cited_by.py 内联逻辑上收） |
| **core/crossref_api.py** | 仅参考文献/引用计数 | 新增 `get_issued_year()`/`_extract_issued_year()`，缓存键 `issued:{doi}`；`fetch_references` 顺带复用同一响应写入年份缓存，避免二次请求 |
| **clean_cache.py** | `_should_keep_doi` 过滤 + 内联清洗 | 删除 `_should_keep_doi`/`DOI_PREFIX_RE`；`_clean_doi_key` 简化为 `process_doi(raw)[0]`；`shutil` 上提至顶层 |
| **cli.py** | 无 `--ref_max_age`；`_cmd_remove_doi` 用 else 打印 | 新增 `--ref_max_age`（默认15）并透传两个 pdf2md 命令；`_cmd_remove_doi` 改 early-return；移除未用 `Path` 导入 |
| **README.md** | 含「增量对比 (vs v2.0)」章节 | 删除 v2.0 对比章节；新增强化描述（`--ref_max_age`）；本文档末尾追加 (vs v2.1) 对比 |
| **pyproject.toml** | — | 逐字一致 |
| **config.py / core/markdown_utils.py / core/obsidian_path.py / commands/remove_doi.py / commands/trash.py / commands/__init__.py / core/__init__.py** | — | 逐字一致（7 个） |

### 关键变化

- **文献年代闸门（核心新特性）**：`pdf2md` 新增 `--ref_max_age`（默认 15 年）。主 DOI 首发年份距今超过阈值时仅钉住主 DOI，跳过 `_merge_new_dois` 与 Crossref 参考文献追加，避免老文献引用膨胀；年份通过 `core/crossref_api.get_issued_year()` 获取，`fetch_references` 已顺带缓存同响应中的年份，免二次请求。
- **上传并行化**：MinerU 批次上传由顺序 for 循环改为 `ThreadPoolExecutor(max_workers=5)` + `_upload_one` 辅助函数。
- **公共工具下沉**：`find_plausible_dois`/`doi_from_doi_line`/`doi_wikilink`（core/doi.py）、`new_doi_wikilinks`（core/refs.py）、`cited_by_fresh`（core/frontmatter.py）将原散落在 pdf2md.py/cited_by.py/crossref.py/markdown_graph.py 的内联逻辑集中复用。
- **markdown_graph 重构**：`_process_references` + `_resolve_refs_final` 合并为单一 `_rebuild_reference_list()`，`DoiEntry` 由元组结构改为 List+dict（去重键字典化），减少重复遍历。
- **清理与精简**：pdf2md.py 删除 Clippings 模糊匹配索引（约 50 行）；archive.py 双图片正则合并；match.py 惰性计算 DOI 集合；clean_cache.py 移除 `_should_keep_doi`；cli.py 增加 early-return。
