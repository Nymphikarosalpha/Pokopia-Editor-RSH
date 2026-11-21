@echo off
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 tools\prepare_fork.py
) else (
    python tools\prepare_fork.py
)
if errorlevel 1 (
    echo.
    echo Preparation failed. Read the message above.
    pause
    exit /b 1
)
echo.
echo Finished. Review changes and commit them using GitHub Desktop.
pause
