@echo off
setlocal

set SCRIPT_PATH=
if exist "%CD%\skills\usage\scripts\usage.py" if exist "%CD%\plugin.json" set SCRIPT_PATH=%CD%\skills\usage\scripts\usage.py
if not defined SCRIPT_PATH if exist "%CD%\..\skills\usage\scripts\usage.py" if exist "%CD%\..\plugin.json" set SCRIPT_PATH=%CD%\..\skills\usage\scripts\usage.py
if not defined SCRIPT_PATH set SCRIPT_PATH=%~dp0..\skills\usage\scripts\usage.py
if not exist "%SCRIPT_PATH%" set SCRIPT_PATH=%USERPROFILE%\.gemini\config\skills\usage\scripts\usage.py
if not exist "%SCRIPT_PATH%" set SCRIPT_PATH=%USERPROFILE%\.gemini\config\plugins\antigravity-usage\skills\usage\scripts\usage.py

if not exist "%SCRIPT_PATH%" (
    echo Error: usage.py script not found. 1>&2
    exit /b 1
)

where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    py -3 "%SCRIPT_PATH%" %*
    exit /b %ERRORLEVEL%
)

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    python "%SCRIPT_PATH%" %*
    exit /b %ERRORLEVEL%
)

where python3 >nul 2>&1
if %ERRORLEVEL% equ 0 (
    python3 "%SCRIPT_PATH%" %*
    exit /b %ERRORLEVEL%
)

echo Error: Python was not found on PATH. 1>&2
exit /b 1
