@echo off
rem Run the whole test-suite: JS first (fast, no venv needed), then Python.
cd /d "%~dp0.."
call npm test
if errorlevel 1 exit /b 1
rem Prefer the project venv so the server suite actually runs; fall back to PATH.
if exist ".venv\Scripts\python.exe" (set "PY=.venv\Scripts\python.exe") else (set "PY=python")
%PY% -m unittest discover -s tests -t . -v
pause
