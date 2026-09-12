@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python environment missing. Please follow README.md to install.
  pause
  exit /b 1
)
echo POC URL: http://127.0.0.1:8501
echo Keep this window open. Press Ctrl+C to stop.
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless false --browser.gatherUsageStats false
pause
