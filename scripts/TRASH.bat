@echo off
setlocal
set "current_dir=%~dp0"
set "current_dir=%current_dir:~0,-1%"
python "C:\ResearchFront\Claude\Obsidian-Paper-Tools\cli.py" trash "%current_dir%"
timeout /t 30
