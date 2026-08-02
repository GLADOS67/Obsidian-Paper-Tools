@echo off
chcp 936 > nul
setlocal enabledelayedexpansion
:start
echo ========================================
echo  Drag .md here or paste path / q=quit
echo ========================================
echo.
set "SRC="
set /p "SRC=Source .md: "
if /i "!SRC!"=="q" goto end
if "!SRC!"=="" goto start
set "SRC=!SRC:"=!"
if not exist "!SRC!" (
    echo [ERR] Not found: !SRC!
    echo.
    goto start
)
echo.
set "TARGET="
set /p "TARGET=Target folder: "
set "TARGET=!TARGET:"=!"
if "!TARGET!"=="" (
    echo [ERR] Empty target
    echo.
    goto start
)
echo.
echo Source: !SRC!
echo Target: !TARGET!
echo.
python "C:\ResearchFront\Claude\Obsidian-Paper-Tools\cli.py" archive -s "!SRC!" -t "!TARGET!"
echo.
goto start
:end
exit /b
