@echo off
REM GUI가 안 뜰 때 원인을 보기 위한 콘솔 실행용 (평소엔 상위 폴더의 .vbs를 쓰세요).
cd /d "%~dp0..\.."
python tools\server-manager\app.py
if errorlevel 1 (
    echo.
    echo 오류가 발생했습니다. 위 메시지를 확인하세요.
    pause
)
