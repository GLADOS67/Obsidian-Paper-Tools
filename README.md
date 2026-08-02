![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue) ![License](https://img.shields.io/badge/license-MIT-green)

**Author:** Li Kan <lik1453529@163.com>

---

# Obsidian-Paper-Tools 1.0 — 克雷瓦联合

> **克雷瓦联合 (Union of Krewo, 1385)** — 波兰与立陶宛的首次宪制联姻，仅靠一个君主的人格纽带便铺开了此后四百年的共主疆域。如本项目：以 CLI 为冠冕、commands 为咨政、config 为宪章，立下此后一切扩展的骨架。

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
> *— PDF-to-Markdown batch conversion · DOI citation graph · Crossref/PubMed API · note matching & archiving*

---

## Installation

**Prerequisites:** Python ≥ 3.10

```bash
pip install .
```

**External dependencies:**

- [MinerU](https://mineru.net) API token — required by `pdf2md`
- Recommended vault directory layout (see [Configuration](#configuration))

---

## Commands Overview

| Command | Description | 说明 |
| --- | --- | --- |
| `pdf2md` | MinerU PDF batch → Markdown + DOI enrichment | MinerU PDF 批处理 → Markdown + DOI 增强 |
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
│   └── obsidian_path.py   # Obsidian URI resolution
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

### 7. What is the difference between hardlink and copy in `archive`? / `archive` 命令的硬链接和复制有何区别？

`archive` tries `os.link()` (hardlink) first — zero extra disk space, but only works on the same volume. On failure, falls back to `shutil.copy2()`. Both preserve file metadata.

### 8. How to update cited-by data for existing notes? / 如何更新已有笔记的 cited-by 数据？

```bash
vaultools cited-by --path C:\Vault\Clippings
```

The command auto-skips files whose `cited_by_date` is < 30 days old. Use `--max` to control how many citing papers are fetched per file.

---

## License

MIT

---

---

**作者：** Li Kan <lik1453529@163.com>

# Obsidian-Paper-Tools 1.0 — 克雷瓦联合

> **克雷瓦联合 (1385)** — 波兰与立陶宛的首次宪制联姻，仅靠一个君主的人格纽带便铺开了此后四百年的共主疆域。如本项目：以 CLI 为冠冕、commands 为咨政、config 为宪章，立下此后一切扩展的骨架。

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
> *— PDF 批量转 Markdown · DOI 引用图谱 · Crossref/PubMed API · 笔记匹配与归档*

---

## 安装

**前置条件：** Python ≥ 3.10

```bash
pip install .
```

**外部依赖：**

- [MinerU](https://mineru.net) API token — `pdf2md` 命令必需
- 推荐的 Vault 目录结构（见[配置](#配置)）

---

## 命令概览

| 命令 | 说明 | Description |
| --- | --- | --- |
| `pdf2md` | MinerU PDF 批处理 → Markdown + DOI 增强 | MinerU PDF batch → Markdown + DOI enrichment |
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
│   └── obsidian_path.py   # Obsidian URI 解析
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

### 7. `archive` 命令的硬链接和复制有何区别？

`archive` 优先尝试 `os.link()`（硬链接）——不占额外磁盘空间，但仅限同一卷。跨卷时自动回退为 `shutil.copy2()`，并保留文件元数据。

### 8. 如何更新已有笔记的 cited-by 数据？

```bash
vaultools cited-by --path C:\Vault\Clippings
```

命令自动跳过 `cited_by_date` 距今不足 30 天的文件。使用 `--max` 控制每篇拉取篇数。

---

## 许可证

MIT
