@echo off
rem Snapshot Umbra data (safe to run while the app is open)
cd /d "%~dp0.."
python tools\snapshot_data.py %*
pause
