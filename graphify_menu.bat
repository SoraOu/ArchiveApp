@echo off
setlocal EnableExtensions
title Graphify Menu - Office Document Archive
cd /d "%~dp0"
chcp 65001 >nul 2>&1
set "PYTHONUTF8=1"

rem Put this file in the ArchiveApp folder (next to app.py) and double-click it.
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

:menu
cls
echo ============================================
echo   Graphify - code map for the Archive project
echo ============================================
if exist "graphify-out\graph.json" (echo   Graph: built) else (echo   Graph: NOT built yet - run option 7)
echo   Folder: %CD%
echo.
echo   1  Install or update graphify
echo   2  Read the summary report
echo   3  Open the interactive graph in the browser
echo   4  Ask a question about the code
echo   5  Explain one part of the code
echo   6  Find the link between two parts
echo   7  Update the graph after code changes
echo   8  Auto-update while I work
echo   9  Register graphify with an AI assistant
echo   0  Exit
echo.
choice /c 1234567890 /n /m "Choose a number: "
if errorlevel 10 goto :exit
if errorlevel 9 goto :register
if errorlevel 8 goto :watch
if errorlevel 7 goto :update
if errorlevel 6 goto :path
if errorlevel 5 goto :explain
if errorlevel 4 goto :query
if errorlevel 3 goto :html
if errorlevel 2 goto :report
if errorlevel 1 goto :install
goto :menu

rem ---------- 1. install ----------
:install
echo.
echo   Installing graphify. This needs internet and can take a few minutes...
echo.
"%PY%" -m pip install --upgrade graphifyy
echo.
if errorlevel 1 (echo   Install failed. Read the messages above.) else (echo   Done.)
pause
goto :menu

rem ---------- 2. report ----------
:report
if not exist "graphify-out\GRAPH_REPORT.md" goto :no_graph
start "" notepad "graphify-out\GRAPH_REPORT.md"
goto :menu

rem ---------- 3. interactive graph ----------
:html
if not exist "graphify-out\graph.html" goto :no_graph
start "" "graphify-out\graph.html"
goto :menu

rem ---------- 4. query ----------
:query
call :need_tool
if "%TOOL_OK%"=="0" goto :no_tool
if not exist "graphify-out\graph.json" goto :no_graph
echo.
echo   Type your question in plain words, for example: how is a backup recorded
set "Q="
set /p "Q=  Question: "
if not defined Q goto :menu
set "Q=%Q:"=%"
echo.
"%PY%" -m graphify query "%Q%" | more
echo.
pause
goto :menu

rem ---------- 5. explain ----------
:explain
call :need_tool
if "%TOOL_OK%"=="0" goto :no_tool
if not exist "graphify-out\graph.json" goto :no_graph
echo.
echo   Type the name of a class, function or file, for example: Archive
set "N="
set /p "N=  Name: "
if not defined N goto :menu
set "N=%N:"=%"
echo.
"%PY%" -m graphify explain "%N%" | more
echo.
pause
goto :menu

rem ---------- 6. path ----------
:path
call :need_tool
if "%TOOL_OK%"=="0" goto :no_tool
if not exist "graphify-out\graph.json" goto :no_graph
echo.
echo   Type two names to see how they are connected, for example: MainWindow and backup_root
set "A="
set "B="
set /p "A=  From: "
if not defined A goto :menu
set /p "B=  To:   "
if not defined B goto :menu
set "A=%A:"=%"
set "B=%B:"=%"
echo.
"%PY%" -m graphify path "%A%" "%B%"
echo.
pause
goto :menu

rem ---------- 7. update ----------
:update
call :need_tool
if "%TOOL_OK%"=="0" goto :no_tool
echo.
echo   Rebuilding the graph from the code. No AI and no internet needed...
echo.
"%PY%" -m graphify update .
echo.
pause
goto :menu

rem ---------- 8. watch ----------
:watch
call :need_tool
if "%TOOL_OK%"=="0" goto :no_tool
start "Graphify auto-update - close this window to stop" cmd /k "%PY% -m graphify watch ."
echo.
echo   A new window opened. The graph now updates when you save code.
echo   Close that window to stop.
echo.
pause
goto :menu

rem ---------- 9. register with an AI assistant ----------
:register
call :need_tool
if "%TOOL_OK%"=="0" goto :no_tool
cls
echo   Register graphify with which AI assistant?
echo   (Only pick the one you will actually use.)
echo.
echo   1  Claude Code
echo   2  Codex
echo   3  Cursor
echo   4  Gemini CLI
echo   5  GitHub Copilot CLI
echo   6  Other - type its name
echo   7  Back
echo.
choice /c 1234567 /n /m "Choose a number: "
if errorlevel 7 goto :menu
if errorlevel 6 goto :reg_other
if errorlevel 5 goto :reg_copilot
if errorlevel 4 goto :reg_gemini
if errorlevel 3 goto :reg_cursor
if errorlevel 2 goto :reg_codex
set "PLAT=claude"
goto :reg_run
:reg_codex
set "PLAT=codex"
goto :reg_run
:reg_cursor
set "PLAT=cursor"
goto :reg_run
:reg_gemini
set "PLAT=gemini"
goto :reg_run
:reg_copilot
set "PLAT=copilot"
goto :reg_run
:reg_other
set "PLAT="
echo.
set /p "PLAT=  Assistant name (for example opencode, aider, kiro): "
if not defined PLAT goto :menu
set "PLAT=%PLAT: =%"
set "PLAT=%PLAT:"=%"
:reg_run
echo.
echo   Registering graphify with %PLAT% ...
echo.
"%PY%" -m graphify install --platform %PLAT%
echo.
pause
goto :menu

rem ---------- helpers ----------
:need_tool
set "TOOL_OK=1"
"%PY%" -m graphify --help >nul 2>&1
if errorlevel 1 set "TOOL_OK=0"
exit /b 0

:no_tool
echo.
echo   Graphify is not installed yet. Choose option 1 first.
echo.
pause
goto :menu

:no_graph
echo.
echo   No graph found in the graphify-out folder.
echo   Choose option 7 to build it from the code.
echo.
pause
goto :menu

:exit
endlocal
