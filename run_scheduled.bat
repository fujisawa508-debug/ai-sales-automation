@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist logs mkdir logs

for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TS=%%T

python main.py --scrape --research --save --all > "logs\%TS%.log" 2>&1

exit /b %ERRORLEVEL%
