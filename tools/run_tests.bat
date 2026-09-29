@echo off
rem Run the whole test-suite (no extra packages needed)
cd /d "%~dp0.."
python -m unittest discover -s tests -t . -v
pause
