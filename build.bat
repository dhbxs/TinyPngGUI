@echo off
cd /d "%~dp0"
echo Building TinifyCompress.exe ...
uv sync
uv run pyinstaller --noconfirm --clean TinifyCompress.spec
if errorlevel 1 (
  echo Build failed.
  exit /b 1
)
echo.
echo Done: dist\TinifyCompress.exe
echo Double-click to run. No install needed.
pause
