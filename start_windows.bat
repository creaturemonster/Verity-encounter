@echo off
cd /d "%~dp0"
if defined PYTHON (
  "%PYTHON%" run.py %*
) else (
  py run.py %*
)
pause
