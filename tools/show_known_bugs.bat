@echo off
rem Show WHY each known bug fails (tests marked known_bug)
cd /d "%~dp0.."
set OBSCURA_SHOW_BUGS=1
python -m unittest discover -s tests -t . 2>&1 | more
pause
