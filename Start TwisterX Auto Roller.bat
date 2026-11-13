@echo off
setlocal EnableDelayedExpansion
title TwisterX Auto Roller - starting
cd /d "%~dp0"

REM ================================================================
REM  Double-click to run TwisterX Auto Roller from the .py file.
REM  Installs anything that's missing (Python, packages, Tesseract)
REM  the first time, then just starts the app on later runs.
REM ================================================================

set "PKGS=customtkinter pyautogui pillow pytesseract mss requests pystray"
set "PY="

REM ---- 1. Find Python ---------------------------------------------
call :find_python
if defined PY goto have_python

echo Python was not found. Installing Python 3.12...
where winget >nul 2>&1
if errorlevel 1 goto no_winget
winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
call :find_python
if defined PY goto have_python
echo.
echo Python was installed but could not be found yet.
echo Close this window and double-click the file again.
pause
exit /b 1

:no_winget
echo.
echo Could not install Python automatically - winget is not available.
echo Opening python.org: install Python and tick "Add python.exe to PATH",
echo then double-click this file again.
start "" https://www.python.org/downloads/windows/
pause
exit /b 1

:have_python
echo Using Python: !PY!

REM ---- 2. Python packages -----------------------------------------
"!PY!" -c "import customtkinter, pyautogui, PIL, pytesseract, mss, requests, pystray" >nul 2>&1
if not errorlevel 1 goto packages_ok
echo Installing missing Python packages - this only happens once...
"!PY!" -m pip install --upgrade pip --quiet --disable-pip-version-check
"!PY!" -m pip install --upgrade --quiet --disable-pip-version-check %PKGS%
"!PY!" -c "import customtkinter, pyautogui, PIL, pytesseract, mss, requests, pystray" >nul 2>&1
if errorlevel 1 goto pip_failed
:packages_ok

REM ---- 3. Tesseract OCR -------------------------------------------
call :find_tesseract
if defined TESS goto tess_ok
echo Tesseract OCR was not found. Installing it - Windows may ask for permission...
where winget >nul 2>&1
if errorlevel 1 goto tess_manual
winget install -e --id UB-Mannheim.TesseractOCR --silent --accept-package-agreements --accept-source-agreements
call :find_tesseract
if defined TESS goto tess_ok
:tess_manual
echo.
echo Tesseract could not be installed automatically.
echo Opening the download page. Install it with the default options,
echo then double-click this file again. The app will still open, but OCR won't work yet.
start "" https://github.com/UB-Mannheim/tesseract/wiki
pause
:tess_ok

REM ---- 4. Start the app without a console window --------------------
set "PYW=!PY:python.exe=pythonw.exe!"
if exist "!PYW!" (
    start "" "!PYW!" "%~dp0TwisterX_Auto_Roller.py"
) else (
    start "" "!PY!" "%~dp0TwisterX_Auto_Roller.py"
)
exit /b 0

:pip_failed
echo.
echo Installing the Python packages failed. Check your internet connection,
echo then double-click this file again.
pause
exit /b 1

REM ================================================================
:find_python
set "PY="
for %%V in (313 312 311 310) do (
    if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
    if not defined PY if exist "%ProgramFiles%\Python%%V\python.exe" set "PY=%ProgramFiles%\Python%%V\python.exe"
)
if defined PY goto :eof
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PY=%%P"
if defined PY goto :eof
REM Skip the Microsoft Store stub, which isn't a real Python.
for /f "delims=" %%P in ('where python 2^>nul') do (
    if not defined PY (
        echo %%P | find /i "WindowsApps" >nul || set "PY=%%P"
    )
)
goto :eof

:find_tesseract
set "TESS="
if exist "%~dp0tesseract\tesseract.exe" set "TESS=1"
if exist "%ProgramFiles%\Tesseract-OCR\tesseract.exe" set "TESS=1"
if exist "%ProgramFiles(x86)%\Tesseract-OCR\tesseract.exe" set "TESS=1"
if exist "%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe" set "TESS=1"
where tesseract >nul 2>&1 && set "TESS=1"
goto :eof
