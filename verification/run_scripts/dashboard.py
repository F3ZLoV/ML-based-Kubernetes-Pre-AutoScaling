"""GKE 역검증 실시간 대시보드 — http://localhost:8765 (5초 자동 갱신)"""
import html
import os
import re
import subprocess
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
STAGES = [("ramp", "repro.log", ["hpa", "gru"], (1, 2, 3)),
          ("periodic", "periodic_gru.log", ["gru"], (1, 2, 3)),
          ("ramp", "rerun.log", ["hpa", "gru"], (4,)),        # 지연 구간 run 재측정
          ("periodic", "periodic_ensemble.log", ["ensemble"], (1, 2, 3))]
PLAN = [(sc, m, n) for sc, _, ms, ns in STAGES for m in ms for n in ns]
START = re.compile(r"▶ \[(\w+?)_(ramp|periodic)_run(\d)\] (\d\d:\d\d:\d\d) \(duration (\d+)s\)")
DONE = re.compile(r"✅ (\w+?)_(ramp|periodic)_run(\d): (\d+) scale_out events")
FILE = re.compile(r"(\w+?)_(ramp|periodic)_run(\d)")

# 한 번의 WSL 호출로 클러스터 상태와 run별 결과 CSV 요약을 가져온다 (--exec: Windows PATH 섞임 방지)
PROBE = r"""
export PATH=$HOME/google-cloud-sdk/bin:$PATH
echo "POD $(kubectl get deploy ticketbench-deploy -o jsonpath='{.spec.replicas} {.status.readyReplicas}' 2>/dev/null)"
echo "SCALER $(kubectl get hpa,scaledobject --no-headers 2>/dev/null | awk '{print $1}' | paste -sd, -)"
R=$HOME/repro_gke/results
for f in $R/week8/*_stats.csv; do [ -f "$f" ] && echo "STATS $(basename $f) $(grep ',Aggregated,' $f)"; done
for f in $R/lead_time_*.csv; do [ -f "$f" ] && echo "LEAD $(basename $f) $(grep -c ',scale_out,' $f) $(awk -F, 'NR==2{print $6}' $f)"; done
for f in $R/week8/*_stats_history.csv; do [ -f "$f" ] && echo "HIST $(basename $f) $(awk -F, 'NR==2{print $1}' $f) $(tail -1 $f | cut -d, -f1) $(( $(date +%s) - $(stat -c %Y $f) ))"; done
"""
DUR = {"ramp": 480, "periodic": 540}  # LoadShape 길이 (s)


def probe():
    try:
        return subprocess.run(["wsl", "--exec", "bash", "-c", PROBE],
                              capture_output=True, text=True, timeout=20).stdout.splitlines()
    except Exception:
        return []


def parse(lines):
    runs = {}
    for sc, log, _, _ in STAGES:  # 시작 시각·완료 여부만 로그에서 (태그 기준이라 순서 무관)
        p = os.path.join(HERE, log)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8", errors="replace") as f:
            for line in f:
                if m := START.search(line):
                    runs.setdefault((m[2], m[1], int(m[3])), {}).update(start=m[4], dur=int(m[5]))
                elif m := DONE.search(line):
                    runs.setdefault((m[2], m[1], int(m[3])), {})["done"] = True
    for line in lines:  # 통계는 결과 CSV 에서
        kind, _, rest = line.partition(" ")
        if kind not in ("STATS", "LEAD", "HIST"):
            continue
        name, _, data = rest.partition(" ")
        m = FILE.search(name.replace("lead_time_", ""))
        if not m:
            continue
        r = runs.setdefault((m[2], m[1], int(m[3])), {})
        if kind == "STATS" and data:
            v = data.split(",")  # Type,Name,Req,Fail,...,50%(11) ... 95%(16) 98% 99%(18)
            r.update(reqs=int(v[2]), fails=int(v[3]), p95=v[16], p99=v[18])
        elif kind == "LEAD":
            n_ev, *init = data.split()
            r.update(events=int(n_ev), init=init[0] if init else "–")
        elif kind == "HIST":
            v = data.split()
            if len(v) == 3 and v[0].isdigit() and v[1].isdigit():
                first, last, age = int(v[0]), int(v[1]), int(v[2])
                r.setdefault("start", datetime.fromtimestamp(first).strftime("%H:%M:%S"))
                r.setdefault("dur", DUR[m[2]])
                # 이력 파일이 30초 넘게 갱신되지 않고 부하 길이를 채웠으면 Locust 종료 = 측정 완료
                if age > 30 and last - first >= DUR[m[2]] - 20:
                    r["done"] = True
    return runs


def cluster(lines):
    pod = next((l[4:].split() for l in lines if l.startswith("POD ")), None)
    sc = next((l[7:].strip() for l in lines if l.startswith("SCALER ")), "")
    if not pod:
        return None, None, "조회 실패"
    return int(pod[0]), int(pod[1]) if len(pod) > 1 else 0, sc or "없음 (run 사이 중립 상태)"


def page():
    lines, now = probe(), datetime.now()
    runs = parse(lines)
    desired, ready, scaler = cluster(lines)
    done = sum(1 for k in PLAN if runs.get(k, {}).get("done"))
    rows, current = [], None
    for k in PLAN:
        sc, m, n = k
        r = runs.get(k)
        if r and r.get("done"):
            st, cls = "완료", "done"
        elif r and "start" in r:
            t0 = datetime.combine(now.date(), datetime.strptime(r["start"], "%H:%M:%S").time())
            el = (now - t0).total_seconds()
            st = f"부하 중 {int(el)}s / {r['dur']}s" if el < r["dur"] else "쿨다운·수렴 대기"
            cls, current = "run", (k, el, r["dur"])
        else:
            st, cls = "대기", "wait"
        r = r or {}
        f = lambda key, fmt="{}": fmt.format(r[key]) if key in r else "–"
        err = f"{r['fails'] / r['reqs'] * 100:.3f}%" if "reqs" in r and r["reqs"] else "–"
        rows.append(f"<tr class={cls}><td>{sc}</td><td>{m.upper()}</td><td>{n}</td><td>{st}</td>"
                    f"<td>{f('start')}</td><td>{f('events')}</td><td>{f('init')}</td><td>{f('reqs', '{:,}')}</td>"
                    f"<td>{err}</td><td>{f('p95')}</td><td>{f('p99')}</td></tr>")
    remaining = len(PLAN) - done
    eta = (now + timedelta(minutes=12 * remaining)).strftime("%H:%M") if remaining else "완료"
    cur_txt = "없음"
    if current:
        (sc, m, n), el, dur = current
        pct = min(100, el / dur * 100)
        cur_txt = (f"<b>{sc} / {m.upper()} run {n}</b> — {int(el)}s 경과"
                   f"<div class=bar><div style='width:{pct:.0f}%'></div></div>")
    pods = "조회 실패" if desired is None else f"목표 <b>{desired}</b> / Ready <b>{ready}</b>"
    return f"""<!doctype html><html><head><meta charset=utf-8><meta http-equiv=refresh content=5>
<title>GKE 역검증 진행</title><style>
body{{font:14px system-ui,sans-serif;background:#111;color:#ddd;margin:24px}}
h1{{font-size:20px;margin:0 0 4px}} .sub{{color:#888;margin-bottom:16px}}
.cards{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}}
.card{{background:#1c1c1c;border:1px solid #333;border-radius:8px;padding:12px 16px;min-width:200px}}
.card .k{{color:#888;font-size:12px}} .card .v{{font-size:18px;margin-top:4px}}
.bar{{height:6px;background:#333;border-radius:3px;margin-top:8px}} .bar div{{height:6px;background:#4c8dff;border-radius:3px}}
table{{border-collapse:collapse;width:100%}} th,td{{padding:6px 10px;border-bottom:1px solid #2a2a2a;text-align:left}}
th{{color:#888;font-weight:500}} tr.done td{{color:#9fd49f}} tr.run td{{color:#fff;background:#1d2a44}} tr.wait td{{color:#666}}
</style></head><body>
<h1>GKE 역검증 진행 상황</h1><div class=sub>{now:%H:%M:%S} 기준 · 5초마다 자동 갱신 ·
<a style=color:#4c8dff href="https://console.cloud.google.com/kubernetes/workload/overview?project={os.environ.get('PROJECT_ID', '')}">GKE 콘솔</a></div>
<div class=cards>
<div class=card><div class=k>진행</div><div class=v>{done} / {len(PLAN)} run 완료</div></div>
<div class=card><div class=k>지금 실행 중</div><div class=v style=font-size:14px>{cur_txt}</div></div>
<div class=card><div class=k>TicketBench 파드</div><div class=v>{pods}</div></div>
<div class=card><div class=k>활성 스케일러</div><div class=v style=font-size:13px>{html.escape(scaler)}</div></div>
<div class=card><div class=k>예상 종료</div><div class=v>{eta}</div></div>
</div>
<table><tr><th>시나리오</th><th>모델</th><th>run</th><th>상태</th><th>시작</th><th>scale-out</th>
<th>초기 파드</th><th>요청 수</th><th>에러율</th><th>P95 (ms)</th><th>P99 (ms)</th></tr>
{''.join(rows)}</table></body></html>"""


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = page().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("dashboard on http://localhost:8765", flush=True)
    HTTPServer(("127.0.0.1", 8765), H).serve_forever()
