@echo off
setlocal EnableDelayedExpansion

:: ============================================================================
::  PrivacyShield — Master Build Script  (revamped)
::  Usage:   build.bat [version]
::  Example: build.bat 1.0.0
::  Output:  dist_release\PrivacyShield Setup <version>.exe
:: ============================================================================

title PrivacyShield Builder
color 0A

set APP_VERSION=%~1
if "%APP_VERSION%"=="" set APP_VERSION=1.0.0

echo.
echo  ============================================================
echo    PrivacyShield Build System  v%APP_VERSION%
echo  ============================================================
echo.

:: ── Paths ─────────────────────────────────────────────────────────────────────
set ROOT=%~dp0
set ROOT=%ROOT:~0,-1%

set PYTHON=%ROOT%\tf_env\Scripts\python.exe
set PYINSTALLER=%ROOT%\tf_env\Scripts\pyinstaller.exe
set NODE=node
set NPM_CLI=%ProgramFiles%\nodejs\node_modules\npm\bin\npm-cli.js
set NODE_NPM=%NODE% "%NPM_CLI%"

set FRONTEND_DIST=%ROOT%\frontend\dist
set BACKEND_DIST=%ROOT%\backend_dist
set UPDATER_DIST=%ROOT%\dist
set ELECTRON_DIR=%ROOT%\electron
set RELEASE_DIR=%ROOT%\dist_release
set ASSETS_DIR=%ELECTRON_DIR%\assets

echo  Root:     %ROOT%
echo  Python:   %PYTHON%
echo  Electron: %ELECTRON_DIR%
echo.

:: ── Step 1 — Pre-flight checks ────────────────────────────────────────────────
echo [STEP 1/8] Checking prerequisites...

if not exist "%PYTHON%" (
    echo  [ERROR] Python not found: %PYTHON%
    echo          Create virtualenv: python -m venv tf_env
    pause & exit /b 1
)
for /f "tokens=*" %%v in ('"%PYTHON%" --version 2^>^&1') do echo  [OK] %%v

%NODE% --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Node.js not found. Install from https://nodejs.org
    pause & exit /b 1
)
for /f "tokens=*" %%v in ('%NODE% --version 2^>^&1') do echo  [OK] Node %%v

if not exist "%NPM_CLI%" (
    echo  [ERROR] npm not found at %NPM_CLI%
    echo          Try: where npm  to find the correct path
    pause & exit /b 1
)

:: Install/upgrade PyInstaller if missing
if not exist "%PYINSTALLER%" (
    echo  [INFO] Installing PyInstaller into tf_env...
    "%PYTHON%" -m pip install pyinstaller --quiet
    if errorlevel 1 (
        echo  [ERROR] Failed to install PyInstaller
        pause & exit /b 1
    )
)
for /f "tokens=*" %%v in ('"%PYINSTALLER%" --version 2^>^&1') do echo  [OK] PyInstaller %%v

:: Install required Python packages if missing
echo  [INFO] Ensuring Python dependencies...
"%PYTHON%" -m pip install pymupdf beautifulsoup4 pillow requests plyer win10toast --quiet --upgrade

:: ── Step 2 — Write version.json ───────────────────────────────────────────────
echo.
echo [STEP 2/8] Writing version.json v%APP_VERSION%...
(
    echo {
    echo   "version": "%APP_VERSION%",
    echo   "build_date": "%date% %time%",
    echo   "github_owner": "YOUR_GITHUB_USERNAME",
    echo   "github_repo":  "PrivacyShield"
    echo }
) > "%ROOT%\version.json"
echo  [OK] version.json written

:: ── Step 3 — Build React frontend ─────────────────────────────────────────────
echo.
echo [STEP 3/8] Building React frontend (Vite)...
cd /d "%ROOT%\frontend"

if not exist "node_modules" (
    echo  [INFO] Installing frontend npm packages...
    %NODE_NPM% install --legacy-peer-deps
    if errorlevel 1 ( echo  [ERROR] npm install failed & pause & exit /b 1 )
)

%NODE_NPM% run build
if errorlevel 1 (
    echo  [ERROR] Frontend Vite build failed!
    pause & exit /b 1
)
echo  [OK] Frontend built → %FRONTEND_DIST%

:: ── Step 4 — Bundle Python backend ────────────────────────────────────────────
echo.
echo [STEP 4/8] Bundling Python backend with PyInstaller...
cd /d "%ROOT%"

if exist "%BACKEND_DIST%" (
    echo  [INFO] Removing old backend build...
    rmdir /s /q "%BACKEND_DIST%"
)
if exist "%ROOT%\build_backend" rmdir /s /q "%ROOT%\build_backend"

"%PYINSTALLER%" backend_bundle.spec ^
    --distpath "%BACKEND_DIST%" ^
    --workpath "%ROOT%\build_backend" ^
    --noconfirm
if errorlevel 1 (
    echo  [ERROR] Backend PyInstaller failed!
    pause & exit /b 1
)
echo  [OK] Backend bundled → %BACKEND_DIST%\backend\

:: ── Step 5 — Bundle Updater ───────────────────────────────────────────────────
echo.
echo [STEP 5/8] Bundling Updater with PyInstaller...
cd /d "%ROOT%"

if not exist "%UPDATER_DIST%" mkdir "%UPDATER_DIST%"
if exist "%UPDATER_DIST%\updater.exe" del /q "%UPDATER_DIST%\updater.exe"
if exist "%ROOT%\build_updater" rmdir /s /q "%ROOT%\build_updater"

if not exist "%ROOT%\updater.spec" (
    echo  [WARN] updater.spec not found — creating it automatically...
    (
        echo # updater.spec — auto-generated
        echo import os
        echo a = Analysis(['updater.py'], pathex=['.'], binaries=[], datas=[], hiddenimports=['requests'], hookspath=[], runtime_hooks=[], excludes=[], win_no_prefer_redirects=False, win_private_assemblies=False, noarchive=False^)
        echo pyz = PYZ^(a.pure, a.zlib_data^)
        echo exe = EXE^(pyz, a.scripts, a.binaries, a.zipfiles, a.datas, name='updater', debug=False, bootloader_ignore_signals=False, strip=False, upx=True, upx_exclude=[], runtime_tmpdir=None, console=True, onefile=True^)
    ) > "%ROOT%\updater.spec"
)

"%PYINSTALLER%" updater.spec ^
    --distpath "%UPDATER_DIST%" ^
    --workpath "%ROOT%\build_updater" ^
    --noconfirm
if errorlevel 1 (
    echo  [ERROR] Updater PyInstaller failed!
    pause & exit /b 1
)
echo  [OK] Updater → %UPDATER_DIST%\updater.exe

:: ── Step 6 — Prepare Electron assets ─────────────────────────────────────────
echo.
echo [STEP 6/8] Preparing Electron assets...
if not exist "%ASSETS_DIR%" mkdir "%ASSETS_DIR%"

:: Generate icons if missing
if not exist "%ASSETS_DIR%\icon.ico" (
    echo  [INFO] Generating icons via generate_icon.py...
    "%PYTHON%" "%ROOT%\generate_icon.py"
)

:: Ensure tray16.png exists
if not exist "%ASSETS_DIR%\tray16.png" (
    echo  [INFO] Generating tray icon...
    "%PYTHON%" "%ROOT%\generate_icon.py"
)

:: Create license.txt
if not exist "%ASSETS_DIR%\license.txt" (
    echo PrivacyShield - Privacy Exposure Analysis Tool > "%ASSETS_DIR%\license.txt"
    echo Copyright ^(c^) 2026. All rights reserved.   >> "%ASSETS_DIR%\license.txt"
)

echo  [OK] Assets: icon.ico, tray16.png, license.txt ready

:: ── Step 7 — Install Electron deps ───────────────────────────────────────────
echo.
echo [STEP 7/8] Installing Electron build dependencies...
cd /d "%ELECTRON_DIR%"

%NODE_NPM% install
if errorlevel 1 (
    echo  [ERROR] npm install failed in electron\
    pause & exit /b 1
)
echo  [OK] Electron deps ready

:: ── Step 8 — electron-builder ────────────────────────────────────────────────
echo.
echo [STEP 8/8] Packaging with electron-builder (NSIS)...
cd /d "%ELECTRON_DIR%"

if exist "%RELEASE_DIR%" (
    echo  [INFO] Cleaning old release...
    rmdir /s /q "%RELEASE_DIR%"
)

:: Pass version to electron-builder via env
set npm_config_app_version=%APP_VERSION%

%NODE_NPM% run build
if errorlevel 1 (
    echo  [ERROR] electron-builder failed!
    pause & exit /b 1
)

:: ── Done ──────────────────────────────────────────────────────────────────────
echo.
echo  ============================================================
echo    BUILD COMPLETE!
echo  ============================================================
echo.
echo  Installer: %RELEASE_DIR%\PrivacyShield Setup %APP_VERSION%.exe
echo.
echo  What was included:
echo    Backend    : %BACKEND_DIST%\backend\backend.exe
echo    Updater    : %UPDATER_DIST%\updater.exe
echo    Frontend   : %FRONTEND_DIST%\
echo    Database   : Created fresh per-user in %%APPDATA%%\PrivacyShield\
echo.
echo  Next steps:
echo    1. Test installer on a clean machine
echo    2. Upload to GitHub Releases as: PrivacyShield-Setup-%APP_VERSION%.exe
echo    3. Tag the release: v%APP_VERSION%
echo    4. Replace YOUR_GITHUB_USERNAME in version.json + updater.py
echo.
pause
