from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from prometheus_fastapi_instrumentator import Instrumentator
import math

app = FastAPI(title="TicketBench API")
Instrumentator().instrument(app).expose(app)

# DB 병목현상을 배제하기 위한 In-Memory 데이터베이스
TICKET_DB = {
    1: {"name": "2026 드림콘서트 (논문 스파이크 테스트용)", "total_seats": 5000, "available_seats": 5000},
}

# --- 프론트엔드 UI (HTML + CSS + JS) ---
HTML_UI = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TicketBench - 부하 테스트 티켓팅</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 flex items-center justify-center h-screen">
    <div class="bg-white p-8 rounded-lg shadow-xl w-96 text-center">
        <h1 class="text-3xl font-bold text-blue-600 mb-2">TicketBench 🎟️</h1>
        <p class="text-gray-500 text-sm mb-6">K8s Autoscaling Demo Server</p>
        
        <div class="border-2 border-blue-200 rounded p-4 mb-4 bg-blue-50">
            <h2 id="ticket-name" class="text-xl font-bold text-gray-800">로딩중...</h2>
            <p class="text-gray-600 mt-2">남은 좌석: <span id="seats" class="font-bold text-blue-600 text-2xl">...</span>석</p>
        </div>

        <div class="flex space-x-2">
            <button onclick="refreshStatus()" class="w-1/3 bg-gray-500 hover:bg-gray-600 text-white font-bold py-2 px-4 rounded transition">
                새로고침
            </button>
            <button onclick="buyTicket()" id="buy-btn" class="w-2/3 bg-red-500 hover:bg-red-600 text-white font-bold py-2 px-4 rounded transition flex justify-center items-center">
                <span>결제하기 (부하발생)</span>
            </button>
        </div>
        <p id="log" class="mt-4 text-sm font-semibold text-gray-700 h-6"></p>
    </div>

    <script>
        const ticketId = 1;

        // 1. 상태 새로고침 (중간 부하 API 호출)
        async function refreshStatus() {
            document.getElementById('log').innerText = "상태 확인 중...";
            try {
                const res = await fetch(`/api/v1/tickets/${ticketId}/status`);
                const data = await res.json();
                document.getElementById('seats').innerText = data.available_seats;
                document.getElementById('ticket-name').innerText = "2026 드림콘서트";
                document.getElementById('log').innerText = "새로고침 완료!";
                setTimeout(() => document.getElementById('log').innerText = "", 1500);
            } catch (e) {
                document.getElementById('log').innerText = "서버 응답 없음 (과부하)";
            }
        }

        // 2. 결제하기 (스파이크 고부하 API 호출)
        async function buyTicket() {
            const btn = document.getElementById('buy-btn');
            const log = document.getElementById('log');
            
            btn.innerHTML = `<svg class="animate-spin h-5 w-5 mr-2 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> 결제 진행 중...`;
            btn.disabled = true;
            btn.classList.add('opacity-50', 'cursor-not-allowed');
            log.innerText = "서버에서 무거운 연산 처리 중...";
            log.className = "mt-4 text-sm font-bold text-orange-500 h-6";

            const startTime = Date.now();

            try {
                const res = await fetch(`/api/v1/tickets/${ticketId}/buy`, { method: 'POST' });
                const data = await res.json();
                const latency = Date.now() - startTime;

                if (res.ok) {
                    document.getElementById('seats').innerText = data.seat_left;
                    log.innerText = `✅ 예매 성공! (응답시간: ${latency}ms)`;
                    log.className = "mt-4 text-sm font-bold text-green-600 h-6";
                } else {
                    log.innerText = `❌ 실패: ${data.detail}`;
                    log.className = "mt-4 text-sm font-bold text-red-600 h-6";
                }
            } catch (e) {
                log.innerText = "💥 서버 터짐 (Timeout)";
                log.className = "mt-4 text-sm font-bold text-red-600 h-6";
            } finally {
                btn.innerHTML = "결제하기 (부하발생)";
                btn.disabled = false;
                btn.classList.remove('opacity-50', 'cursor-not-allowed');
            }
        }

        // 페이지 로드 시 최초 데이터 1회 불러오기
        window.onload = refreshStatus;
    </script>
</body>
</html>
"""

# --- API 엔드포인트 ---

@app.get("/")
async def serve_ui():
    """웹 브라우저로 접속하면 화면(HTML)을 보여줍니다."""
    return HTMLResponse(content=HTML_UI)

@app.get("/api/v1/tickets/{ticket_id}/status")
async def get_ticket_status(ticket_id: int):
    """새로고침용 API (화면 갱신)"""
    if ticket_id not in TICKET_DB:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"available_seats": TICKET_DB[ticket_id]["available_seats"]}

@app.post("/api/v1/tickets/{ticket_id}/buy")
async def buy_ticket(ticket_id: int):
    """결제용 API (스파이크 부하 발생)"""
    if ticket_id not in TICKET_DB:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # [핵심] 서버 부하를 일으키는 무거운 루프 연산
    result = 0
    for i in range(5000000):  
        result += math.sqrt(i)

    if TICKET_DB[ticket_id]["available_seats"] > 0:
        TICKET_DB[ticket_id]["available_seats"] -= 1
        return {"seat_left": TICKET_DB[ticket_id]["available_seats"]}
    else:
        raise HTTPException(status_code=400, detail="Sold out")