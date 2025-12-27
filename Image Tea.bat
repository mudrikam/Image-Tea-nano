::[Bat To Exe Converter]
::
::fBE1pAF6MU+EWGPeyGAlIRdQcC2PPWy/S4EZ6aX17uSInkQTR/Y+dIOV2LWaQA==
::YAwzoRdxOk+EWAjk
::fBw5plQjdDWDJHuR/U40FDJZTQOHcV+/B/gS6eb00/iCsXEUWeM4fbDP37XAKeMcig==
::YAwzuBVtJxjWCl3EqQJgSA==
::ZR4luwNxJguZRRnk
::Yhs/ulQjdF+5
::cxAkpRVqdFKZSDk=
::cBs/ulQjdF+5
::ZR41oxFsdFKZSDk=
::eBoioBt6dFKZSDk=
::cRo6pxp7LAbNWATEpCI=
::egkzugNsPRvcWATEpCI=
::dAsiuh18IRvcCxnZtBJQ
::cRYluBh/LU+EWAnk
::YxY4rhs+aU+IeA==
::cxY6rQJ7JhzQF1fEqQJhZksaHEraXA==
::ZQ05rAF9IBncCkqN+0xwdVsFAlTMbCXqZg==
::ZQ05rAF9IAHYFVzEqQIZJRpTSUS2OWra
::eg0/rx1wNQPfEVWB+kM9LVsJDC2PPWy/RoEZ6Yg=
::fBEirQZwNQPfEVWB+kM9LVsJDC2PPWy/RoEZ6Yg=
::cRolqwZ3JBvQF1fEqQIZJRpTSUS2OWr6K7AI6ez6++vHhUgTUfA+bIDJug==
::dhA7uBVwLU+EWH2B50M5JhJVDDeWKW+zCdU=
::YQ03rBFzNR3SWATE0EcjKRJaRQXi
::dhAmsQZ3MwfNWATE0EcjKRJaRQXCD3+vArwTiA==
::ZQ0/vhVqMQ3MEVWAtB9wSA==
::Zg8zqx1/OA3MEVWAtB9wSA==
::dhA7pRFwIByZRRnk
::Zh4grVQjdDWDJHuR/U40FDJZTQOHcV+/B/gS6eb008OKo0oYFNY6ecHewrHu
::YB416Ek+ZG8=
::
::
::978f952a14a936cc963da21a135fa983
@echo off
setlocal




set "PYTHON_DIR=%~dp0python\Windows"
set "PYTHONW=%PYTHON_DIR%\pythonw.exe"
set "PYTHON_EXE=%PYTHON_DIR%\python.exe"
set "VERIFY_FILE=%~dp0temp\.is_installation_verified"
set "INSTALL_BAT=%~dp0install.bat"



REM Robust dependency check (folder, files, pip, requirements)
echo Checking Python environment and dependencies...
set "CHECK_FAILED=0"

REM Check python/Windows folder
if exist "%PYTHON_DIR%" (
    echo   [OK] python/Windows folder found.
) else (
    echo   [MISSING] python/Windows folder not found!
    set "CHECK_FAILED=1"
)

REM Check pythonw.exe
if exist "%PYTHONW%" (
    echo   [OK] pythonw.exe found.
) else (
    echo   [MISSING] pythonw.exe not found!
    set "CHECK_FAILED=1"
)

REM Check python.exe
if exist "%PYTHON_EXE%" (
    echo   [OK] python.exe found.
) else (
    echo   [MISSING] python.exe not found!
    set "CHECK_FAILED=1"
)

REM Check pip (pip.exe or pip module)
if "%CHECK_FAILED%"=="0" (
    "%PYTHON_EXE%" -m pip --version >nul 2>nul && echo   [OK] pip module found. || (echo   [MISSING] pip not working! & set "CHECK_FAILED=1")
)

REM Check requirements.txt
if exist "%~dp0requirements.txt" (
    echo   [OK] requirements.txt found.
) else (
    echo   [MISSING] requirements.txt not found!
    set "CHECK_FAILED=1"
)

REM Check .is_installation_verified (pelengkap, bukan utama)
if exist "%VERIFY_FILE%" (
    echo   [OK] .is_installation_verified found.
) else (
    echo   [MISSING] .is_installation_verified not found!
    set "CHECK_FAILED=1"
)


REM Check pip dependencies (optional, skip if pip already failed)
if "%CHECK_FAILED%"=="0" (
    "%PYTHON_EXE%" -m pip check >nul 2>nul && echo   [OK] pip dependencies valid. || (echo   [MISSING] pip dependencies not valid! & set "CHECK_FAILED=1")
)

REM === Robust: Check requirements.txt vs pip freeze ===
if "%CHECK_FAILED%"=="0" (
    "%PYTHON_EXE%" -m pip freeze > "%TEMP%\pip_freeze_check.txt"
    for /f "usebackq tokens=*" %%r in ("%~dp0requirements.txt") do (
        set "REQ=%%r"
        setlocal enabledelayedexpansion
        if not "!REQ!"=="" if not "!REQ:~0,1!"=="#" (
            findstr /I /C:"!REQ!" "%TEMP%\pip_freeze_check.txt" >nul
            if errorlevel 1 (
                echo   [MISSING] !REQ! not installed!
                endlocal & set "CHECK_FAILED=1"
            ) else (
                echo   [OK] !REQ! installed.
                endlocal
            )
        ) else (
            endlocal
        )
    )
    del "%TEMP%\pip_freeze_check.txt"
)



REM If any check failed, run install.bat for dependency recovery
if "%CHECK_FAILED%"=="1" (
    echo.
    echo =====================================
    echo  Python environment not detected, incomplete, or broken.
    echo  Running install.bat to repair dependencies...
    echo =====================================
    if exist "%INSTALL_BAT%" (
        call "%INSTALL_BAT%"
        echo.
        echo ================================
        echo  Dependency repair complete.
        echo  Launching Image Tea...
        echo ================================
        start "" "%PYTHONW%" "%~dp0main.py"
    ) else (
        echo ERROR: install.bat not found!
        pause
    )
    exit /b 0
)

REM If all checks passed, run main.py as usual
start "" "%PYTHONW%" "%~dp0main.py"

exit /b 0
endlocal
