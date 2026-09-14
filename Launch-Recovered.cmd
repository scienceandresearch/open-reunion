@echo off
if exist "%~dp0local\recovered\catalog.json" (
  python "%~dp0run.py" recover "%~dp0local\recovered"
) else (
  python "%~dp0run.py" recover "%~dp0.."
)
if errorlevel 1 pause
