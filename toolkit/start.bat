@echo off
REM Windows: double-click to set up (first time) and open the web app.
cd /d "%~dp0"
if not exist .venv (
  echo Creating virtual environment...
  py -3 -m venv .venv || python -m venv .venv
  call .venv\Scripts\activate
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate
)
if not exist .env copy .env.example .env && notepad .env
python -m tunimix seeds
start http://127.0.0.1:8765
python -m tunimix web
