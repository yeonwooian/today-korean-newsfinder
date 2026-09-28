@echo off
cd /d "%~dp0"
echo ========================================================
echo  [오늘도국어학원] 인스타 카드뉴스 자동생성 웹 대시보드
echo ========================================================
echo.
call .venv\Scripts\streamlit.exe run app.py --server.port 8501 --server.headless false
pause