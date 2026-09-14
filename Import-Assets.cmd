@echo off
if exist "%~dp0OpenReunion.exe" (
  "%~dp0OpenReunion.exe"
) else if exist "%~dp0local\recovered\catalog.json" (
  python "%~dp0run.py" recover "%~dp0local\recovered" --original-ui
  if errorlevel 1 pause
) else (
  python "%~dp0run.py" import-assets --output "%~dp0local\recovered" --play
  if errorlevel 1 pause
)
