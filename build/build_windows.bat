@echo off
REM Build the Windows standalone app: dist\XRD Tools\XRD Tools.exe
REM
REM Must be run on an actual Windows machine (PyInstaller does not cross-compile
REM from macOS). Usage, from anywhere:
REM   build\build_windows.bat
REM
REM Requires Python 3.11/3.12 on PATH.

cd /d "%~dp0\.."

if not exist ".venv" (
    python -m venv .venv
)

call .venv\Scripts\activate.bat
pip install -q --upgrade pip
pip install -q -r requirements.txt

rmdir /s /q build_output 2>nul
rmdir /s /q dist 2>nul

pyinstaller build\xrd_tools.spec --noconfirm --distpath dist --workpath build_output

echo.
echo Done. Run it with:
echo   dist\"XRD Tools"\"XRD Tools.exe"
