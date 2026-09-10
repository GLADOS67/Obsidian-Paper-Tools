"""/s: CLI entry point for Obsidian Vault tools - MinerU, Crossref API, PubMed E-utilities, DOI."""

import argparse

from commands.pdf2md import run_pdf2md
from commands.markdown_graph import run_markdown_graph
from commands.crossref import handle_input as crossref_handle, run_crossref_interactive
from commands.match import run_match
from commands.trash import run_trash
from commands.remove_doi import run_remove_doi
from commands.archive import run_archive
from commands.cited_by import run_cited_by, run_cited_by_interactive
from commands.rename_pdf import run_rename_pdf
from commands.clean_images import run_clean_images
from commands.reconcile import run_reconcile
from commands.unify_symbols import run_unify_symbols

_DEFAULT_PDF = r'C:\Vault\PDF'
_DEFAULT_MD = r'C:\Vault\PENDING\Clippings'
_DEFAULT_IMG = r'C:\Vault\IMAGE'
_DEFAULT_ZIP = r'C:\Vault\ZIP'
_DEFAULT_VAULT = r'C:\Vault'


def _add_api_args(parser, with_zip=True):
    parser.add_argument('--path_pdf', default=_DEFAULT_PDF)
    parser.add_argument('--path_md0', default=_DEFAULT_MD)
    parser.add_argument('--path_images', default=_DEFAULT_IMG)
    if with_zip:
        parser.add_argument('--path_zip', default=_DEFAULT_ZIP)
    parser.add_argument('--enable_api_references', action='store_true', default=True)
    parser.add_argument('--enable_cited_by', action='store_true', default=True)
    parser.add_argument('--cited_by_max', type=int, default=10)
    parser.add_argument('--ref_max_age', type=int, default=15)


def _cmd_remove_doi(args):
    doi = args.doi or input('输入要移除的错误DOI: ').strip()
    if not doi:
        print('未输入DOI')
        return
    modified = run_remove_doi(args.path, doi)
    if modified:
        for p, c in modified:
            print(f'  [{c}行] {p.name}')
    else:
        print('未找到匹配')


def _cmd_remove_doi(args):
    doi = args.doi or input('输入要移除的错误DOI: ').strip()
    if not doi:
        print('未输入DOI')
        return
    modified = run_remove_doi(args.path, doi)
    if modified:
        for p, c in modified:
            print(f'  [{c}行] {p.name}')
    else:
        print('未找到匹配')


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

    sub.add_parser('clean-images', help='清理IMAGE中未被任何MD引用的图片')

    p_rec = sub.add_parser('reconcile', help='全局调谐PA/FE/PT至正确vault或TRASH')
    p_rec.add_argument('--dry-run', action='store_true', default=True)
    p_rec.add_argument('--force', action='store_true')

    p_unify = sub.add_parser('unify-symbols', help='规范化文件名和wikilink中的Unicode符号')
    p_unify.add_argument('--vault', default=r'C:\Vault')
    p_unify.add_argument('--dry-run', action='store_true', default=True)
    p_unify.add_argument('--force', action='store_true')

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return

    cmd = args.command
    if cmd == 'pdf2md':
        run_pdf2md(args.path_pdf, getattr(args, 'path_zip', None), args.path_md0,
                   args.enable_api_references, args.enable_cited_by, args.cited_by_max,
                   local=False, path_images=args.path_images, ref_max_age=args.ref_max_age)
    elif cmd == 'pdf2md-local':
        run_pdf2md(args.path_pdf, getattr(args, 'path_zip', None), args.path_md0,
                   args.enable_api_references, args.enable_cited_by, args.cited_by_max,
                   local=True, path_images=args.path_images, ref_max_age=args.ref_max_age)
    elif cmd == 'markdown':
        run_markdown_graph(args.path)
    elif cmd == 'crossref':
        if args.input:
            crossref_handle(args.input)
        else:
            run_crossref_interactive()
    elif cmd == 'match':
        run_match(args.base_dir, args.dry_run, args.threshold, args.force, args.verbose)
    elif cmd == 'trash':
        run_trash(args.path)
    elif cmd == 'remove-doi':
        _cmd_remove_doi(args)
    elif cmd == 'cited-by':
        if args.path == '-':
            run_cited_by_interactive()
        else:
            run_cited_by(args.path, args.max)
    elif cmd == 'archive':
        run_archive(args.source, args.target)
    elif cmd == 'rename-pdf':
        run_rename_pdf(args.directory)
    elif cmd == 'clean-images':
        run_clean_images()
    elif cmd == 'reconcile':
        run_reconcile(dry_run=not args.force)
    elif cmd == 'unify-symbols':
        run_unify_symbols(args.vault, dry_run=not args.force)


if __name__ == '__main__':
    main()
