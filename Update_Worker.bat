@echo off
setlocal

cd /d "%~dp0"

set "CUR_DIR=%~dp0"
set "RELEASES_API=https://api.github.com/repos/mudrikam/Image-Tea-nano/releases/latest"
set "ZIP_NAME=Image-Tea-nano.zip"
set "ZIP_PATH=%TEMP%\%ZIP_NAME%"
set "EXTRACT_PATH=%TEMP%\Image-Tea-nano-latest"
set "SELF=%~nx0"
set "PYTHONW=%CUR_DIR%python\Windows\pythonw.exe"
set "MAIN_PY=%CUR_DIR%main.py"
set "EXE_PATH=%CUR_DIR%Image Tea.exe"

echo Fetching latest release tag from GitHub...

for /f "usebackq delims=" %%a in (`powershell -Command "try {(Invoke-WebRequest -UseBasicParsing -Uri '%RELEASES_API%').Content | ConvertFrom-Json | Select-Object -ExpandProperty tag_name} catch {''}"`) do set "TAG_NAME=%%a"

if "%TAG_NAME%"=="" (
    echo Failed to fetch release tag. Using fallback version v1.0.51
    set "TAG_NAME=v1.0.51"
)

for /f %%b in ("%TAG_NAME%") do set "TAG_NAME=%%b"

echo TAG obtained: [%TAG_NAME%]

set "REPO_URL=https://github.com/mudrikam/Image-Tea-nano/releases/download/%TAG_NAME%/%ZIP_NAME%"

echo.
echo ============================================
echo Downloading file:
echo   Source : %REPO_URL%
echo   Target : %ZIP_PATH%
echo ============================================

echo Downloading latest release ZIP from GitHub...
powershell -Command "Invoke-WebRequest -UseBasicParsing -Uri '%REPO_URL%' -OutFile '%ZIP_PATH%' -Headers @{'Cache-Control'='no-cache'}"

if not exist "%ZIP_PATH%" (
    echo Failed to download ZIP file. Aborting update.
    exit /b 1
)

echo.
echo ============================================
echo Extracting ZIP:
echo   Source : %ZIP_PATH%
echo   Target : %EXTRACT_PATH%
echo ============================================

rmdir /s /q "%EXTRACT_PATH%" >nul 2>nul
powershell -Command "Expand-Archive -Path '%ZIP_PATH%' -DestinationPath '%EXTRACT_PATH%' -Force"

for /d %%D in ("%EXTRACT_PATH%\*") do set "EXTRACTED_ROOT=%%D"

if not defined EXTRACTED_ROOT (
    echo Extraction failed. Aborting update.
    del /f /q "%ZIP_PATH%"
    exit /b 1
)

echo.
echo ============================================
echo Replacing files with latest version
echo ============================================

setlocal enabledelayedexpansion
for /r "%EXTRACTED_ROOT%" %%F in (*) do (
    set "SRC=%%F"
    set "DST=!SRC:%EXTRACTED_ROOT%=%CUR_DIR%!"
    if /I not "!DST!"=="%CUR_DIR%%SELF%" (
        if not exist "!DST!" (
            for %%G in ("!DST!") do if not exist "%%~dpG" mkdir "%%~dpG" >nul 2>nul
            copy /y "!SRC!" "!DST!" >nul 2>nul
        ) else (
            copy /y "!SRC!" "!DST!" >nul 2>nul
        )
    )
)
endlocal

echo.
echo ============================================
echo Cleaning up temporary files:
echo   Deleting : %ZIP_PATH%
echo   Deleting : %EXTRACT_PATH%
echo ============================================

del /f /q "%ZIP_PATH%"
rmdir /s /q "%EXTRACT_PATH%"

echo.
echo ============================================
echo Update finished.
echo ============================================

REM Attempt to close any running embedded Image Tea process (pythonw) and relaunch automatically
set "PY_PIDS="
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "try { $p = Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq '%PYTHONW%' } | Select-Object -ExpandProperty ProcessId -ErrorAction SilentlyContinue; if ($p) { ($p -join ' ') } } catch { }"`) do set "PY_PIDS=%%p"
if defined PY_PIDS (
    echo Found running Image Tea process(es): %PY_PIDS%
    for %%i in (%PY_PIDS%) do (
        echo Stopping PID %%i ...
        taskkill /PID %%i /T /F >nul 2>nul || echo Failed to stop PID %%i
    )
    timeout /t 1 >nul
) else (
    echo No running embedded Image Tea process found.
)

echo Relaunching application now...
if exist "%EXE_PATH%" (
    start "" "%EXE_PATH%"
) else (
    if exist "%PYTHONW%" (
        start "" "%PYTHONW%" "%MAIN_PY%"
    ) else (
        echo Could not find launcher executable or embedded python to relaunch. Please start Image Tea manually.
    )
)

cmd /c del "%~f0" & exit
endlocal