@echo off
echo Installing Capacity Intelligence...
echo.
pip install --find-links="%~dp0" capacity-intelligence --upgrade
if %errorlevel% neq 0 (
    echo.
    echo Install failed.
    echo Ensure Python and pip are on your PATH.
    echo If your team uses virtual environments, activate it first, then re-run this script.
    pause
    exit /b 1
)
echo.
echo Installation complete. Run run.bat to start the app.
pause
