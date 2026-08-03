@echo off
:: 本地提取 避免信息泄露
chcp 65001 > nul
setlocal
set "current_dir=%~dp0"
set "current_dir=%current_dir:~0,-1%"
python "C:\ResearchFront\Claude\Obsidian-Paper-Tools\cli.py" pdf2md-local --path_md0 "%current_dir%\Clippings\PENDING" --path_images "%current_dir%\Clippings\images"
timeout /t 30
