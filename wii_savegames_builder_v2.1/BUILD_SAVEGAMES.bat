@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "%~dp0wii_savegames_builder.py" %*
    goto :eof
)

where python >nul 2>nul
if %errorlevel%==0 (
    python "%~dp0wii_savegames_builder.py" %*
    goto :eof
)

echo.
echo ERROR: Python 3 was not found.
echo Install Python 3 and run this again.
echo.
pause
