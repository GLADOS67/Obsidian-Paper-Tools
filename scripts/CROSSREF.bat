@echo off
chcp 65001 > nul
python "C:\ResearchFront\Claude\Obsidian-Paper-Tools\cli.py" crossref
timeout /t 30
