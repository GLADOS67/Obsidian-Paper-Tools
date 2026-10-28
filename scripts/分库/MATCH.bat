@echo off
if defined WT_SESSION goto :run
where wt.exe >nul 2>nul || goto :run
start "" wt.exe -w new cmd /c ""%~f0" %*"
exit /b
:run
chcp 65001 > nul
setlocal enabledelayedexpansion
set "BASEDIR=%~dp0"
python "C:\ResearchFront\Claude\Obsidian-Paper-Tools\cli.py" match "%BASEDIR:~0,-1%" %*
pause
