# Obsidian-Paper-Tools

面向 `C:\Vault` 多 vault 的学术论文管理工具集：CLI 单入口 + `core` 共享库 + `commands` 业务编排 + `scripts` 双击 BAT。

## 1. 定位与边界

### 做什么

| 域 | 能力 |
| :--- | :--- |
| 入库 | PDF / PMID / DOI / 标题 → Markdown（MinerU API、本地 pdfplumber、EuropePMC 全文） |
| 加工 | Crossref / PubMed 元数据、DOI 引用图谱、PA / PT / FE 匹配、反向链接回填 |
| 维护 | 全库归属调谐、图片清理 / 恢复、归档、PDF 重命名、Unicode 符号规范化 |

### 不做什么

- 不生成笔记正文：PA / PT / FE 正文由 LLM 或人工产出，本工具只负责落位、校验与互链。
- 不修改 raw 层正文：`Clippings` 论文正文只读，仅 frontmatter 反向链接字段可写。
- 不内置 PDF 下载链：PDF 需先放入 `C:\Vault\PDF`。
- 不做并发多实例：没有进程锁，批量命令请串行运行。
- 不包含 wiki 索引 / 体检：本工具只维护论文层与 PA / PT / FE 关联。

## 2. 快速开始

### 2.1 运行前提

| 项 | 要求 |
| :--- | :--- |
| Python | ≥ 3.10 |
| 依赖 | 见 `pyproject.toml`：`requests` `pyyaml` `pdfplumber` `PyMuPDF` `curl_cffi` |
| MinerU token | `C:\ResearchFront\DATA\API\MinerU.txt`（`config.MINERU_TOKEN`） |
| 操作系统 | Windows（固定盘符路径、`C:\Vault` 容器、BAT 启动器） |
| 外部程序 | 无；PDF 下载由外部准备，本工具不依赖浏览器 CDP |

### 2.2 调用方式

```powershell
$env:PYTHONIOENCODING = 'utf-8'
$cli = "C:\ResearchFront\Claude\Obsidian-Paper-Tools\cli.py"

python $cli --help
python $cli pdf2md
python $cli pdf2md-local
python $cli pmce "10.1000/xyz" --path "C:\Vault\PENDING\Clippings"
python $cli match "C:\Vault\Sarcopenia"
python $cli markdown --path "C:\Vault\Sarcopenia"
python $cli reconcile --dry-run
```

项目按脚本目录运行，`sys.path[0]` 即工具根；`pyproject.toml` 的 `vaultools` 入口为可选安装方式。

### 2.3 BAT 启动器

`scripts/` 是启动器模板，复制到对应 vault / 容器根后双击：

| 目录 | 包含 | 部署位置 |
| :--- | :--- | :--- |
| `scripts/分库/` | `MarkDown` `MATCH` `PDF2MD` `PDF2MD-LOCAL` `PMCE` `RemoveDOI` `TRASH` | 各 vault 根 |
| `scripts/全库/` | `ARCHIVE` `CITEDBY` `CROSSREF` `RECONCILE` `RENAME_PDF` | `C:\Vault` 容器根 |
| `scripts/BLANK/` | 新建 vault 的空白骨架与单库启动器 | 复制为新的 vault 目录 |

BAT 通过命令行参数调用 `cli.py`，不依赖 stdout 变量行协议。

## 3. 代码地图

```
Obsidian-Paper-Tools\
├─ cli.py            # 唯一入口：argparse 注册 + 命令分发
├─ config.py         # 路径、并发基准、缓存路径、User-Agent
├─ core/             # 共享库：IO / DOI / frontmatter / 网络 / PDF / 契约
├─ commands/         # 子命令实现
├─ scripts/          # 双击 BAT 启动器模板
└─ pyproject.toml    # 依赖与可选入口
```

### 3.1 分层职责

| 层 | 职责 | 约束 |
| :--- | :--- | :--- |
| `cli.py` | 参数注册、命令分发、交互输入 | 新子命令必须同时改 `add_parser` 与 `handlers` |
| `config.py` | 通用路径、并发基准、缓存文件、请求头 | 标【勿改】的路径禁改；不在其它模块硬编码绝对路径 |
| `core/` | 可复用能力：IO、DOI、frontmatter、网络、PDF、相似度 | 不读 argparse、不打印业务进度 |
| `commands/` | 子命令业务编排 + 用户可见输出 | 通过 `core` 复用逻辑，避免各写一套 |
| `scripts/` | 环境准备 + 参数拼装 | 不含业务逻辑 |

### 3.2 core 模块索引

| 模块 | 职责 |
| :--- | :--- |
| `__init__.py` | vault 目录识别（`is_vault_dir` / `iter_vault_dirs`）、`try_copy`（优先硬链接） |
| `cache.py` | JSON 缓存、自动编码文本读取、安全读取、批量读取、共享并行 `map_parallel` |
| `doi.py` | DOI 规范化、断行修复、可信度审核、主 DOI 定位、wikilink 构造 |
| `frontmatter.py` | frontmatter 解析 / 序列化、标题取值、施引新鲜度、批量 DOI 收集 |
| `http.py` | requests 会话单例、站点礼貌延迟 |
| `markdown_utils.py` | 正文引用链接与图片格式清洗 |
| `mineru.py` | MinerU v4 API 客户端：申请上传、PUT 上传、轮询、下载 ZIP、产物定位、`content_list_v2.json` 解析 |
| `obsidian_path.py` | Obsidian URI / 普通路径 → 实际 `.md`，含模糊与全库兜底 |
| `pdf_extractor.py` | pdfplumber 文本 / DOI / 表格提取；本地 PDF → Markdown（段落合并、标题启发式、表格） |
| `refs.py` | wikilink 解析、stem 变体、DOI 引用集合、reference 去重、主 DOI 置顶 |
| `similarity.py` | 长度门控 + 长度分桶，减少无效模糊匹配候选 |
| `title_cache.py` | DOI ↔ 标题持久化缓存 + 内存反向索引（精确 / 模糊） |
| `web_services.py` | Crossref 标题→DOI、DOI→参考文献；PubMed 施引查询与 frontmatter 写回 |

### 3.3 命令模块索引

| 模块 | 命令 |
| :--- | :--- |
| `pdf2md.py` | `pdf2md` / `pdf2md-local` |
| `pmce.py` | `pmce` |
| `markdown_graph.py` | `markdown` |
| `crossref.py` | `crossref` |
| `cited_by.py` | `cited-by` |
| `match.py` | `match` |
| `reconcile.py` | `reconcile` |
| `archive.py` | `archive` |
| `clean_images.py` | `clean-images` |
| `trash.py` | `trash` |
| `remove_doi.py` | `remove-doi` |
| `rename_pdf.py` | `rename-pdf` |
| `unify_symbols.py` | `unify-symbols` |

## 4. 数据契约

### 4.1 容器与 vault

`C:\Vault` 是容器根：每个 `C:\Vault\<主题>\` 是独立 Obsidian vault。

```
C:\Vault\
├─ <vault>\
│  ├─ Clippings\        # raw 层：论文 MD（只读）
│  ├─ Claude\           # PA / FE 笔记
│  ├─ Chi\              # PT 译文
│  └─ *.bat             # 从 scripts/分库/ 复制的启动器
├─ IMAGE\               # 共享图片目录
├─ PDF\                 # pdf2md 的 PDF 输入
├─ ZIP\                 # MinerU 产物归档 / 图片恢复源
├─ PENDING\             # pmce / pdf2md 的暂存落点
└─ TRASH\               # 回收站
```

### 4.2 笔记类型

| 类型 | 判定 |
| :--- | :--- |
| source | 路径含 `Clippings` |
| PA | 其余 `Claude\` 下笔记 |
| FE | stem 以 `_figures` 结尾 |
| PT | 父目录名 `Chi` 或 stem 含 `zh-CN` |

### 4.3 常用 frontmatter 字段

| 字段 | 含义 |
| :--- | :--- |
| `title` | 论文标题 |
| `doi` | 主 DOI |
| `reference` | 引用 wikilink 列表，`reference[0]` 为主 DOI |
| `cited_by` | 施引论文 DOI wikilink 列表 |
| `cited_by_date` | 施引查询日期；30 天内视为新鲜 |
| `paper-analyze` | PA 笔记反向链接 |
| `paper-translate` | PT 笔记反向链接 |
| `figure-extractor` | FE 笔记反向链接 |
| `被引` | 本文被哪些笔记引用（`markdown` 回写） |
| `特殊引用数` | 特殊引用计数（`markdown` / `pmce` 维护） |
| `tags` | 正 / 负向标签（`markdown` 回写） |
| `aliases` | 别名列表 |

### 4.4 DOI 与引用口径

- DOI 统一走 `core.doi.process_doi`；`￥` 是 DOI 的安全文件名形态，不是错误字符。
- 主 DOI 定位顺序：frontmatter `doi` → 正文 `DOI:` 行 → 正文首个可信 DOI。
- `is_plausible_doi` 是全项目唯一可信度闸门，过滤纯字母后缀、超长、双 DOI、统计区间等。
- `reference[0]` 为 `[[标题|主DOI]]`；`pin_main_doi` 负责去重并置顶。
- `cited_by_date` 距今小于 30 天时跳过重复查询；`apply_cited_by` 统一写入日期与列表。

### 4.5 raw 层约束

`Clippings` 正文只读。`match` 只回填 `paper-analyze` / `paper-translate` / `figure-extractor`；`markdown` 只重写引用与被引相关字段。

## 5. 命令参考

通用约定：`--dry-run` 为预览，`--force` 才落盘；`reconcile` 与 `unify-symbols` 默认 dry-run。

### 5.1 入库链

#### `pdf2md`

MinerU API 批量 PDF → Markdown，并补全参考文献与施引。

关键参数：

| 参数 | 说明 |
| :--- | :--- |
| `--path_pdf` | PDF 输入目录（默认 `C:\Vault\PDF`） |
| `--path_zip` | MinerU 产物 ZIP 归档目录 |
| `--path_md0` | Markdown 输出目录 |
| `--path_images` | 图片输出目录 |
| `--cited_by_max` | 最多写入多少篇施引 |
| `--ref_max_age` | 参考文献时效上限（年） |

流程：历史完成迁移 → 申请上传链接 → 上传 → 轮询批次 → 下载 ZIP → 解压 → 移 MD / 拷图 → DOI 定级 → 参考文献 / cited-by 补全 → 标记 `完成_*.pdf`。

#### `pdf2md-local`

本地 pdfplumber 转换，不调用 MinerU；识别到 DOI 时仍可能联网补全参考文献 / 施引。

参数与 `pdf2md` 类似，但没有 `--path_zip`；`--path_images` 在本地 pdfplumber 路径不产生图片。适合 MinerU 不可用或 PDF 不便上传的场景；复杂分栏 / 表格 / 图片效果弱于 MinerU。

#### `pmce`

`PMID` / `DOI` / 标题 → EuropePMC 全文 → `Clippings\PENDING`。

关键参数：

- `--path`：目标 `Clippings\PENDING` 目录（必填）
- `--no-graph`：跳过收尾的引用图谱重建
- `--dry-run`：只解析与打印非 OA，不写 MD

流程：输入解析 → EuropePMC 元数据 → OA 条目抓取 JATS 全文并预取 PMC 页面图 URL → 解析为 Markdown → 非 OA 打印 DOI / 标题 → 收尾重建引用图谱并把 `reference[0]` 置为 `[[标题|DOI]]`。

### 5.2 图谱与匹配

#### `markdown`

建立 / 更新 DOI 引用图谱，回写去重后的 `reference`、`cited_by`、`被引`、`tags`。

- `--path`：扫描根目录（必填）
- `--depth`：0 仅 vault 级统计；大于 0 按文件夹输出引用战报

#### `crossref`

标题 ↔ DOI、参考文献拉取 / 接管。`input` 省略时进入交互循环。

输入文法：

- `路径`：处理 Markdown / PDF
- `￥路径`：全面接管，清空旧引用后按标题搜索 DOI 重建
- `local:路径 [doi:目标DOI]`：处理正文参考文献段
- `doi:DOI`：拉取该 DOI 的参考文献并导入指定笔记

#### `cited-by`

PubMed 施引查询并写回 frontmatter。

- `--path`：`.md` 文件或目录；`-` 为交互输入
- `--max`：最多取回篇数（默认 10）

#### `match`

PA / PT / FE 三向匹配，回填论文端反向链接。

- `base_dir`：vault 根（需含 `Clippings` 与 `Chi`）
- `--dry-run`：只预览
- `--threshold`：Jaccard 阈值（默认 0.85）
- `--force`：覆盖已有反向链接
- `-v`：打印失败候选
- `--trash`：额外扫描 `TRASH\Claude` 并做归属调谐

#### `reconcile`

全库 PA / FE / PT 归属调谐到正确 vault 或 `TRASH`。

- 默认 dry-run
- `--force` 才执行移动
- 未匹配到归属的笔记移入 `TRASH\Claude\<vault>`；目标重名时也移入 `TRASH`

### 5.3 归档与维护

#### `archive`

归档 Clippings 论文及其 PA / PT / FE 关联笔记。`-s` 源文件、`-t` 目标目录均必填。

#### `clean-images`

扫描全库 Markdown，把 `IMAGE` 中未被引用的图片移入 `TRASH\Image`。

#### `trash`

归档指定目录下的子目录，并做图片清理 / 从 ZIP 恢复缺失图片。

#### `remove-doi`

删除目录树中包含指定 DOI wikilink 的整行。`--path` 必填，`--doi` 省略时交互输入。

#### `rename-pdf`

按 PyMuPDF 提取的标题重命名 PDF；跳过 `完成_*`，重名自动追加 ` (n)`。

#### `unify-symbols`

文件名与 wikilink 的 Unicode 符号规范化。默认 dry-run，`--force` 才落盘；先改链接，再重命名文件。

## 6. 主链路

```
入库：
  PDF            → pdf2md / pdf2md-local → Markdown
  PMID/DOI/标题  → pmce                 → EuropePMC 全文 Markdown
  归库：PENDING\Clippings → archive → <vault>\Clippings
  副作用：pdf2md 自动补参考文献 / 施引；pmce 收尾重建图谱并置顶主 DOI

加工：
  LLM / 人工写 PA / FE / PT → match 回填反向链接
  crossref / cited-by / markdown 补全引用与被引

维护：
  reconcile 归属调谐
  clean-images / trash 图片清理与恢复
  unify-symbols / rename-pdf 命名规范化
```

## 7. 接口契约

### 7.1 退出码

`cli.py` 正常结束返回 0（除非 `SystemExit`）。`reconcile` / `unify-symbols` 的布尔返回值不会透传为退出码，不能用退出码判断是否实际执行。

### 7.2 写盘

`commands/` 直接使用 `Path.write_text(encoding='utf-8')` 写 Markdown。批量改写前建议先备份 vault。frontmatter 一律通过 `core.frontmatter.dump_frontmatter` 重组，不要手工拼 `---` 头。

### 7.3 并发

没有进程级锁与队列；`pdf2md`、`pmce`、`match`、`reconcile` 不要并发运行。`core.cache.map_parallel` 只用于单进程内的批量 IO；`markdown_graph` / `match` 内部的线程锁只保护共享 map。

## 8. 修改指引

| 需求 | 落点 |
| :--- | :--- |
| 新增子命令 | `cli.py`：`add_parser` + `handlers` 注册；实现放 `commands/<name>.py` |
| 改路径 / 并发基准 / 缓存位置 | `config.py` |
| 改 DOI 规范化与可信度口径 | `core/doi.py` |
| 改 wikilink / reference 文法 | `core/refs.py` |
| 改 frontmatter 解析 / 序列化 / 施引写回 | `core/frontmatter.py` |
| 改远程服务 | `core/web_services.py`；会话与延迟走 `core/http.py` |
| 改本地 PDF 提取 / 转 MD | `core/pdf_extractor.py` |
| 改 MinerU 协议 | `core/mineru.py` |
| 改 BAT 启动器 | `scripts/` 模板；改后同步已部署副本 |

### 硬约束

- 不在其它模块硬编码绝对路径，统一走 `config.py`。
- 不修改 `Clippings` 正文，只允许写反向链接字段。
- 不把 `￥` 当成错误字符；它是 DOI 的安全文件名形态。
- 不改 CLI 参数名与 `dest`；frontmatter 字段名冻结。
- 不并发运行同一批入库 / 调谐命令。

## 9. 配置与缓存

| 配置 | 说明 |
| :--- | :--- |
| `OBSIDIAN_ROOT` | `C:\Vault` 容器根 |
| `DEFAULT_PDF_PATH` | `C:\Vault\PDF` |
| `DEFAULT_ZIP_PATH` | `C:\Vault\ZIP` |
| `DEFAULT_MD_PATH` | `C:\Vault\PENDING\Clippings` |
| `DEFAULT_IMAGE_PATH` | `C:\Vault\IMAGE` |
| `DOI_TITLE_CACHE` | DOI ↔ 标题缓存 JSON |
| `CITE_BY_CACHE` | PubMed 施引缓存 JSON |
| `MINERU_TOKEN` | MinerU API token 文件 |

缓存可删除重建，但会丢失加速；删除前确认没有正在运行的任务。

## 10. 已知限制

- Windows 专用：固定盘符, `C:\Vault` 容器, BAT 启动器。
- PDF 需预先放入 `C:\Vault\PDF`；本工具不负责下载 PDF。
- 本地转换使用 pdfplumber；复杂版式、图表、扫描件效果弱于 MinerU。
- 不包含 wiki 索引 / 体检与 PA 自动队列。
- 没有自动化测试；改动后请先在副本 vault 上运行 `--dry-run`。
- 写盘非原子；批量操作前备份。

## 11. 代码约定

新增代码沿用现有风格：

- Python 模块 / 函数 / 变量使用 `snake_case`；类使用 `PascalCase`；模块级常量使用 `UPPER_SNAKE`。
- 正则常量以 `_RE` 结尾；纯函数优先加 `lru_cache`，但不得让调用方依赖返回值的可变性。
- 目录参数用 `dir_path`，路径用 `path` / `md_path`，标题用 `title`；避免 `l` 等歧义单字母。
- `core/` 不读 argparse、不打印业务进度；进度与用户输出放 `commands/`。
- 注释解释“为什么”，不复述代码；契约、边界、副作用写在模块与函数 docstring 中。
- CLI 参数名、`argparse` 的 `dest`、frontmatter 字段名属于冻结契约，改名必须同步调用方与 BAT。

## 12. 执行与排错

1. 先设编码：`$env:PYTHONIOENCODING = 'utf-8'`。
2. 先预览：`reconcile` / `unify-symbols` 默认 dry-run；`match` 用 `--dry-run` 先看匹配结果。
3. 退出码不等于业务成功：`cli.py` 通常以 0 结束，不要用 `if errorlevel` 判断 `reconcile` 是否执行。
4. 单实例：不要并发运行 `pdf2md`、`pmce`、`match`、`reconcile`。
5. 写盘前备份：批量改写 frontmatter 或移动文件前，先复制 vault 或至少备份 `Clippings` 与 `TRASH`。
6. 缓存排错：`Doi_Title_cache.json` / `Cite_By_cache.json` 损坏或缺失时，相关命令会退化为联网或空缓存；删除缓存可重建，但会丢失加速。
7. 回归检查：`python cli.py --help`、`python -m compileall -q .`，再在副本 vault 上跑一次 `match --dry-run` 与 `markdown`。
