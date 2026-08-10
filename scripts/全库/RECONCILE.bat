@echo off
chcp 65001 > nul
set SCRIPT=C:\ResearchFront\Claude\Obsidian-Paper-Tools\cli.py

python "%SCRIPT%" reconcile %*
if errorlevel 1 goto :end
if "%~1"=="--force" goto :end

echo.
set /p CONFIRM="[DRY RUN] 执行迁移? (y/N): "
if /i "%CONFIRM%"=="y" (
    python "%SCRIPT%" reconcile --force
)
:end
