@echo off
setlocal
cd /d "%~dp0backend"
if not exist "..\.venv\Scripts\python.exe" (
  echo No venv. Create one and: pip install -r ..\requirements-dev.txt pyinstaller
  exit /b 1
)
"..\.venv\Scripts\python.exe" -m PyInstaller Obscura.spec --noconfirm --clean
if errorlevel 1 exit /b 1
echo.
echo Built: backend\dist\Obscura\Obscura.exe
echo Test it: copy that WHOLE Obscura folder elsewhere and run it.