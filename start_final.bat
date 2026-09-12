@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONDONTWRITEBYTECODE=1
echo Workshop-POC-FINAL: http://127.0.0.1:8502/
echo Keep this window open. Press Ctrl+C to stop.
".venv\Scripts\python.exe" -B -m streamlit run final_poc.py --server.port 8502 --server.address 127.0.0.1 --server.headless true --server.fileWatcherType none --browser.gatherUsageStats false
pause
