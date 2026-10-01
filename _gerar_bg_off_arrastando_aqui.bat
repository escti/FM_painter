@echo off
cd /D "%~dp0"
if "%~1"=="" (
  echo Arraste o PNG SEM FUNDO para gerar o json. Ex: efr_logo2_bg_off.png
  pause
  exit /b
)
python "%~dp0tools\gen.py" %* --profile profiles/bg_off_balanced.ini
pause
