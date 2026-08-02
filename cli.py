"""/s: Obsidian-Paper-Tools — Obsidian Vault academic paper management CLI.
Integrates MinerU PDF-to-Markdown API, Crossref API (DOI references & citation lookup),
PubMed E-utilities (cited-by queries), pdfplumber (local PDF text extraction),
and YAML frontmatter manipulation for Obsidian wikilink-based citation graphs.
"""
import argparse
from pathlib import Path

from commands.pdf2md import run_pdf2md
from commands.markdown_graph import run_markdown_graph
from commands.crossref import handle_input as crossref_handle, run_crossref_interactive
from commands.match import run_match
from commands.trash import run_trash
from commands.remove_doi import run_remove_doi
from commands.archive import run_archive
from commands.cited_by import run_cited_by, run_cited_by_interactive


def main():
    parser = argparse.ArgumentParser(description='Obsidian-Paper-Tools')
    sub = parser.add_subparsers(dest='command', help='Available commands')

    p_pdf2md = sub.add_parser('pdf2md', help='MinerU PDF批处理')
    p_pdf2md.add_argument('--path_pdf', default=r'C:\Vault\PDF')
    p_pdf2md.add_argument('--path_zip', default=r'C:\Vault\ZIP')
    p_pdf2md.add_argument('--path_md0', default=r'C:\Vault\Claude\MDfrPDF')
    p_pdf2md.add_argument('--enable_api_references', action='store_true', default=True)
    p_pdf2md.add_argument('--enable_cited_by', action='store_true', default=True)
    p_pdf2md.add_argument('--cited_by_max', type=int, default=10)

    p_md = sub.add_parser('markdown', help='建立DOI引用图谱')
    p_md.add_argument('--path', required=True)

    p_cr = sub.add_parser('crossref', help='Crossref参考文献工具')
    p_cr.add_argument('input', nargs='?', default=None, help='输入(可选)')

    p_match = sub.add_parser('match', help='匹配PA/PT/FE')
    p_match.add_argument('base_dir')
    p_match.add_argument('--dry-run', action='store_true')
    p_match.add_argument('--threshold', type=float, default=0.85)
    p_match.add_argument('--force', action='store_true')
    p_match.add_argument('-v', '--verbose', action='store_true')

    p_trash = sub.add_parser('trash', help='归档子目录')
    p_trash.add_argument('path')

    p_doi = sub.add_parser('remove-doi', help='移除错误DOI')
    p_doi.add_argument('--path', required=True)
    p_doi.add_argument('--doi', default=None)

    p_cite = sub.add_parser('cited-by', help='PubMed Cited-by 查询')
    p_cite.add_argument('--path', default='-', help='.md文件或目录(留空交互输入)')
    p_cite.add_argument('--max', type=int, default=10, help='最多取回篇数(默认10)')

    p_arch = sub.add_parser('archive', help='归档Clippings')
    p_arch.add_argument('-s', '--source', required=True)
    p_arch.add_argument('-t', '--target', required=True)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return

    if args.command == 'pdf2md':
        run_pdf2md(args.path_pdf, args.path_zip, args.path_md0,
                   args.enable_api_references, args.enable_cited_by, args.cited_by_max)
    elif args.command == 'markdown':
        run_markdown_graph(args.path)
    elif args.command == 'crossref':
        if args.input:
            crossref_handle(args.input)
        else:
            run_crossref_interactive()
    elif args.command == 'match':
        run_match(args.base_dir, args.dry_run, args.threshold, args.force, args.verbose)
    elif args.command == 'trash':
        run_trash(args.path)
    elif args.command == 'remove-doi':
        target = Path(args.path)
        doi = args.doi or input('输入要移除的错误DOI: ').strip()
        if not doi:
            print('未输入DOI')
            return
        modified = run_remove_doi(args.path, doi)
        if not modified:
            print('未找到匹配')
        else:
            for p, c in modified:
                print(f'  [{c}行] {p.name}')
    elif args.command == 'cited-by':
        if args.path == '-':
            run_cited_by_interactive()
        else:
            run_cited_by(args.path, args.max)
    elif args.command == 'archive':
        run_archive(args.source, args.target)


if __name__ == '__main__':
    main()
