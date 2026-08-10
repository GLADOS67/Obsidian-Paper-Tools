@echo off
chcp 65001 > nul
setlocal
set "current_dir=%~dp0"
set "current_dir=%current_dir:~0,-1%"
python "C:\ResearchFront\Claude\Obsidian-Paper-Tools\cli.py" remove-doi --path "%current_dir%\Clippings"
timeout /t 30
