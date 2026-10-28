@echo off
if defined WT_SESSION goto :run
where wt.exe >nul 2>nul || goto :run
start "" wt.exe -w new cmd /c ""%~f0" %*"
exit /b
:run
chcp 65001 > nul
setlocal
set "current_dir=%~dp0"
set "current_dir=%current_dir:~0,-1%"
python "C:\ResearchFront\Claude\Obsidian-Paper-Tools\cli.py" markdown --path "%current_dir%\Clippings" --depth 1
timeout /t 30
