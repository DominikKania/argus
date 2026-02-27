@echo off
cd /d C:\source\argus
call venv\Scripts\activate.bat

echo [%date% %time%] Auto-Ampel gestartet >> logs\scheduler.log
python argus.py auto-ampel >> logs\scheduler.log 2>&1
echo [%date% %time%] Beendet (Exit Code: %ERRORLEVEL%) >> logs\scheduler.log

deactivate
