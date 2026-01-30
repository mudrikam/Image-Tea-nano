@echo off
setlocal enabledelayedexpansion

set "BASE_DIR=%~dp0"
set "BASE_DIR=%BASE_DIR:~0,-1%"
set "PYTHON_DIR=%BASE_DIR%\python\Windows"
set "PYTHON_EXE=%PYTHON_DIR%\python.exe"
set "MAIN_PY=%BASE_DIR%\main.py"
set "REQUIREMENTS_FILE=%BASE_DIR%\requirements.txt"
set "TEMP_DIR=%BASE_DIR%\temp"
set "VERIFY_FILE=%TEMP_DIR%\.is_installation_verified"

:INSTALL_START

REM =====================================================================
REM Check if Python directory exists
REM =====================================================================
if exist "%PYTHON_DIR%" (
    echo Python installation found. Installing requirements...
    if exist "%BASE_DIR%\requirements.txt" (
        "%PYTHON_EXE%" -m pip install -r "%BASE_DIR%\requirements.txt" --no-warn-script-location
    ) else (
        echo Warning: requirements.txt not found. Skipping package installation.
    )
    goto :VERIFY
)

REM =====================================================================
REM Define variables for setup process
REM =====================================================================
REM Use application temp folder (not system %TEMP%) to avoid cross-process locks
set "PYTHON_ZIP=%TEMP_DIR%\python-3.12.10-embed-amd64.zip"
set "PYTHON_URL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
set "REQUIREMENTS_FILE=%BASE_DIR%\requirements.txt"

REM =====================================================================
REM Create Python directory
REM =====================================================================
echo Creating Python directory...
mkdir "%PYTHON_DIR%"

REM =====================================================================
REM Download and extract Python embedded distribution
REM =====================================================================
echo Downloading Python embedded distribution...
if not exist "%TEMP_DIR%" (
    echo Creating temp folder "%TEMP_DIR%"...
    mkdir "%TEMP_DIR%"
)
if exist "%PYTHON_ZIP%" (
    echo Removing previous temp archive "%PYTHON_ZIP%"...
    del /f /q "%PYTHON_ZIP%" >nul 2>&1 || echo Could not delete previous temp archive.
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "Try { Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_ZIP%' -UseBasicParsing -ErrorAction Stop } Catch { Write-Error $_; exit 1 }"
if exist "%PYTHON_ZIP%" (
    echo Download succeeded.
    echo Extracting Python...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Try { Expand-Archive -Path '%PYTHON_ZIP%' -DestinationPath '%PYTHON_DIR%' -Force -ErrorAction Stop } Catch { Write-Error $_; exit 1 }"
) else (
    echo Automatic download failed or blocked.
    echo A stable internet connection is required to let Image-Tea download Python automatically.
    echo You can manually install Python from: https://www.python.org/
    choice /M "Have you installed Python from https://www.python.org/?"
    if errorlevel 2 goto MANUAL_INSTALL_N
    if errorlevel 1 goto MANUAL_INSTALL_Y
)

goto :AFTER_DOWNLOAD

:MANUAL_INSTALL_N
echo Powershell or cmd on this machine does not permit Image-Tea to download Python automatically.
echo Please install Python manually from https://www.python.org/ and ensure it is added to PATH.
choice /M "After installing Python, press Y to continue or N to abort"
if errorlevel 2 (
    echo Installation aborted by user.
    goto :ABORT_INSTALL
) else (
    goto MANUAL_INSTALL_Y
)

:MANUAL_INSTALL_Y
nwhere python >nul 2>&1
if errorlevel 1 (
    echo Python executable not found in PATH.
    echo Ensure Python is installed and added to PATH, then run this installer again.
    choice /M "Have you added Python to PATH and installed it?"
    if errorlevel 2 goto MANUAL_INSTALL_N
    if errorlevel 1 goto MANUAL_INSTALL_Y
) else (
    for /f "delims=" %%P in ('where python') do set "USER_PY=%%P" & goto :RUN_INSTALL_PY
)

:RUN_INSTALL_PY
echo Found Python at %USER_PY%
"%USER_PY%" "%BASE_DIR%\install.py"
if errorlevel 1 (
    echo install.py failed to run or returned an error. Aborting.
    goto :ABORT_INSTALL
)

:AFTER_DOWNLOAD

REM =====================================================================
REM Set up pip in the embedded Python distribution
REM =====================================================================
echo Setting up pip...

if not exist "%REQUIREMENTS_FILE%" (
    echo Creating empty requirements.txt file...
    echo. > "%REQUIREMENTS_FILE%"
)

for %%F in ("%PYTHON_DIR%\python*._pth") do (
    type "%%F" > "%%F.tmp"
    echo import site >> "%%F.tmp"
    move /y "%%F.tmp" "%%F"
)

powershell -Command "Invoke-WebRequest -UseBasicParsing -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%PYTHON_DIR%\get-pip.py'"
"%PYTHON_DIR%\python.exe" "%PYTHON_DIR%\get-pip.py" --no-warn-script-location

echo Upgrading pip to the latest version...
"%PYTHON_DIR%\python.exe" -m pip install --upgrade pip --no-warn-script-location

if exist "%REQUIREMENTS_FILE%" (
    echo Installing required packages from requirements.txt...
    "%PYTHON_DIR%\python.exe" -m pip install -r "%REQUIREMENTS_FILE%" --no-warn-script-location
) else (
    echo Warning: requirements.txt not found. Skipping package installation.
)

:ABORT_INSTALL
echo Installation aborted or failed. Please fix the issue and try again.
exit /b 1

:VERIFY
echo.
echo ================================
echo Verifying Python and pip version:
echo ================================
"%PYTHON_EXE%" --version
if errorlevel 1 (
    if exist "%VERIFY_FILE%" del "%VERIFY_FILE%"
    echo Python not working. Reinstalling...
    rmdir /s /q "%PYTHON_DIR%"
    goto :INSTALL_START
)
"%PYTHON_EXE%" -c "import sys; print('Python executable:', sys.executable)"
if errorlevel 1 (
    if exist "%VERIFY_FILE%" del "%VERIFY_FILE%"
    echo Python not working. Reinstalling...
    rmdir /s /q "%PYTHON_DIR%"
    goto :INSTALL_START
)
"%PYTHON_EXE%" -m pip --version
if errorlevel 1 (
    if exist "%VERIFY_FILE%" del "%VERIFY_FILE%"
    echo Pip not working. Reinstalling...
    rmdir /s /q "%PYTHON_DIR%"
    goto :INSTALL_START
)

echo.
echo ================================
echo Verifying installed requirements:
echo ================================
set "REQ_MISSING=0"
if exist "%BASE_DIR%\requirements.txt" (
    "%PYTHON_EXE%" -m pip freeze > "%TEMP%\pip_freeze.txt"
    for /f "usebackq tokens=*" %%r in ("%BASE_DIR%\requirements.txt") do (
        set "REQ=%%r"
        if not "!REQ!"=="" if "!REQ:~0,1!" NEQ "#" (
            findstr /I /C:"!REQ!" "%TEMP%\pip_freeze.txt" >nul
            if errorlevel 1 (
                echo   [MISSING/DIFFERENT] !REQ!
                set "REQ_MISSING=1"
            ) else (
                echo   [OK] !REQ!
            )
        )
    )
    del "%TEMP%\pip_freeze.txt"
) else (
    echo requirements.txt not found, skipping requirements verification.
)

if "%REQ_MISSING%"=="1" (
    if exist "%VERIFY_FILE%" del "%VERIFY_FILE%"
    echo One or more dependencies are missing or incorrect. Reinstalling...
    rmdir /s /q "%PYTHON_DIR%"
    goto :INSTALL_START
)

echo.
echo Setup complete.

if not exist "%TEMP_DIR%" (
    mkdir "%TEMP_DIR%"
)
echo ok>"%VERIFY_FILE%"

endlocal
