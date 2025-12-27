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

for /f "usebackq delims=" %%a in (`powershell -Command "try {(Invoke-WebRequest -Uri '%RELEASES_API%').Content | ConvertFrom-Json | Select-Object -ExpandProperty tag_name} catch {''}"`) do set "TAG_NAME=%%a"

if "%TAG_NAME%"=="" (
    echo Failed to fetch release tag. Using fallback version v1.0.42
    set "TAG_NAME=v1.0.42"
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
powershell -Command "Invoke-WebRequest -Uri '%REPO_URL%' -OutFile '%ZIP_PATH%' -Headers @{'Cache-Control'='no-cache'}"

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
echo ================================
echo Update finished.
echo ================================
echo Press Y to launch the application now, or N to close.

choice /c yn /n /m "Launch the application now? (Y/N): "
if errorlevel 2 (
    echo Update finished. You can run the application later from Image Tea.exe
) else (
    echo.
    echo Launching Image Tea.exe...
    start "" "%EXE_PATH%"
)

cmd /c del "%~f0" & exit
endlocal