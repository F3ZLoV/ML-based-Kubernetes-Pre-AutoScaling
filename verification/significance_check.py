#!/usr/bin/env python3
"""논문의 주요 비교가 3회 반복으로 통계적으로 뒷받침되는지 검정한다.

사용: python verification/significance_check.py
입력: results/paper_dataset/ (84 run)

비교 단위는 run(조건당 3개). 리드 타임은 run별 scale_out 평균, P95·P99·Err 는 run별 Aggregated 값.
검정은 Welch t-test(양측). p < 0.05 를 '확인', 그 외는 '확인 안 됨'으로 표기한다.
0.24 s 기준: 같은 HPA·같은 부하 모양(aws_spike vs alibaba_spike)의 3회 평균 차이 하나를 잰 값.
"""
import csv
import os
import statistics as st

from scipy import stats

D = os.path.join(os.path.dirname(__file__), "..", "results", "paper_dataset")
M = ("hpa", "lstm", "gru", "ensemble")
SC = ("aws_spike", "alibaba_spike", "alibaba_periodic", "alibaba_wiki", "general_spike", "step", "ramp")


def rows(sc, m, n, kind):
    with open(os.path.join(D, f"{sc}__{m}__run{n}__{kind}.csv"), newline="") as f:
        return list(csv.DictReader(f))


def metric(sc, m, key):
    out = []
    for n in (1, 2, 3):
        if key == "lead":
            ev = [float(r["lead_time_sec"]) for r in rows(sc, m, n, "lead_time") if r["event_type"] == "scale_out"]
            out.append(st.mean(ev))
        else:
            a = next(r for r in rows(sc, m, n, "stats") if r["Name"] == "Aggregated")
            out.append({"p95": float(a["95%"]), "p99": float(a["99%"]),
                        "err": float(a["Failure Count"]) / float(a["Request Count"]) * 100}[key])
    return out


def test(label, a, b):
    p = stats.ttest_ind(a, b, equal_var=False).pvalue
    print(f"  {label:58s} {st.mean(a):9.3f} vs {st.mean(b):9.3f}   p = {p:.3f}  {'확인' if p < 0.05 else '확인 안 됨'}")
    return p


print("[1] 논문 본문의 핵심 비교")
test("ramp Lead: GRU vs HPA (15.1% 단축, 초록·IV.3.3·VI·Table 7·9)", metric("ramp", "gru", "lead"), metric("ramp", "hpa", "lead"))
test("ramp P95: GRU vs HPA (25.9% 개선, IV.3.3)", metric("ramp", "gru", "p95"), metric("ramp", "hpa", "p95"))
test("ramp P99: GRU vs HPA (22% 개선, Table 9)", metric("ramp", "gru", "p99"), metric("ramp", "hpa", "p99"))
test("gen-spike Lead: GRU vs HPA (0.12 s, 유의하지 않다고 서술)", metric("general_spike", "gru", "lead"), metric("general_spike", "hpa", "lead"))
test("gen-spike P95: GRU vs HPA (2배, Table 9·VI)", metric("general_spike", "gru", "p95"), metric("general_spike", "hpa", "p95"))
test("gen-spike P95: GRU vs LSTM (7배, IV.3.1)", metric("general_spike", "gru", "p95"), metric("general_spike", "lstm", "p95"))
for m in ("hpa", "gru", "ensemble"):
    test(f"gen-spike Err: LSTM vs {m.upper()} (10·39·108배, IV.3.1)", metric("general_spike", "lstm", "err"), metric("general_spike", m, "err"))

print("\n[2] Table 8 학습 데이터 민감도 (AWS vs Alibaba, 같은 부하 모양)")
for m in M:
    test(f"{m.upper()} Lead: Alibaba vs AWS", metric("alibaba_spike", m, "lead"), metric("aws_spike", m, "lead"))

print("\n[3] 0.24 s 기준의 크기 (같은 조건 3회 평균끼리 차이의 표준오차)")
for sc in ("ramp", "step", "general_spike"):
    for m in M:
        v = metric(sc, m, "lead")
        print(f"  {sc:14s} {m:9s} run SD {st.stdev(v):.2f} s  → 3회 평균 차이의 표준오차 ≈ {st.stdev(v) * (2 / 3) ** .5:.2f} s")

print("\n[4] 지표별 1위가 2위와 통계적으로 구분되는지 (Fig 2 승수)")
wins = {}
for key in ("lead", "p95", "p99", "err"):
    ok = 0
    for sc in SC:
        v = {m: metric(sc, m, key) for m in M}
        rank = sorted(M, key=lambda m: st.mean(v[m]))
        p = stats.ttest_ind(v[rank[0]], v[rank[1]], equal_var=False).pvalue
        ok += p < 0.05
        print(f"  {key:4s} {sc:17s} 1위 {rank[0]:9s} 2위 {rank[1]:9s} p = {p:.3f}")
    wins[key] = ok
print("  → 2위와 구분되는 1위 수 (7개 시나리오 중):", wins)

print("\n[5] IV.4.3 진동 (alibaba_periodic, run별 대형 점프+급락 횟수)")
osc = {}
for m in ("ensemble", "lstm", "gru"):
    c = []
    for n in (1, 2, 3):
        k = 0
        for r in rows("alibaba_periodic", m, n, "lead_time"):
            a, b = int(r["from_replicas"]), int(r["to_replicas"])
            k += (r["event_type"] == "scale_out" and b - a >= 20) or (r["event_type"] == "scale_down" and a >= 15 and b <= 3)
        c.append(k)
    osc[m] = c
    print(f"  {m:9s} run별 {c}")
print("  Ensemble vs GRU: 3 run 모두 Ensemble > GRU =", all(e > g for e, g in zip(sorted(osc['ensemble']), sorted(osc['gru']))))
