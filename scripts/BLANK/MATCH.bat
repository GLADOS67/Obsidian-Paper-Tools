@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
set "BASEDIR=%~dp0"
python "C:\ResearchFront\Claude\Obsidian-Paper-Tools\cli.py" match "%BASEDIR:~0,-1%" %*
pause
