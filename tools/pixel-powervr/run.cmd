@echo off
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0run.py" %*
) else (
    python "%~dp0run.py" %*
)
pause
