@echo off
setlocal
cd /d "%~dp0backend"
if not exist "..\.venv\Scripts\python.exe" (
  echo No venv. Create one and: pip install -r ..\requirements-dev.txt pyinstaller
  exit /b 1
)
"..\.venv\Scripts\python.exe" -m PyInstaller Umbra.spec --noconfirm --clean
if errorlevel 1 exit /b 1
echo.
echo Built: backend\dist\Umbra\Umbra.exe
echo Test it: copy that WHOLE Umbra folder elsewhere and run it.