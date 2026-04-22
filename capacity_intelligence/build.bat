@echo off
cd /d "%~dp0"
echo Building Capacity Intelligence wheel...
python -m pip install --quiet --upgrade build
python -m build --wheel
echo.
echo Copying deploy scripts to dist\...
if not exist dist mkdir dist
copy /y deploy\install.bat dist\ >nul
copy /y deploy\run.bat dist\ >nul
copy /y deploy\README.txt dist\ >nul
echo.
echo Done. Share the contents of dist\ with users.
echo   dist\capacity_intelligence-*.whl
echo   dist\install.bat
echo   dist\run.bat
echo   dist\README.txt
echo.
pause
