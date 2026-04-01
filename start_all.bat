@echo off
:: 한글 깨짐 방지 (UTF-8)
chcp 65001 >nul

echo ===================================================
echo 🚀 TicketBench AI AutoScaling Local Environment
echo ===================================================
echo.

:: 1. Uvicorn (AI 예측 서버) 실행
echo [1/3] AI 예측 서버 (Uvicorn) 를 시작합니다...
start powershell -NoExit -Command "$Host.UI.RawUI.WindowTitle = 'AI_Server'; Write-Host '▶ AI 예측 서버 실행 중...' -ForegroundColor Green; uvicorn ai_metrics_api:app --host 0.0.0.0 --port 8000 --reload"

:: 2. Pinggy (외부 터널링) 실행
echo [2/3] Pinggy 터널링을 시작합니다...
start powershell -NoExit -Command "$Host.UI.RawUI.WindowTitle = 'Pinggy_Tunnel'; Write-Host '▶ Pinggy 터널 생성 중...' -ForegroundColor Cyan; ssh -p 443 -R0:127.0.0.1:8000 a.pinggy.io"

:: 3. Locust (부하 테스트) 대기창 띄우기
echo [3/3] Locust 터미널을 준비합니다...
start powershell -NoExit -Command "$Host.UI.RawUI.WindowTitle = 'Locust_Test'; Write-Host '▶ 클러스터의 새 EXTERNAL-IP를 확인한 뒤 아래 명령어를 완성해서 실행하세요!' -ForegroundColor Yellow; Write-Host ''; Write-Host '명령어 예시: locust -f locustfile.py --host=http://123.45.67.89' -ForegroundColor White"

echo.
echo 모든 준비가 완료되었습니다. PowerShell 창 3개를 확인해 주세요!
pause