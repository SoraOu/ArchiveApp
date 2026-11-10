@echo off
setlocal
title Prepare files for an AI chat - Office Document Archive
cd /d "%~dp0"

rem Put this file in the ArchiveApp folder (next to HANDOFF.md). Double-click to use.
rem The menu is read from HANDOFF.md every time, so it changes when the handoff changes.

if not exist "HANDOFF.md" goto :no_handoff
if not exist "tools\handoff_tool.py" goto :no_tool

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" tools\handoff_tool.py %*
if errorlevel 1 pause
goto :end

:no_handoff
echo.
echo   HANDOFF.md was not found here.
echo   Put this file in the ArchiveApp folder, next to HANDOFF.md, and run it again.
echo.
pause
goto :end

:no_tool
echo.
echo   tools\handoff_tool.py was not found.
echo   Extract handoff_automation.zip into the ArchiveApp folder, then run this again.
echo.
pause

:end
endlocal
