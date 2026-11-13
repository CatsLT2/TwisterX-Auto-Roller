@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo  TwisterX Auto Roller  --  EXE Builder
echo ============================================
echo.
echo  Builds ONE standalone EXE with Python, all packages and
echo  Tesseract OCR inside. The EXE runs on any Windows PC
echo  with nothing installed.
echo.

REM -- Check Python --------------------------------
python --version >nul 2>&1
if errorlevel 1 goto no_python

REM -- Clean build environment ----------------------
REM A private venv keeps unrelated packages (torch, pandas, ...) out of the EXE.
echo [1/3] Preparing a clean build environment...
if not exist "build\venv\Scripts\python.exe" python -m venv "build\venv"
if not exist "build\venv\Scripts\python.exe" goto pip_failed
set "VPY=build\venv\Scripts\python.exe"
"%VPY%" -m pip install --upgrade --quiet --disable-pip-version-check pip
"%VPY%" -m pip install --upgrade --disable-pip-version-check pyinstaller pyautogui pillow pytesseract mss requests customtkinter pystray
if errorlevel 1 goto pip_failed

REM -- Tesseract: needed here so it can be bundled --
echo.
echo [2/3] Checking for Tesseract...
if exist "%ProgramFiles%\Tesseract-OCR\tesseract.exe" goto tess_ok
if defined TESSERACT_DIR goto tess_ok
where tesseract >nul 2>&1
if not errorlevel 1 goto tess_ok
echo Tesseract not found - installing it so it can be bundled into the EXE...
winget install -e --id UB-Mannheim.TesseractOCR --silent --accept-package-agreements --accept-source-agreements
if exist "%ProgramFiles%\Tesseract-OCR\tesseract.exe" goto tess_ok
echo ERROR: Tesseract is required to build. Install it from
echo https://github.com/UB-Mannheim/tesseract/wiki and run this again.
pause
exit /b 1
:tess_ok

REM -- Build EXE -----------------------------------
echo.
echo [3/3] Building EXE with PyInstaller - this takes a few minutes...
"%VPY%" -m PyInstaller build.spec --clean --noconfirm
if errorlevel 1 goto build_failed

REM -- Optional code signing -----------------------
REM Set SIGN_PFX to your code-signing certificate (.pfx) and SIGN_PASSWORD to its
REM password before running this file, and the EXE is signed + timestamped.
if not defined SIGN_PFX goto sign_skip
set "SIGNTOOL="
for /f "delims=" %%S in ('where signtool 2^>nul') do if not defined SIGNTOOL set "SIGNTOOL=%%S"
if not defined SIGNTOOL for /f "delims=" %%S in ('dir /b /s "%ProgramFiles(x86)%\Windows Kits\10\bin\*signtool.exe" 2^>nul ^| findstr /i "x64"') do set "SIGNTOOL=%%S"
if not defined SIGNTOOL goto sign_notool
echo.
echo Signing "dist\TwisterX Auto Roller.exe" ...
"%SIGNTOOL%" sign /f "%SIGN_PFX%" /p "%SIGN_PASSWORD%" /fd sha256 /tr http://timestamp.digicert.com /td sha256 /d "TwisterX Auto Roller" "dist\TwisterX Auto Roller.exe"
if errorlevel 1 goto sign_failed
echo Signed OK.
goto sign_skip
:sign_notool
echo WARNING: signtool.exe not found - install the Windows SDK to sign. EXE left unsigned.
goto sign_skip
:sign_failed
echo WARNING: signing failed - check SIGN_PFX / SIGN_PASSWORD. EXE left unsigned.
:sign_skip

echo.
echo ============================================
echo  BUILD COMPLETE
echo  EXE is in:  "dist\TwisterX Auto Roller.exe"
echo ============================================
echo.
echo  The EXE is fully standalone - share just that one file.
echo  config.json and data.txt are created next to it on first run.
echo.
pause
exit /b 0

:no_python
echo ERROR: Python not found. Install Python 3.10+ from python.org and retry,
echo or just double-click "Start TwisterX Auto Roller.bat", which installs it for you.
pause
exit /b 1

:pip_failed
echo ERROR: pip install failed. Check your internet connection.
pause
exit /b 1

:build_failed
echo ERROR: PyInstaller build failed. See output above.
pause
exit /b 1
