# Obsidian-Paper-Tools

面向 `C:\Vault` 多 vault 的学术论文管理工具集。`cli.py` 是唯一命令行入口，`core/` 放可复用能力，`commands/` 放业务编排，`scripts/` 放双击启动器，`skill_scripts/` 放供 LLM 技能调用的单文件脚本。

## 1. 定位与边界

### 做什么

| 域 | 能力 |
| :--- | :--- |
| 入库 | PDF → Markdown（MinerU 云端批处理 / 本地 pdfplumber）；PMID、DOI、标题 → EuropePMC OA 全文 Markdown |
| 检索 | PubMed 关键词检索、OpenAlex / EuropePMC 高引用检索，输出表格与 PMCE 输入块 |
| 加工 | Crossref 参考文献、PubMed 施引、DOI 引用图谱、Clippings 与 PA / PT / FE 三向匹配及反向链接回填 |
| 初始化 | 为论文计算 PA / FE / PT 落点与临时目录，写入 frontmatter 占位字段；论文与笔记互链由 `link_note_to_paper` 完成 |
| 维护 | 全库归属调谐、未引用图片清理与 ZIP 恢复、论文及派生笔记归档、PDF 按标题重命名、Unicode 符号规范化 |

### 不做什么

- 不生成 PA / PT / FE 笔记正文：正文由 LLM 或人工撰写，本工具只负责落位、匹配、互链与字段维护。
- 不改 `Clippings` 论文正文：只写 frontmatter 中的 DOI、引用、反向链接与标签字段。
- 不下载 PDF：PDF 需事先放入 `C:\Vault\PDF`；也不抓取非 OA 全文，非 OA 条目只打印 DOI 与标题。
- 不做多实例保护（没有进程锁与任务队列，批量命令请串行运行），也不做知识库索引、站点体检、浏览器下载链；没有自动化测试与回滚，没有 GUI，写盘直接覆盖，批量操作前请自行备份 vault。

## 2. 快速开始

### 2.1 运行前提

| 项 | 要求 |
| :--- | :--- |
| Python | ≥ 3.10 |
| 依赖 | 见 `pyproject.toml`：`curl_cffi` `pyyaml` `requests` `pdfplumber` `PyMuPDF` |
| MinerU token | `C:\ResearchFront\DATA\API\MinerU.txt`（`config.MINERU_TOKEN`） |
| 操作系统 | Windows（固定盘符路径、`C:\Vault` 容器、BAT 启动器） |
| 外部程序 | 无；PDF 由外部准备，工具不依赖浏览器或 Node.js |

`cli.py` 在顶部一次性导入全部 `commands.*`，因此连 `--help` 也会加载 `requests` / `pdfplumber` / `fitz` / `curl_cffi`；缺任一依赖时任何子命令都无法启动。项目按脚本目录运行，`sys.path[0]` 即工具根；`pyproject.toml` 的 `vaultools` 入口只是可选安装方式，`build-backend` 非标准，`pip install .` 可能失败。

### 2.2 调用方式

```powershell
$env:PYTHONIOENCODING = 'utf-8'
$cli = "<工具根>\cli.py"

python $cli --help
python $cli pdf2md
python $cli pdf2md-local
python $cli pmce "10.1000/xyz" --path "C:\Vault\PENDING\Clippings"
python $cli markdown --path "C:\Vault\<vault>" --depth 1
python $cli match "C:\Vault\<vault>" --dry-run
python $cli crossref "10.1000/xyz"
python $cli reconcile
python $cli unify-symbols --vault "C:\Vault"
```

### 2.3 BAT 启动器

`scripts/` 是启动器模板，本身不含业务逻辑，只拼参数调用 `cli.py`。

| 目录 | 文件 | 部署位置 |
| :--- | :--- | :--- |
| `scripts/全库/` | `ARCHIVE` `CITEDBY` `CROSSREF` `RECONCILE` `RENAME_PDF` | `C:\Vault` 容器根 |
| `scripts/分库/` | `MarkDown` `MATCH` `PDF2MD` `PDF2MD-LOCAL` `PMCE` `RemoveDOI` `TRASH` | 各 vault 根 |
| `scripts/BLANK/` | `MarkDown` `MATCH` `PDF2MD` `PDF2MD-LOCAL` `PMCE` `RemoveDOI` `RENAME_PDF` `TRASH` | 新建 vault 的启动器骨架 |

- 所有 BAT 都写死调用 `C:\ResearchFront\Claude\Obsidian-Paper-Tools\cli.py`；部署到其它目录时必须先改这一行，否则调用的是另一份检出。
- 都用 Windows Terminal 新窗口运行：已有 `WT_SESSION` 时直接执行，否则尝试 `wt.exe -w new cmd /c`，失败则退回当前窗口。
- `分库/` 用 `%~dp0` 推导 vault 根：`MarkDown` 指向 `<vault>\Clippings` 并带 `--depth 1`；`PDF2MD` / `PDF2MD-LOCAL` / `PMCE` 指向 `<vault>\Clippings\PENDING`；`RemoveDOI` 指向 `<vault>\Clippings`；`MATCH` 与 `TRASH` 直接用 vault 根。`PDF2MD` / `PDF2MD-LOCAL` 只覆盖 `--path_md0`，PDF 输入仍取默认 `C:\Vault\PDF`；`PMCE` 与 `MATCH` 用 `%*` 透传额外参数。
- `全库/ARCHIVE` 循环询问源文件与目标目录，输入 `q` 退出；`RECONCILE` 先跑 dry-run，再询问 `y` 才追加 `--force`；`RENAME_PDF` 固定处理 `C:\Vault\PDF`。
- 除 `TRASH` 外都执行 `chcp 65001`；多数脚本以 `timeout` 或 `pause` 停留窗口，`ARCHIVE` / `RECONCILE` 直接结束，没有 stdout 变量协议。

## 3. 代码地图

```
Obsidian-Paper-Tools\
├─ cli.py            # 唯一入口：argparse 注册 + 命令分发表
├─ config.py         # 路径、并发基准、缓存路径、请求头
├─ core\             # 共享库：13 个 Python 文件（含 __init__.py）
├─ commands\         # 13 个命令模块 + 空 __init__.py
├─ scripts\          # 20 个双击 BAT 启动器
│  ├─ 全库\          # 5 个跨库脚本
│  ├─ 分库\          # 7 个单库脚本
│  └─ BLANK\         # 8 个新库骨架脚本
├─ skill_scripts\    # 4 个技能入口脚本 + 1 个共享模块
└─ pyproject.toml    # 依赖与可选入口
```

### 3.1 分层职责

| 层 | 职责 | 约束 |
| :--- | :--- | :--- |
| `cli.py` | 参数注册、命令分发、少量交互输入 | 新子命令必须同时改 `add_parser` 与 `handlers` |
| `config.py` | 通用路径、并发基准、缓存文件、请求头 | 标【勿改】的路径禁改；其它模块不硬编码绝对路径 |
| `core/` | 可复用能力：IO、DOI、frontmatter、网络、PDF、相似度 | 不读 argparse；少数模块会打印网络或提取错误 |
| `commands/` | 子命令业务编排、用户可见输出、写盘 | 通过 `core` 复用逻辑，不重复实现 DOI 与 frontmatter 处理 |
| `scripts/` | 环境准备与参数拼装 | 不含业务逻辑 |
| `skill_scripts/` | 技能侧单文件入口与共享工具 | 入口脚本统一先 `import skill_common` 再注入工具根；共享模块与脚本按硬连接同步 |

`commands/pdf2md.py` 的 MinerU 协议已拆到 `core/mineru.py`：上传申请、PUT 上传、轮询、下载、解压产物定位、`content_list_v2.json` 解析都由该模块完成，`pdf2md.py` 只做批次编排与后处理。

## 4. core 模块索引

| 模块 | 职责 |
| :--- | :--- |
| `__init__.py` | vault 目录识别（`is_vault_dir` / `iter_vault_dirs`）、`try_copy`（优先硬链接，失败退回复制） |
| `cache.py` | JSON 缓存读写（紧凑序列化）、自动编码文本读取、安全读取、批量读取、共享线程池 `map_parallel` |
| `doi.py` | DOI 规范化、断行修复、可信度审核、主 DOI 定位、wikilink 构造、标题规范化 |
| `frontmatter.py` | frontmatter 解析 / 序列化、标题取值、`source_key`、施引新鲜度、施引写回、批量 DOI 收集 |
| `http.py` | requests 会话单例、站点礼貌延迟 |
| `markdown_utils.py` | 正文链接、图片与 PDF 伪影清洗 |
| `mineru.py` | MinerU 云端 API：申请上传链接、PUT 上传、轮询批次、下载 ZIP、产物定位、JSON 解析与主 DOI 候选 |
| `obsidian_path.py` | `obsidian://` URI / 普通路径 → 实际 `.md`，含同目录模糊与全库兜底 |
| `pdf_extractor.py` | pdfplumber 文本 / DOI / 表格提取；本地 PDF → Markdown（段落合并、标题启发式、表格） |
| `refs.py` | wikilink 解析、stem 变体、DOI 引用集合、reference 去重、主 DOI 置顶 |
| `similarity.py` | 长度门控 + 长度分桶，减少无效模糊匹配候选 |
| `title_cache.py` | DOI ↔ 标题持久化缓存 + 内存反向索引（精确 / 模糊，不发 API） |
| `web_services.py` | Crossref 标题→DOI、DOI→参考文献；PubMed 施引；OpenAlex 元数据与在线标题验证 |

## 5. commands 模块索引

| 模块 | 命令 | 一句话职责 |
| :--- | :--- | :--- |
| `pdf2md.py` | `pdf2md` / `pdf2md-local` | MinerU 云端批量转换与本地 pdfplumber 转换，含 DOI / 参考文献 / 施引补全 |
| `pmce.py` | `pmce` | PMID / DOI / 标题 → EuropePMC OA 全文 Markdown |
| `markdown_graph.py` | `markdown` | 建立 DOI 引用图谱，回写 `reference` `cited_by` `被引` `tags` |
| `crossref.py` | `crossref` | 四种输入文法的 Crossref 参考文献工具 |
| `cited_by.py` | `cited-by` | PubMed 施引查询并写回 frontmatter |
| `match.py` | `match` | Clippings ↔ PT / PA / FE 匹配，回填反向链接 |
| `reconcile.py` | `reconcile` | 全库 PA / PT / FE 归属调谐 |
| `archive.py` | `archive` | 归档论文及其 PA / PT / FE 笔记到目标 vault |
| `clean_images.py` | `clean-images` | 未引用图片移入 `TRASH\Image` |
| `trash.py` | `trash` | 图片清理 / ZIP 恢复 + 子目录按日期归档 |
| `remove_doi.py` | `remove-doi` | 删除含指定 DOI wikilink 的整行 |
| `rename_pdf.py` | `rename-pdf` | PyMuPDF 提取标题后重命名 PDF |
| `unify_symbols.py` | `unify-symbols` | 文件名与 wikilink 的 Unicode 符号规范化 |
| `__init__.py` | — | 空文件，无逻辑 |

## 6. skill_scripts 索引

四个入口脚本都是独立命令：先 `import skill_common as _sc`，由 `_sc.bootstrap_tool_root()` 在检测到上级存在 `commands/` 时把工具根插入 `sys.path`，再使用 `_sc.make_session`、`_sc.fmt_md_table`、`_sc.fmt_pmce`、`_sc.die`。脚本与 `skill_common.py` 都按硬连接同步到技能目录；只复制其中一个脚本而漏掉 `skill_common.py` 会直接导入失败。

| 脚本 | 输入 / 参数 | 输出与用途 |
| :--- | :--- | :--- |
| `high_cited.py` | `--query`（逗号分块：主题词搜摘要，后续块搜标题，用竖线分隔同义词，空格词加引号）、`--source`（`openalex` / `europepmc` / `auto`）、`--retmax`（默认 `20`）、`--years`、`--min-cited`、`--format`（`md` / `json` / `pmce`） | 按真实引用数降序的 Markdown 表格 + PMCE 输入块，或 JSON；`auto` 先走 OpenAlex，失败降级 EuropePMC，EuropePMC 取回后由客户端排序 |
| `init_paper.py` | 普通路径 / `obsidian://` / `file:///`；至少一个 `--pa` / `--fe` / `--pt`；`--dry-run` | 单行 JSON：`shared`（vault 根、论文路径、标题、创建目录）、`pa` / `fe` / `pt` 落点、`pending_frontmatter_fields` 或 `error`；只建目录与 frontmatter 占位，不写笔记正文 |
| `link_note_to_paper.py` | `target`、`source`、可选 `alias`；`--replace` / `--replace-field` / `--dry-run` | 在笔记 frontmatter 后插入 `[[source]]`，有别名时以竖线分隔；`--replace` 把 `<!-- RELINK_HERE -->` 换成 `# [[...]]` 并精简 frontmatter，`--replace-field` 填指定字段；成功 `done:`，失败 `missing:` / `RELINK_HERE not found`，退出码 `1` |
| `pubmed_search.py` | `--query` 成型检索式、`--retmax`（默认 `20`）、`--mindate` / `--maxdate` / `--datetype`、`--sort`、`--format`、`--pmce-out`、`--usehistory` | PubMed 元数据表 + PMCE 输入块，或 JSON；`--pmce-out` 可直接喂给 `pmce`。固定一次 `esearch` + 每批 `200` 个 PMID 的 `efetch`，请求间隔约 `0.34` 秒，限流退避重试一次 |

`skill_common.py` 提供五个公共函数：

| 函数 | 职责 |
| :--- | :--- |
| `bootstrap_tool_root()` | 脚本位于工具 `skill_scripts` 下时，把工具根插入 `sys.path[0]`；技能路径下不注入 |
| `make_session(user_agent)` | 构造带指定 `User-Agent` 的 `requests.Session` |
| `fmt_md_table(header, rows)` | 输出 Markdown 表格：表头 + `:---` 分隔行 + 数据行，并对单元格内的竖线做转义 |
| `fmt_pmce(entries)` | 输出 PMCE 输入块：有 DOI 用 DOI，缺 DOI 用 `PMID: <pmid>` |
| `die(message)` | 错误写入 stderr 并以状态码 `1` 退出 |

`init_paper.py` 的 `obsidian://` 解析固定拼到 `C:\Vault\<vault>`；`high_cited.py` 直连失败时降级到 PowerShell `Invoke-RestMethod`；`pubmed_search.py` 在 URL 过长时自动转 POST。脚本顶部的集成说明段是契约文本，可折行但不要改语义。

## 7. 数据契约

### 7.1 容器与 vault

`C:\Vault` 是容器根，每个 `C:\Vault\<主题>\` 是独立 Obsidian vault。

```
C:\Vault\
├─ <vault>\            # Clippings\（raw 层，正文只读）、Claude\（PA / FE）、Chi\（PT）、*.bat
├─ IMAGE\               # 共享扁平图片目录
├─ PDF\                 # pdf2md 的 PDF 输入，处理后改名 完成_*.pdf
├─ ZIP\                 # MinerU 产物归档；trash 恢复缺失图片的来源
├─ PENDING\             # 默认 Markdown 输出落点（PENDING\Clippings）
└─ TRASH\               # 回收站：Image\、Claude\
```

`is_vault_dir` 的判定：非 `.` 开头、目录名不在 `{TRASH, IMAGE, PDF, ZIP}`、且含 `Clippings` / `Claude` / `Chi` 任一子目录。该判定被 `pdf2md`、`reconcile`、`unify-symbols` 共用。

### 7.2 笔记类型

| 类型 | 判定 |
| :--- | :--- |
| source | 路径含 `Clippings` |
| PA | `Claude\` 下、stem 不含 `zh-CN`、且不以 `_figures` 结尾的笔记 |
| FE | `Claude\` 下 stem 以 `_figures` 结尾 |
| PT | 父目录名 `Chi`，或 stem 含 `zh-CN` |
| 引用溯源类 | stem 以 `_citations` / `_fwd_citations` 结尾；`reconcile` 强制保留 |

判定只依赖路径与文件名，不写 `kind` 字段。

### 7.3 常用 frontmatter 字段

| 字段 | 含义 | 主要写入方 |
| :--- | :--- | :--- |
| `title` | 论文标题 | 外部剪藏、转换、人工 |
| `doi` | 主 DOI（字符串或单元素列表） | `pdf2md` `crossref` |
| `reference` | DOI wikilink 列表，`reference[0]` 为主 DOI | `pdf2md` `crossref` `markdown` |
| `cited_by` | 施引论文 DOI wikilink 列表 | `pdf2md` `cited-by` |
| `cited_by_date` | 最近一次施引查询日期（`YYYY-MM-DD`） | `pdf2md` `cited-by` |
| `paper-analyze` | PA 笔记反向链接（`[[stem]]`，有别名时以竖线分隔） | `match` |
| `paper-translate` | PT 译文反向链接 | `match` |
| `figure-extractor` | FE 图示反向链接 | `match` |
| `被引` | 本文被哪些笔记引用（`[[stem]]` 列表） | `markdown` |
| `特殊引用数` | 非安全形态引用计数 | `markdown` `pmce` |
| `tags` | `正向` / `负向` 标签 | `markdown` |
| `aliases` | 别名列表；`markdown` 会把未建图谱的笔记重置为空列表 | `markdown` |
| `source` / `published` | 来源 URL（`match` 与 `reconcile` 用来对齐 Clippings）/ 发表年（`pdf2md` 判断参考文献时效） | 外部剪藏、PT 生成方、`pdf2md` |
| `pdf_path` | 本地 PDF 路径，仅本地转换写入 | `pdf2md-local` |

`cited_by_count` 会被施引写回主动删除；`author` / `published` 会在 `markdown` 处理未建图谱的笔记时被剔除；`引用情况` 会被 `markdown` 删除。

### 7.4 DOI 与引用口径

- DOI 统一走 `core.doi.process_doi`；`￥` 是 DOI 的安全文件名形态，不是错误字符：把 `/` 换成 `￥`，去掉 `\ : * ? " < > |` 等文件系统非法字符，折叠连续 `￥` / 下划线 / 空白，截断到两百字符，为空时回退为 `doi-<hash>`。
- 主 DOI 通用定位顺序：frontmatter `doi` → 正文 `DOI:` 行 → 正文中第一个可信 DOI；`pdf2md` 另有缓存、缓存交叉验证、标题搜索、OpenAlex、JSON、PDF 的定级链。`is_plausible_doi` 是可信度闸门，过滤纯字母后缀、超长、双 DOI、`.doi` 标签、统计区间（如 `1.2(0.9-1.5)`）、参考文献尾注样式（如 `12.Smith`）与以符号结尾的截断 DOI。
- `reference[0]` 为 `[[标题|主DOI]]`，`pin_main_doi` 负责去重并置顶；`cited_by_date` 在默认新鲜窗口内跳过重复查询，`apply_cited_by` 统一写日期并在有结果时覆盖 `cited_by`。
- 引用列表去重以显示侧 DOI 小写为键；已有链接若 name 部分含裸 `/` 会被改写为 `￥` 形态。`Clippings` 正文只读：`match` 只回填三个反向链接字段，`markdown` 重写引用 / 被引 / 标签 / 别名 / 特殊引用数，`pdf2md` / `crossref` 主要写 `doi` 与 `reference`；`pdf2md` 另写 `published`、`cited_by` / `cited_by_date` 与本地 `pdf_path`，`remove-doi` 按整行删除。

## 8. 命令参考

通用约定：`reconcile` 与 `unify-symbols` 默认 dry-run，必须加 `--force` 才落盘；`match` 用 `--dry-run` 预览。

### 8.1 入库链

#### `pdf2md`

MinerU 云端批量 PDF → Markdown，并补全参考文献与施引。

| 参数 | 默认 | 说明 |
| :--- | :--- | :--- |
| `--path_pdf` | `C:\Vault\PDF` | PDF 输入目录（递归） |
| `--path_zip` | `C:\Vault\ZIP` | ZIP 下载与解压临时目录 |
| `--path_md0` | `C:\Vault\PENDING\Clippings` | Markdown 输出目录 |
| `--path_images` | `C:\Vault\IMAGE` | 图片复制目标 |
| `--cited_by_max` | `10` | 最多写入多少篇施引 |
| `--ref_max_age` | `15` | 参考文献时效上限（年） |
| `--local` | 关闭 | 被 argparse 接受，但不参与分发 |

`--local` 只在参数表里存在：`cli.py` 分发时固定 `local=(cmd == 'pdf2md-local')`，因此 `pdf2md --local` 仍会走云端并需要 token。需要本地转换请直接用 `pdf2md-local`。

1. 递归收集 `--path_pdf` 下文件名不含 `完成` 的 PDF；先扫全库 `Clippings` 建 `stem → md` 索引，处理历史遗留：已有 `完成_<name>.pdf` 且能找到对应 MD 时，把 MD 硬链接（失败退回复制）到输出目录、PDF 移入上级 `TRASH`；找不到 MD 则把完成标记移入 `TRASH` 并重新处理。
2. 每批最多 `45` 个 PDF 申请上传链接，上传、下载、逐文件处理都走共享线程池；轮询批次每 `10` 秒一次，默认上限半小时；已存在的 ZIP 跳过。
3. 解压后取 `full.md`、`images/`、`content_list_v2.json`，MD 落到 `--path_md0`（文件名经 `canonicalize_stem` 归一），图片复制到 `--path_images`。
4. DOI 从三处汇总：Markdown 正文、`content_list_v2.json` 文本块、PDF 文本（pdfplumber 在 `spawn` 子进程里跑，最多 `4` 进程，`60` 秒超时）。主 DOI 按缓存 → 缓存交叉验证 → Crossref 标题搜索 → OpenAlex 在线验证 → MD → JSON → PDF 定级；随后补全参考文献与施引、清洗正文，把 `](images/` 替换为 `--path_images` 绝对路径，写入 frontmatter，把 PDF 改名为 `完成_<原名>.pdf`（失败则移入上级 `TRASH`），收尾保存缓存。
5. 参考文献只在论文发表年缺失或未超过 `--ref_max_age` 时补；正文没有 `## 参考文献` 段时自动追加 Crossref 条目，同时把新 DOI 并入 `reference`。

注意：`--enable_api_references` 与 `--enable_cited_by` 用 `store_true` 且默认 `True`，命令行无法关闭，只能改 `cli.py` 或调用 `run_pdf2md` 时传 `False`。从 `content_list_v2.json` 提取到的裸 URL 会被包成 `sslocal://flow/file_open?url=...` 形式，这是既有行为。图片目标已存在时会用 `copy2` 覆盖。

#### `pdf2md-local`

本地 pdfplumber 转换，不调用 MinerU；识别到 DOI 时仍可能联网补全参考文献与施引。

参数与 `pdf2md` 类似，但没有 `--path_zip`。用 pdfplumber 抽文本、`find_tables` 转 Markdown 表、按句末符号与大小写合并断行，并用编号标题 / 全大写短行 / 常见章节名猜测二级标题。随后执行与云端一致的 DOI、参考文献、施引补全，PDF 同样改名 `完成_`。本地分支不产出图片，却仍会把 `](images/` 改写成共享图片目录的绝对路径，因此正文里的图片链接可能指向并不存在的文件。复杂分栏、扫描件、矢量图的效果明显弱于 MinerU；适合 MinerU 不可用或 PDF 不便上传的场景。每个文件独立处理，共用进程内线程池。

#### `pmce`

`PMID` / `DOI` / 标题 → EuropePMC OA 全文 → `Clippings\PENDING`。

`input` 可为文件路径或直接粘贴的文本，省略时进入粘贴模式（空行结束）；`--path` 必填，指向目标 `Clippings\PENDING`；`--no-graph` 跳过收尾图谱与主 DOI 置顶；`--dry-run` 只打印非 OA，不写 MD。

1. 输入按 DOI、`PMID:` 标签或 7–9 位裸数字、标题行三类解析；标题要求至少 3 个长度 ≥ 4 的英文词，且整行长度在 20 字符以上、不超过三百字符。同一标识去重。
2. 元数据按每批 `40` 条并行查询 EuropePMC（`resultType=core`，`pageSize=100`），遇到限流或服务端错误按 `Retry-After` 或递增等待重试，最多 3 次；整批请求失败时，仅 DOI 类条目改用 OpenAlex 免费接口补元数据。匹配优先按 PMID / DOI 精确命中，标题按 `SequenceMatcher` 相似度 ≥ 0.5 选最佳。
3. 仅 `pmcid` 存在且 `isOpenAccess == 'Y'` 的条目进入全文抓取；其余收集为非 OA 清单，结尾打印 DOI 与标题。
4. 全文走 JATS XML 解析：标题、来源、作者、DOI、发表年、Abstract、章节标题、段落、列表、公式、表格（HTML 表）、图片与参考文献。写文件前会抓取 PMC 页面，尝试把图文件名映射到真实 CDN 地址；未命中的图保留 PMC 图页、EuropePMC 全文，以及有 href 时的图片文件链接。输出初稿为无 frontmatter 的 MD，文件名取标题清洗后的前 `150` 字符；同名文件已存在时跳过，同一批次内重名时追加 `_<PMCID>`。`--dry-run` 在这里返回，只打印非 OA；正常收尾若未加 `--no-graph`，会对 `PENDING` 的父目录（即 `Clippings`）执行一次 `markdown`，并把刚写入文件的 `reference[0]` 置为 `[[文件名|自身 DOI]]`，必要时递增 `特殊引用数`。全文抓取失败的条目会并入非 OA 清单，解析失败的条目只打印原因；已存在的基础文件名会跳过，不会覆盖。

### 8.2 图谱与匹配

#### `markdown`

建立 / 更新 DOI 引用图谱，回写去重后的 `reference`、`cited_by`、`被引`、`tags`。

`--path` 必填，递归处理 `.md`；`--depth` 默认 `0`（仅 vault 级统计），大于 `0` 时按文件夹层级输出引用战报。

- 收集阶段：并行读取文件，解析 `reference` 与 `cited_by` 中的 DOI，建立全局 `DOI → (名称形态, 引用者 stem 集合)` 映射。对既无 `aliases` 也无 `reference` 的笔记，从全文抓 DOI 建 `reference`，重置 `aliases`，剔除 `author` / `published`，并写 `特殊引用数`。
- 回写阶段：重建每个文件的 `reference`（统一 name 形态、按 DOI 去重、丢弃不可信 DOI），解析 `cited_by`，按引用者集合写 `被引 = [[stem]]`（排除自身），按 `(被引数 - 特殊引用数) > 0` 打 `正向` / `负向` 标签，删除 `引用情况`。PMC 网页剪藏若正文前 `500` 字符含 `us_flag.svg` 且 `reference[0]` 是安全 DOI 形式，会把 `reference[0]` 升级为 `[[文件名|DOI]]`。

收尾会打印当前不存在但被引最多的 DOI，以及 `cited_by` 中出现最多的外部 DOI；`--depth` 大于 `0` 时按层级逐文件夹复用同一套统计。该命令会整文件重写 frontmatter，并把本文 DOI 追加到每个参考文献 DOI 的 `Cite_By_cache` 列表，同时更新 DOI 标题缓存；跑之前先备份。`Cite_By_cache` 与 `cited-by` 命令共用，因此本地图谱与 PubMed 施引结果会写在同一份缓存里。

#### `crossref`

标题 ↔ DOI、参考文献拉取 / 接管。`input` 省略时进入循环交互，按 `Ctrl+C` 退出并保存缓存。

- `路径`：处理 `.md` 或 `.pdf`，取主 DOI（frontmatter → PDF 首页 → 正文）后拉 Crossref 参考文献；`.md` 回写 `reference` 并置顶主 DOI。
- `￥路径`：接管模式，忽略已有 `reference`，用标题搜 DOI，再按 Crossref 结果从空列表重建。
- `local:路径 [doi:目标DOI]`：解析正文 `# 参考文献` / `# Reference` 下的编号条目，逐条取 DOI 或按标题搜 DOI，再合并进 `reference`。
- `doi:DOI`：先拉该 DOI 的参考文献，再交互询问目标 `.md` 路径后导入。

- 纯路径模式提取不到 DOI 时会尝试标题搜索：Crossref 返回标题与本地标题做 `SequenceMatcher` 比对，相似度低于 0.5 时用 Crossref 标题再查一次。
- 普通路径模式保留已有引用，去重后把主 DOI 置顶；只有 `￥` 接管模式会清空后重建。对 PDF 输入只拉取参考文献并打印条数，不写 `reference`。`local:` 模式把正文条目中已含 DOI 的直接采用，其余并发查 Crossref，找不到 DOI 的条目跳过；`doi:` 模式先确认 DOI 格式，拉不到参考文献就终止，目标路径支持 `obsidian://` URI。所有模式共用同一份 DOI 标题缓存；只有交互循环会在每轮结束与退出时保存缓存，一次性调用不落盘。

#### `cited-by`

PubMed 施引查询并写回 frontmatter。

`--path` 默认 `-`（交互输入，也可给 `.md` 文件或目录），`--max` 默认 `10`，只影响读取时的截断。

路径支持 `obsidian://` URI 与全库兜底。若目标是目录且自身不叫 `Clippings`、但下面有 `Clippings` 子目录，会自动下沉一层。主 DOI 取 frontmatter `doi` → `DOI:` 行 → 正文首个可信 DOI，再回退到 `reference[0]`。`cited_by_date` 在默认新鲜窗口内直接跳过。查询链路为 `esearch`（DOI → PMID）→ `elink`（citedin）→ `esummary`（每 `100` 个一批），只保留近 5 年文献并按发表日降序；写回 `cited_by` 与 `cited_by_date`，同时删除 `cited_by_count`。已存在于目标目录 frontmatter / reference / cited_by 中的 DOI 会被过滤。施引缓存保存全量列表，`--max` 只在读取时截断。没有查询结果时只刷新 `cited_by_date`，不会清空已有 `cited_by`。

#### `match`

PA / PT / FE 三向匹配，回填论文端反向链接。`base_dir` 必须是含 `Clippings` 与 `Chi` 的 vault 根；`Claude` 可选，缺失时只跳过 PA / FE。

`--dry-run` 只打印不写盘；`--threshold` 为 PT 的 Jaccard 阈值（默认 `0.85`）；`--force` 覆盖已有反向链接（默认跳过已填字段）；`-v` / `--verbose` 打印 PT 失败时的三个最高候选；`--trash` 额外扫描 `TRASH\Claude` 并做归属调谐。

- PT（`paper-translate`）：Chi 反向索引（按 `paper-translate` 目标回指）→ `source` 相同 → `reference[0]` 目标相同 → DOI 集合 Jaccard 达阈值。Jaccard 用 DOI 倒排索引预筛；别名取 Chi 的 `title`。
- PA（`paper-analyze`）：Clippings 与 PA 之间的 H1 wikilink 反指 → 文件名（空格换下划线）→ DOI 子串命中（带记忆化）→ `SequenceMatcher` 模糊匹配（长度门控 `0.63`，接受阈值 `0.7`）。别名取 PA 的 H1 标题（缺失时取正文首个中文行）。FE（`figure-extractor`）则走 H1 / PA 别名反指 → 文件名 → `stem + _figures` 模糊匹配。

`--trash` 的调谐是双向的：当前 vault `Claude` 下未被任何 Clippings 引用、且不是 FE / zh-CN 的 PA 会移入 `C:\Vault\TRASH\Claude\<vault>`；`TRASH` 中被当前 vault 新匹配到的 PA / FE 会回收到对应 vault 的 `Claude`。只主动移动 PA，FE 与 PT 不主动移入回收站。每次匹配成功只在非 dry-run 时写盘；返回布尔值表示是否有新匹配，但 `cli.py` 不会把它转成退出码。

#### `reconcile`

全库 PA / FE / PT 归属调谐，默认 dry-run，`--force` 才移动文件。vault 根固定 `C:\Vault`，回收站固定 `C:\Vault\TRASH\Claude`，命令行不暴露这两个路径。

判定顺序：PA 先看 H1 指向的目标笔记属于哪个 vault；其次看自身 stem 是否被某个 Clippings 的反向引用命中；再看 stem 是否存在于某个 vault 的 `Clippings`；都不满足则记为孤儿。PT 依次看 `paper-translate` 目标、`source`、`reference[0]` 目标、`reference[0]` 的 DOI、DOI 集合 Jaccard（阈值 0.5），最后回退到 stem / 反向引用。FE 的归属跟随对应 PA。

只有判定为 `move` 的文件会真正移动；目标位置已有同名文件时，源文件以 ` (n)` 唯一名移入 `TRASH\Claude\<来源 vault>`。孤儿不会自动移入回收站，只打印 `[WARN] ... 保持原位`，但统计里的 `trash` 计数仍会包含它们，便于人工复核。PA 中带 `_citations` / `_fwd_citations` 后缀的强制保留，stem 末尾带空格加数字的重复项会在输出中标注。结尾打印 keep / move / trash 统计与各 vault 保留数量。只扫描每个 vault 的 `Claude` / `Chi` 第一层 `.md`；`Clippings` 索引则递归扫描。子目录中的派生笔记不会被该命令调谐。

### 8.3 归档与维护

#### `archive`

归档 Clippings 论文及其 PA / PT / FE 关联笔记。`-s/--source`（源 `.md`）与 `-t/--target`（目标目录）均必填。

- 目标必须位于某个含 `.obsidian` 的 vault 内（含 vault 根），否则直接 `SystemExit`。目标若就是 vault 根，自动落到 `<vault>\Clippings`；若目标相对 vault 根恰为 `<主题>\Clippings`，文件落到其 `PENDING` 子目录。
- 源文件按硬链接优先、失败退回复制的方式搬入；随后依据 frontmatter 的 `paper-analyze` / `paper-translate`，从源 vault 的 `Claude\` / `Chi\` 复制对应 PA / PT 笔记到目标 vault 同名目录；PA 存在时再复制 `<PA stem>_figures.md`。结果以 Markdown 表格打印：`硬链接 / 已复制 / 跳过(已存在) / 未找到`，不做删除、不做覆盖。

#### `clean-images`

无参数。扫描 `C:\Vault` 全部 `.md`，把 `IMAGE` 中未被任何笔记引用的文件移入 `C:\Vault\TRASH\Image`。只识别本地图片语法 `![alt](path)`，且路径需含 `Vault/IMAGE`、`/images/` 或以 `images/` 开头；HTTP 图片忽略。目录来自 `config`，命令行不提供覆盖。IMAGE 目录不存在时会直接报错，不会自动创建。

#### `trash`

先做图片维护，再做目录归档：

1. 扫描 `C:\Vault` 全部 `.md`，收集引用了 `Vault/IMAGE`、`/images/` 或 `images/` 的图片名。
2. `IMAGE` 中未被引用的文件移入 `C:\Vault\TRASH\Image`。
3. `IMAGE` 中缺失但被引用的文件，从 `C:\Vault\ZIP\*.zip` 里按 basename 找回，剩余缺失项逐条打印。随后把 `<path>` 下除 `.obsidian`、`TRASH` 外的所有子目录移入 `<path>\trash\YYYYMMDD\`，并在原位重建空目录。该步对路径不做校验，把 vault 根当参数会移走 `Clippings` / `Claude` / `Chi`，运行前务必确认参数。

#### `remove-doi`

`--path` 必填，`--doi` 可省略（省略时交互输入）。把 DOI 转成 `[[安全DOI|原始DOI]]` 后，递归扫描目录下 `.md`，删除包含该 wikilink 的整行，线程池并行，最后逐文件打印命中行数。它按整行删除，不会保留同一行的其它内容；只匹配该精确 wikilink 文本，其它 name 形态不会被删除。

#### `rename-pdf`

位置参数 `directory`，默认当前目录；只处理该目录第一层的 `*.pdf`，跳过 `完成_` 开头的文件。

标题来源：优先 PyMuPDF 元数据 `title`，经垃圾标题（`untitled`、`microsoft word`、出版社名等）、稿件号、源文件扩展名、超长全大写等过滤；不合格则用首页字号布局启发式（上半页、最大字号、行聚类、跳过机构与作者学位行）。得到标题后清理 DOI、`ahead of print` 等状态词、`et al.` 与作者学位，引号统一为规范双弯引号，去掉非法文件名字符，超长按词截断。若标题能在 DOI 标题缓存中找到前缀，会用首页后续词验证并取缓存中的完整标题。重名自动追加 ` (2)`、` (3)`。失败项打印原因并保留原名。

#### `unify-symbols`

`--vault` 默认 `C:\Vault`；不加 `--force` 即为 dry-run，只打印映射，`--force` 才落盘。

扫描每个 vault 的 `Claude` / `Chi` / `Clippings`，用 `canonicalize_stem` 判断文件名是否含需要规范化的 Unicode 字符（各种破折号 → `-`，单弯引号 → 规范双弯引号，省略号 → `...`）。执行时先改所有 wikilink 目标，再重命名文件，最后打印重命名数量与链接更新数量。只处理文件名与链接目标，不改正文文字。

## 9. 主链路

```
入库：PDF → pdf2md / pdf2md-local → PENDING\Clippings；PMID/DOI/标题 → pmce → OA 全文 MD；
      检索 → pubmed_search / high_cited；归库 → archive；副作用 → DOI / Crossref / 施引写回
加工：init_paper → 落位与占位；LLM/人工写 PA/FE/PT → match；link_note_to_paper → 互链；
      crossref / cited-by → 引用补全；markdown → 图谱、被引、正负向标签
维护：reconcile / clean-images / trash / unify-symbols / rename-pdf
```

链上自动副作用有两处：`pdf2md` 转换完立即补 DOI / 参考文献 / 施引并改名 `完成_*.pdf`；`pmce` 默认收尾重建引用图谱并置顶主 DOI。其它命令都需要手动串联。

## 10. 接口契约

### 10.1 退出码

`cli.py` 正常结束返回 0。`run_reconcile` / `run_unify_symbols` / `run_match` 返回的布尔值被 `main()` 丢弃，不会变成退出码，因此不能用 `if errorlevel` 判断是否真的执行了迁移或匹配。`archive` 在源文件不存在或目标不在 vault 下时 `SystemExit`，才会得到非零退出码。`RECONCILE.bat` 里的 `if errorlevel 1 goto :end` 实际上很难触发，必须靠 dry-run 输出与交互确认控制。`link_note_to_paper.py` 用 `0` / `1` 表示成功 / 失败；`pubmed_search.py` 与 `high_cited.py` 出错时 `sys.exit(1)`；`init_paper.py` 把错误写进 JSON 的 `error` 字段，仍以 0 结束。

### 10.2 写盘

改写 Markdown 内容时直接用 `Path.write_text(..., encoding='utf-8')`，没有原子替换、没有临时文件、没有备份。需要重建 frontmatter 时一律经 `core.frontmatter.dump_frontmatter` 重组，不要手工拼 `---` 头。`dump_frontmatter` 在 `fm` 为空时只返回正文，因此空 frontmatter 会被静默丢弃；它会把正文的 `\r\n` / `\r` 归一为 `\n`，避免 Windows 文本模式写出 `\r\r\n`。批量读取与 frontmatter 解析侧容错 UTF-8 与 GBK，部分命令直接按 UTF-8 读取；写侧统一 UTF-8。

### 10.3 并发

- `core.cache.map_parallel` 是模块级共享线程池，供上传、下载、批量读文件、frontmatter 解析、图形扫描等复用；结果保持输入顺序，异常在取结果时抛出。`pdf2md` 的上传、下载与逐文件后处理并行；PDF 文本抽取使用 `multiprocessing` 的 `spawn` 池，最多 `4` 进程，单次 `60` 秒超时。本地转换与云端后处理共用线程池。
- `markdown` / `match` / `reconcile` / `cited-by` / `remove-doi` / `rename-pdf` / `clean-images` / `trash` / `unify-symbols` 都在单进程内并行 IO；`markdown` 的共享 DOI 映射用 `threading.Lock` 保护，`match` 主要串行遍历 Clippings。
- DOI 标题缓存与施引缓存是单文件 JSON，模块内有锁，但没有跨进程锁；多个命令并发会互相覆盖缓存。不要同时跑两个批量命令，也不要在 `pdf2md` 运行期间跑 `markdown`。

### 10.4 网络

Crossref 与 PubMed 请求共用 `requests.Session`，固定浏览器 UA；Crossref 带 `mailto` 参数与 `rows=3`，文献详情超时 `100` 秒；Crossref 标题查询与施引批次之间随机等待 1–2 秒。`_api_get` 吞掉所有异常并返回 `None`，调用方按“无结果”处理，不重试。OpenAlex 请求对限流与服务端错误做 3 次指数退避，仍失败则返回 `None`。`pmce` 的 EuropePMC 请求有自己的重试循环，限流或服务端错误会按 `Retry-After` 或递增秒数等待；PMC 页面抓取先试 requests，再试 `curl_cffi` 的 Chrome 指纹。标题→DOI 的 Crossref 结果必须通过相似度门控（≥ 0.5 或子串命中）才会被接受。

## 11. 修改指引

| 需求 | 落点 |
| :--- | :--- |
| 新增子命令 | `cli.py` 注册 `add_parser` 并补 `handlers`；实现放 `commands/<name>.py` |
| 改路径 / 并发基准 / 缓存位置 | `config.py` |
| 改 DOI 规范化与可信度口径 | `core/doi.py` |
| 改 wikilink / reference 文法 | `core/refs.py` |
| 改 frontmatter 解析 / 序列化 / 来源键 / 施引写回 | `core/frontmatter.py` |
| 改远程服务 | `core/web_services.py`；会话与延迟走 `core/http.py` |
| 改 PDF 提取 / 本地转 MD / MinerU | `core/pdf_extractor.py`、`core/mineru.py`；批次编排在 `commands/pdf2md.py` |
| 改匹配策略 / 归属判定 | `commands/match.py` 顶部常量与 `_match_*`；`commands/reconcile.py` 的 `resolve_action` |
| 改 PDF 标题启发式 | `commands/rename_pdf.py` 的 `JUNK_TITLES`、状态词与首页布局逻辑 |
| 改技能脚本 / BAT | `skill_scripts/<脚本>.py` 与 `skill_scripts/skill_common.py`；`scripts/` 模板改后同步已部署副本与写死的 `cli.py` 路径 |

硬约束：

- 不在其它模块硬编码绝对路径，统一走 `config.py`。
- 不修改 `Clippings` 正文，只允许写引用与反向链接字段。
- 不把 `￥` 当成错误字符；它是 DOI 的安全文件名形态。
- 不改 CLI 参数名与 `dest`；frontmatter 字段名冻结，改名必须同步 BAT、调用方与既有 vault 数据。
- 不并发运行同一批入库 / 调谐命令；不把 `core/` 变成第二个 CLI，参数解析与用户进度留在 `commands/`。不改 `skill_scripts` 顶部的 bootstrap 注入；技能侧与工具侧按同一文件维护，新增公共逻辑放 `skill_common.py`。

## 12. 配置与缓存

| 配置 | 值 / 说明 |
| :--- | :--- |
| `CPU_CORES` | `max(1, CPU 数 - 1)`，并发基准 |
| `MINERU_TOKEN` | `C:\ResearchFront\DATA\API\MinerU.txt` |
| `OBSIDIAN_ROOT` | `C:\Vault` 容器根 |
| `DEFAULT_PDF_PATH` | `C:\Vault\PDF` |
| `DEFAULT_ZIP_PATH` | `C:\Vault\ZIP` |
| `DEFAULT_MD_PATH` | `C:\Vault\PENDING\Clippings` |
| `DEFAULT_IMAGE_PATH` | `C:\Vault\IMAGE` |
| `DOI_TITLE_CACHE` | `D:\ResearchFront\DATA\API\Doi_Title_cache.json`（标【勿改】） |
| `CITE_BY_CACHE` | `D:\ResearchFront\DATA\API\Cite_By_cache.json`（标【勿改】） |
| `CROSSREF_MAILTO` / `USER_AGENT` | Crossref 的 `mailto` 参数 / 浏览器 UA 字符串 |

- `Doi_Title_cache.json`：`DOI → [title, 规范化 title]`；`put_doi_title` 写入前会拒绝不可信 DOI 与带 `[[...]]` 的标题，已有非空标题默认不覆盖，`force=True` 才允许覆盖。`Cite_By_cache.json`：`DOI → [施引 DOI, ...]`，保存全量施引列表，读取时再过滤与截断。缓存可删除重建，但会丢失加速；删除前确认没有正在运行的任务。
- 固定参数：PT 的 Jaccard `0.85`，PA / FE 模糊接受阈值 `0.7`，Obsidian URI 模糊 `0.7`，标题缓存模糊 `0.95`，Crossref 标题门控 `0.5`，`reconcile` 的 DOI Jaccard `0.5`，施引新鲜期约一个月，PubMed 时间窗 5 年，每批上传 `45` 个 PDF，`pmce` 每批 `40` 条，施引摘要每批 `100` 个 PMID。

## 13. 已知限制

- Windows 专用（盘符路径、`C:\Vault` 容器、BAT、`spawn` 多进程）；不下载 PDF，论文必须事先放进 `C:\Vault\PDF`，`分库/PDF2MD.bat` 也不会改 PDF 输入目录。
- `pdf2md --local` 被参数表接受但不生效，实际仍走云端；本地转换只能走 `pdf2md-local`。`--enable_api_references` / `--enable_cited_by` 也无法从命令行关闭，想彻底离线只能改代码或直接调用 `run_pdf2md`。
- 主 DOI 启发式把“正文中第一个可信 DOI”当论文自身 DOI；若首页先出现参考文献 DOI，可能定错，需要人工用 `crossref ￥路径` 或 `doi:` 模式纠正。OpenAlex 与缓存验证也可能接受错误候选；Crossref 标题查询最多取 3 条候选，只接受相似度 ≥ 0.5 或子串命中的第一条。
- 本地 pdfplumber 转换不抽图，却仍把 `images/` 前缀改写成共享图片目录的绝对路径，可能产生断图；复杂表格与公式效果有限。
- `trash <path>` 会移动该路径下所有子目录，参数写错代价很高；`markdown` 会覆盖 `tags`、`aliases`、`特殊引用数`，其它工具写入的同名字段会被冲掉，并会把本文 DOI 注入参考文献的施引缓存。`reconcile` 的 `trash` 统计只表示孤儿，不会自动移入回收站；`match --trash` 只把未匹配 PA 移入回收站，不主动移动 FE / PT；`reconcile` 只扫 `Claude` / `Chi` 第一层。
- `pmce` 只抓 OA 全文，非 OA 只打印，不会生成占位 MD；全文初稿不含 frontmatter，需依赖收尾的 `markdown` 补齐；JATS 公式只识别带 `\begin{document}...\end{document}` 包裹的 TeX。
- `clean-images` / `trash` 假定 `IMAGE` 目录存在，目录缺失时会直接报错；`archive` 按 UTF-8 严格读取源文件。写盘非原子且无锁，没有自动化测试；`pyproject.toml` 的 `build-backend` 非标准，`pip install .` 可能失败，以脚本方式运行为主。`skill_scripts` 的四个入口都依赖同目录的 `skill_common.py`；只复制单个脚本到技能目录会因缺少共享模块而失败。`pubmed_search.py` 的 `--usehistory` 只向 `esearch` 透传该参数，实际取回仍以 `esearch` 返回的 idlist 为准。

## 14. 代码约定

- 模块名、函数名、变量名用 `snake_case`，类名用 `PascalCase`，模块级常量用 `UPPER_SNAKE`。正则常量没有统一前缀：`PATTERN_*`（`doi.py` / `markdown_utils.py` / `mineru.py`）、`*_RE`（`refs.py` / `match.py`）、`_RE_*` 与 `RE_*`（`doi.py` / `crossref.py`）并存；改代码时沿用所在模块的写法。纯函数优先加 `lru_cache`（`process_doi` / `norm_title` / `canonicalize_stem` / `classify_claude_stem` / `norm_stems` / `pa_stem_variants` / `_parse_obsidian_uri`），但不得让调用方依赖返回值的可变性。
- 需要提醒后来者不要误改的位置用 `# 【勿改】` 注释，例如 `￥` 的设计意图与两个缓存路径。
- `core/` 不读 `argparse`；用户进度与业务输出放 `commands/`。`core/web_services.py` 会打印 Crossref / PubMed / OpenAlex 进度，`core/mineru.py` 与 `core/pdf_extractor.py` 会打印提取失败，属于既有例外。
- 路径参数命名不统一（`path` / `path_pdf` / `base_dir` / `directory`），调用时以 `cli.py` 的 `dest` 为准。frontmatter 字段名、CLI 参数名、JSON 缓存键都视为冻结契约；改名必须同步 BAT、调用方与既有 vault 数据。交互循环写在 `commands/crossref.py` 与 `commands/cited_by.py` 内部，新增交互逻辑不要放进 `core/`。
- 技能脚本只通过 `skill_common.py` 获取 bootstrap、会话、表格与 PMCE 格式化；不要在单个脚本里另写一份 bootstrap，也不要让 `skill_common.py` 依赖工具根的 `core/` 才能在技能路径下运行。

## 15. 执行与排错

1. 先设编码：`$env:PYTHONIOENCODING = 'utf-8'`；BAT 已带 `chcp 65001`（`TRASH.bat` 除外）。
2. 先预览：`reconcile` / `unify-symbols` 不加 `--force` 即 dry-run；`match` 用 `--dry-run`。
3. 依赖检查：`cli.py` 顶部一次性导入全部命令模块，缺 `fitz` / `pdfplumber` / `requests` / `yaml` / `curl_cffi` 时连 `--help` 都会失败。退出码不等于业务结果：除 `archive` 的 `SystemExit` 外，一律以 0 结束，靠输出判断。
4. 单实例：不要并发跑 `pdf2md`、`pmce`、`markdown`、`match`、`reconcile`；不要跨进程共享两个 JSON 缓存。缓存异常时相关命令会退化为联网或空缓存，确认无任务在跑后再删除重建。写盘前先备份：批量改写 frontmatter 或移动目录前，先复制 vault，至少备份 `Clippings` 与 `TRASH`；回归检查用 `python cli.py --help`、`python -m compileall -q <工具根>`，再在副本 vault 上跑一次 `match --dry-run` 与 `markdown`。
