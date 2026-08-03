"""/s: Obsidian-Paper-Tools — Obsidian Vault academic paper management CLI.
Integrates MinerU API (cloud PDF-to-Markdown), pdfplumber (local PDF-to-MD via --local flag),
Crossref API (DOI references & citation lookup), PubMed E-utilities (cited-by queries),
PyMuPDF title extraction (PDF rename), and YAML frontmatter for Obsidian wikilink citation graphs.
Uses match/case dispatch (Python 3.10+). Includes --path_images for custom image output.
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
from commands.rename_pdf import run_rename_pdf


def _add_api_args(parser, with_zip=True):
    parser.add_argument('--path_pdf', default=r'C:\Vault\PDF')
    parser.add_argument('--path_md0', default=r'C:\Vault\Claude\MDfrPDF')
    parser.add_argument('--path_images', default=None)
    if with_zip:
        parser.add_argument('--path_zip', default=r'C:\Vault\ZIP')
    parser.add_argument('--enable_api_references', action='store_true', default=True)
    parser.add_argument('--enable_cited_by', action='store_true', default=True)
    parser.add_argument('--cited_by_max', type=int, default=10)


def _cmd_remove_doi(args):
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


def main():
    parser = argparse.ArgumentParser(description='Obsidian-Paper-Tools')
    sub = parser.add_subparsers(dest='command', help='Available commands')

    p_pdf2md = sub.add_parser('pdf2md', help='MinerU PDF批处理')
    _add_api_args(p_pdf2md)
    p_pdf2md.add_argument('--local', action='store_true', help='使用本地pdfplumber离线转换')

    p_local = sub.add_parser('pdf2md-local', help='本地pdfplumber PDF转MD')
    _add_api_args(p_local, with_zip=False)

    sub.add_parser('markdown', help='建立DOI引用图谱').add_argument('--path', required=True)

    sub.add_parser('crossref', help='Crossref参考文献工具').add_argument('input', nargs='?', default=None, help='输入(可选)')

    p_match = sub.add_parser('match', help='匹配PA/PT/FE')
    p_match.add_argument('base_dir')
    p_match.add_argument('--dry-run', action='store_true')
    p_match.add_argument('--threshold', type=float, default=0.85)
    p_match.add_argument('--force', action='store_true')
    p_match.add_argument('-v', '--verbose', action='store_true')

    sub.add_parser('trash', help='归档子目录').add_argument('path')

    p_doi = sub.add_parser('remove-doi', help='移除错误DOI')
    p_doi.add_argument('--path', required=True)
    p_doi.add_argument('--doi', default=None)

    p_cite = sub.add_parser('cited-by', help='PubMed Cited-by 查询')
    p_cite.add_argument('--path', default='-', help='.md文件或目录(留空交互输入)')
    p_cite.add_argument('--max', type=int, default=10, help='最多取回篇数(默认10)')

    p_arch = sub.add_parser('archive', help='归档Clippings')
    p_arch.add_argument('-s', '--source', required=True)
    p_arch.add_argument('-t', '--target', required=True)

    sub.add_parser('rename-pdf', help='Rename PDF files by extracted title').add_argument('directory', nargs='?', default='.', help='Directory containing PDF files')

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return

    match args.command:
        case 'pdf2md':
            run_pdf2md(args.path_pdf, args.path_zip, args.path_md0,
                       args.enable_api_references, args.enable_cited_by, args.cited_by_max,
                       local=args.local, path_images=args.path_images)
        case 'pdf2md-local':
            run_pdf2md(args.path_pdf, None, args.path_md0,
                       args.enable_api_references, args.enable_cited_by, args.cited_by_max,
                       local=True, path_images=args.path_images)
        case 'markdown':
            run_markdown_graph(args.path)
        case 'crossref':
            crossref_handle(args.input) if args.input else run_crossref_interactive()
        case 'match':
            run_match(args.base_dir, args.dry_run, args.threshold, args.force, args.verbose)
        case 'trash':
            run_trash(args.path)
        case 'remove-doi':
            _cmd_remove_doi(args)
        case 'cited-by':
            run_cited_by_interactive() if args.path == '-' else run_cited_by(args.path, args.max)
        case 'archive':
            run_archive(args.source, args.target)
        case 'rename-pdf':
            run_rename_pdf(args.directory)


if __name__ == '__main__':
    main()
