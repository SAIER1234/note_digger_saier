@echo off
chcp 65001 >nul
title Note Digger - AI Piano Transcription

echo ========================================
echo   Note Digger - AI自动钢琴扒谱
echo ========================================
echo.

REM Kill old processes on common ports
for %%p in (8000 5000 3000) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%p.*LISTENING"') do (
        taskkill /F /PID %%a 2>nul
    )
)

REM Set Python path
set PYTHON=D:\Software\anaconda3\envs\bp311\python.exe
set BACKEND_DIR=d:\GitWarehouse\note_digger_saier\backend
set FRONTEND_DIR=d:\GitWarehouse\note_digger_saier\frontend

echo [1/2] Starting backend on http://localhost:8000 ...
start "Note Digger Backend" %PYTHON% -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
timeout /t 3 >nul

echo [2/2] Starting frontend on http://localhost:5000 ...
start "Note Digger Frontend" cmd /c "cd /d %FRONTEND_DIR% && npm run dev -- -p 5000"
timeout /t 5 >nul

echo.
echo ========================================
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5000
echo   API Docs: http://localhost:8000/docs
echo ========================================
echo.
echo 打开浏览器访问 http://localhost:5000 即可使用
echo.
echo 按任意键停止所有服务...
pause >nul

REM Cleanup on exit
taskkill /F /FI "WINDOWTITLE eq Note Digger Backend" 2>nul
taskkill /F /FI "WINDOWTITLE eq Note Digger Frontend" 2>nul
echo 服务已停止.
pause
