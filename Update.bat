::[Bat To Exe Converter]
::
::fBE1pAF6MU+EWGPeyGAlIRdQcC2PPWy/S4EZ6aX17uSInngNUOMrfbDs1aaFJfJd6ETwFQ==
::YAwzoRdxOk+EWAjk
::fBw5plQjdDWDJHuR/U40FDJZTQOHcV+/B/gS6eb00/iCsXEUWeM4fbDP37WxNfAX61HhO58u2Ro=
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
::cxY6rQJ7JhzQF1fEqQJhZksaHErVXA==
::ZQ05rAF9IBncCkqN+0xwdVsFAlTMbCXtZg==
::ZQ05rAF9IAHYFVzEqQIZJRpTSUS2OWr6M6UY6fz+/Yo=
::eg0/rx1wNQPfEVWB+kM9LVsJDC2PPWy/RoEZ6ajO/+6GtkgPNA==
::fBEirQZwNQPfEVWB+kM9LVsJDC2PPWy/RoEZ6ajO/+6GtkgPNA==
::cRolqwZ3JBvQF1fEqQIZJRpTSUS2OWr6M6UY6fz+/Yo=
::dhA7uBVwLU+EWH2B50M5JhJVDDeWKW+zCdU=
::YQ03rBFzNR3SWATE0EcjKRJaRQXi
::dhAmsQZ3MwfNWATE0EcjKRJaRQXCD3+vArwTiA==
::ZQ0/vhVqMQ3MEVWAtB9wSA==
::Zg8zqx1/OA3MEVWAtB9wSA==
::dhA7pRFwIByZRRnk
::Zh4grVQjdDWDJHuR/U40FDJZTQOHcV+/B/gS6eb008OKo0oYFNY6ec/uyrCPNOUBpED8cPY=
::YB416Ek+ZG8=
::
::
::978f952a14a936cc963da21a135fa983
@echo off
setlocal

cd /d "%~dp0"

set "WORKER=%~dp0Update_Worker.bat"

echo Running update worker...
start "" "%WORKER%"

exit /b 0
endlocal
