@echo off
if defined WT_SESSION goto :run
where wt.exe >nul 2>nul || goto :run
start "" wt.exe -w new cmd /c ""%~f0" %*"
exit /b
:run
chcp 65001 > nul
python "C:\ResearchFront\Claude\Obsidian-Paper-Tools\cli.py" cited-by
timeout /t 30
