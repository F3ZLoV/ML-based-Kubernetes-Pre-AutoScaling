#!/usr/bin/env python3
"""GKE 축소 재현 결과를 논문과 비교한다.

사용: python verification/analyze_repro.py [verification/gke_repro]
입력: <dir>/lead_time_{model}_{scenario}_run{N}.csv, <dir>/week8/{model}_{scenario}_run{N}_stats.csv
집계 규칙은 논문과 동일 (Lead·Aggressiveness: pooled mean / P95·P99·Err: run 평균).

ramp: run 1~3 이 원래 실행. 21:49~22:01(KST) 사이 클러스터 전체가 일시적으로 느려져
      HPA run3, GRU run1 의 모든 scale-out 이 12~15 s 로 측정됨 → 같은 조건으로 run 4 를 재측정.
      두 집계(원래 run 1~3 / 지연 구간 run 을 run 4 로 대체)를 모두 보고한다.
"""
import csv
import os
import statistics as st
import sys

D = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "gke_repro")
NOISE = 0.24


def run(model, sc, n):
    with open(os.path.join(D, f"lead_time_{model}_{sc}_run{n}.csv"), newline="") as f:
        rows = list(csv.DictReader(f))
    so = [r for r in rows if r["event_type"] == "scale_out"]
    with open(os.path.join(D, "week8", f"{model}_{sc}_run{n}_stats.csv"), newline="") as f:
        a = next(r for r in csv.DictReader(f) if r["Name"] == "Aggregated")
    jumps = sum(1 for r in so if int(r["to_replicas"]) - int(r["from_replicas"]) >= 20)
    drops = sum(1 for r in rows if r["event_type"] == "scale_down"
                and int(r["from_replicas"]) >= 15 and int(r["to_replicas"]) <= 3)
    return {"lead_ev": [float(r["lead_time_sec"]) for r in so],
            "aggr_ev": [int(r["to_replicas"]) - int(r["from_replicas"]) for r in so],
            "p95": float(a["95%"]), "p99": float(a["99%"]),
            "err": float(a["Failure Count"]) / float(a["Request Count"]) * 100,
            "reqs": int(a["Request Count"]), "jumps": jumps, "drops": drops}


def summary(model, sc, runs):
    rs = [run(model, sc, n) for n in runs]
    ev = [x for r in rs for x in r["lead_ev"]]
    return {"lead": st.mean(ev), "n_ev": len(ev), "lead_runs": [st.mean(r["lead_ev"]) for r in rs],
            "aggr": st.mean([x for r in rs for x in r["aggr_ev"]]),
            "p95": st.mean(r["p95"] for r in rs), "p99": st.mean(r["p99"] for r in rs),
            "err": st.mean(r["err"] for r in rs),
            "jumps": sum(r["jumps"] for r in rs), "drops": sum(r["drops"] for r in rs)}


def ramp_block(title, hr, gr):
    h, g = summary("hpa", "ramp", hr), summary("gru", "ramp", gr)
    d = h["lead"] - g["lead"]
    print(f"\n[ramp] {title}  (HPA run {hr}, GRU run {gr})")
    print(f"  {'':22s}{'HPA':>9s}{'GRU':>9s}   논문 HPA / GRU")
    print(f"  {'Lead (s, pooled)':22s}{h['lead']:9.2f}{g['lead']:9.2f}   2.92 / 2.48")
    print(f"  {'P95 (ms)':22s}{h['p95']:9.0f}{g['p95']:9.0f}   580 / 430")
    print(f"  {'P99 (ms)':22s}{h['p99']:9.0f}{g['p99']:9.0f}   733 / 573")
    print(f"  {'Err (%)':22s}{h['err']:9.3f}{g['err']:9.3f}   0.01 / 0.01")
    print(f"  {'Aggressiveness':22s}{h['aggr']:9.2f}{g['aggr']:9.2f}   3.14 / 3.24")
    print(f"  {'scale_out 이벤트':22s}{h['n_ev']:9d}{g['n_ev']:9d}")
    print(f"  run별 Lead  HPA {['%.2f' % x for x in h['lead_runs']]}  GRU {['%.2f' % x for x in g['lead_runs']]}")
    print(f"  → Lead: GRU가 HPA보다 {abs(d):.2f}s {'빠름' if d > 0 else '느림'} ({d / h['lead'] * 100:+.1f}%)"
          f"   | 논문: 0.44s 빠름 (+15.1%)")
    print(f"  → P95 : GRU가 {(h['p95'] - g['p95']) / h['p95'] * 100:+.1f}% 낮음   | 논문 +25.9%")
    print(f"  → P99 : GRU가 {(h['p99'] - g['p99']) / h['p99'] * 100:+.1f}% 낮음   | 논문 +21.8%")
    print(f"  → |Lead 차| {abs(d):.2f}s  vs 논문 노이즈 기준 {NOISE}s: {'초과' if abs(d) > NOISE else '이내'}")


ramp_block("원래 실행 run 1~3 (지연 구간 포함)", (1, 2, 3), (1, 2, 3))
ramp_block("지연 구간 run 을 run 4 로 대체", (1, 2, 4), (2, 3, 4))

print("\n[periodic] IV.4.3 진동 검증 (논문: Ensemble 대형 점프 6·급락 5 / LSTM 7·2 / GRU 0·0, 3 run 합계)")
for m in ("gru", "ensemble"):
    try:
        s = summary(m, "periodic", (1, 2, 3))
    except FileNotFoundError:
        print(f"  {m:9s} (결과 없음)")
        continue
    print(f"  {m:9s} 대형 점프(Δ≥20) {s['jumps']}  급락(≥15→≤3) {s['drops']}  | Lead {s['lead']:.2f}s  "
          f"P95 {s['p95']:.0f}ms  P99 {s['p99']:.0f}ms  Err {s['err']:.3f}%  Aggr {s['aggr']:.2f}")
