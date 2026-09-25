#!/usr/bin/env python3
"""논문 최종본(12쪽, 표 9개)의 모든 수치 주장을 84 run 원시 데이터로 재계산해 대조한다.

사용: python verification/verify_paper.py   (저장소 루트에서, 표준 라이브러리만 사용)
데이터: results/paper_dataset/{scenario}__{model}__run{N}__{lead_time|stats|stats_history}.csv

집계 규칙 (논문과 동일)
- Lead Time, Aggressiveness : 3 run 의 scale_out 이벤트를 합쳐 평균 (pooled mean)
- P95 / P99 / Err            : run 별 Locust Aggregated 값의 3 run 평균
- Time-to-Peak               : run 별 (최초 scale_out → 최대 replica 도달) 의 3 run 평균
"""
import csv
import os
import statistics as st
import sys
from collections import Counter
from datetime import datetime

DS = os.path.join(os.path.dirname(__file__), "..", "results", "paper_dataset")
M = ["hpa", "lstm", "gru", "ensemble"]
S = ["aws_spike", "alibaba_spike", "alibaba_periodic", "alibaba_wiki",
     "general_spike", "step", "ramp"]
ML = ["lstm", "gru", "ensemble"]


def rows(s, m, n, kind):
    with open(os.path.join(DS, f"{s}__{m}__run{n}__{kind}.csv"), newline="") as f:
        return list(csv.DictReader(f))


def agg(rs):
    return next(r for r in rs if r.get("Name") == "Aggregated")


# ---------------------------------------------------------------- 집계
lead, aggr, ttp, p95, p99, err = {}, {}, {}, {}, {}, {}
etypes = Counter()
run_max = []
for s in S:
    for m in M:
        ev, dl, tps, a95, a99, ae = [], [], [], [], [], []
        for n in (1, 2, 3):
            lr = rows(s, m, n, "lead_time")
            etypes.update(r["event_type"] for r in lr)
            so = [r for r in lr if r["event_type"] == "scale_out"]
            ev += [float(r["lead_time_sec"]) for r in so]
            dl += [int(r["to_replicas"]) - int(r["from_replicas"]) for r in so]
            if so:
                mx = max(int(r["to_replicas"]) for r in so)
                run_max.append(mx)
                t = lambda r: datetime.fromisoformat(r["timestamp"])
                tps.append((min(t(r) for r in so if int(r["to_replicas"]) == mx) - t(so[0])).total_seconds())
            a = agg(rows(s, m, n, "stats"))
            a95.append(float(a["95%"])); a99.append(float(a["99%"]))
            ae.append(float(a["Failure Count"]) / float(a["Request Count"]) * 100)
        lead[s, m] = st.mean(ev); aggr[s, m] = st.mean(dl); ttp[s, m] = st.mean(tps)
        p95[s, m] = st.mean(a95); p99[s, m] = st.mean(a99); err[s, m] = st.mean(ae)

results = []  # (section, label, paper, data, ok)


def ck(sec, label, paper, data, tol):
    results.append((sec, label, paper, data, abs(data - paper) <= tol))


def pct(a, b):  # b 대비 a 가 얼마나 빠른가 (%)
    return (b - a) / b * 100


# ---------------------------------------------------------------- IV.2 / III.5 이벤트 수
ck("IV.2", "scale_out 이벤트 수", 545, etypes["scale_out"], 0)
ck("IV.2", "scale_down 이벤트 수", 366, etypes["scale_down"], 0)
ck("III.5", "scale_out_partial (평균 제외)", 1, etypes["scale_out_partial"], 0)
ck("IV.2", "전체 스케일링 이벤트", 912, sum(etypes.values()), 0)
ck("IV.4.1", "25 도달 run 수 (나머지는 18~24)", 80, sum(x == 25 for x in run_max), 0)
ck("IV.4.1", "최대 도달 replica 최솟값", 18, min(run_max), 0)

# ---------------------------------------------------------------- Table 4
T4 = {"aws_spike": (3.08, 4.76, 3.10, 2.57), "alibaba_spike": (3.32, 5.41, 3.62, 4.67),
      "alibaba_periodic": (3.76, 5.73, 5.71, 6.65), "alibaba_wiki": (2.70, 5.71, 4.16, 7.41),
      "general_spike": (3.52, 3.64, 3.40, 3.84), "step": (2.67, 3.53, 3.02, 3.38),
      "ramp": (2.92, 2.93, 2.48, 2.94)}
for s, v in T4.items():
    for i, m in enumerate(M):
        ck("Table 4", f"{s}/{m} Lead", v[i], lead[s, m], 0.006)
wins = Counter(min(M, key=lambda m: lead[s, m]) for s in S)
for m, w in (("hpa", 4), ("gru", 2), ("ensemble", 1), ("lstm", 0)):
    ck("IV.2", f"Lead 1위 횟수 {m}", w, wins[m], 0)
r = [lead[s, "lstm"] / lead[s, "hpa"] for s in ("alibaba_spike", "alibaba_periodic", "alibaba_wiki")]
ck("IV.2", "LSTM/HPA 배율 최소 (1.5)", 1.5, min(r), 0.05)
ck("IV.2", "LSTM/HPA 배율 최대 (2.1)", 2.1, max(r), 0.05)

# ---------------------------------------------------------------- Table 5
T5 = {"general_spike": {"hpa": (2200, 2733, 0.13), "lstm": (8000, 8900, 1.30),
                        "gru": (1100, 1333, 0.03), "ensemble": (2067, 2533, 0.01)},
      "step": {"hpa": (437, 593, 0.00), "lstm": (813, 1133, 0.04),
               "gru": (453, 650, 0.02), "ensemble": (707, 987, 0.05)},
      "ramp": {"hpa": (580, 733, 0.01), "lstm": (677, 903, 0.04),
               "gru": (430, 573, 0.01), "ensemble": (533, 693, 0.05)}}
for s, d in T5.items():
    for m, (a, b, e) in d.items():
        ck("Table 5", f"{s}/{m} P95", a, p95[s, m], 0.6)
        ck("Table 5", f"{s}/{m} P99", b, p99[s, m], 0.6)
        ck("Table 5", f"{s}/{m} Err", e, err[s, m], 0.005)

# ---------------------------------------------------------------- IV.3 본문
gs, rp = "general_spike", "ramp"
ck("IV.3.1", "gen-spike 4모델 Lead 격차 ≤0.44", 0.44,
   max(lead[gs, m] for m in M) - min(lead[gs, m] for m in M), 0.006)
ck("IV.3.1", "GRU P95 vs LSTM '7배 이상'", 7.27, p95[gs, "lstm"] / p95[gs, "gru"], 0.05)
ck("IV.3.1", "LSTM Err vs HPA '약 10배'", 10, err[gs, "lstm"] / err[gs, "hpa"], 0.5)
ck("IV.3.1", "LSTM Err vs GRU '약 39배'", 39, err[gs, "lstm"] / err[gs, "gru"], 1.5)
ck("IV.3.1", "LSTM Err vs Ensemble '약 108배'", 108, err[gs, "lstm"] / err[gs, "ensemble"], 5)
ck("IV.3.2", "step GRU−HPA P95 차 16ms", 16, p95["step", "gru"] - p95["step", "hpa"], 1)
step_hpa_all = all(min(M, key=lambda m: d[("step", m)]) == "hpa" for d in (lead, p95, p99, err))
ck("IV.3.2", "step: HPA 4지표 모두 1위 (1=참)", 1, int(step_hpa_all), 0)
ck("IV.3.2", "Ensemble Aggr / HPA '약 2배'", 2.0, aggr["step", "ensemble"] / aggr["step", "hpa"], 0.15)
ck("IV.3.3", "ramp GRU Lead 단축 15.1%", 15.1, pct(lead[rp, "gru"], lead[rp, "hpa"]), 0.1)
ck("IV.3.3", "ramp GRU P95 개선 25.9%", 25.9, pct(p95[rp, "gru"], p95[rp, "hpa"]), 0.1)
ck("Abstract", "ramp GRU−HPA Lead 차 0.44s", 0.44, lead[rp, "hpa"] - lead[rp, "gru"], 0.006)
# 아래 셋은 논문이 반올림된 표 값으로 계산한 파생 수치 → 표 값 기준으로 판정하고 원시값은 따로 보고
t4 = lambda s, m: T4[s][M.index(m)]
ck("Abstract", "gen-spike GRU−HPA Lead 차 0.12s (표 값 기준)", 0.12, t4(gs, "hpa") - t4(gs, "gru"), 0.006)
ROUNDED_NOTE = [("gen-spike GRU−HPA Lead 차", "0.12 s", f"{lead[gs, 'hpa'] - lead[gs, 'gru']:.3f} s")]
ck("Abstract", "run 간 변동 0.24s (AWS vs Alibaba spike HPA)", 0.24,
   lead["alibaba_spike", "hpa"] - lead["aws_spike", "hpa"], 0.006)
ck("Table 9", "SPIKE GRU P95 = HPA의 1/2 ('2배 우수')", 2.0, p95[gs, "hpa"] / p95[gs, "gru"], 0.01)

# ---------------------------------------------------------------- Table 6
T6t = {"general_spike": (86.2, 57.6, 64.2, 63.7), "step": (151.6, 219.5, 155.2, 169.2),
       "ramp": (105.5, 169.0, 106.4, 144.4)}
T6a = {"general_spike": (4.29, 9.80, 7.44, 10.82), "step": (3.83, 6.96, 4.22, 7.29),
       "ramp": (3.14, 4.29, 3.24, 4.12)}
for s in T6t:
    for i, m in enumerate(M):
        ck("Table 6", f"{s}/{m} TTP", T6t[s][i], ttp[s, m], 0.06)
        ck("Table 6", f"{s}/{m} Aggr", T6a[s][i], aggr[s, m], 0.006)
syn = ("general_spike", "step", "ramp")
ck("IV.4.2", "HPA Aggr 최소 3.1", 3.1, min(aggr[s, "hpa"] for s in syn), 0.05)
ck("IV.4.2", "HPA Aggr 최대 4.3", 4.3, max(aggr[s, "hpa"] for s in syn), 0.05)
ck("IV.4.2", "ML Aggr 최소 3.2", 3.2, min(aggr[s, m] for s in syn for m in ML), 0.05)
ck("IV.4.2", "ML Aggr 최대 10.8", 10.8, max(aggr[s, m] for s in syn for m in ML), 0.05)
ml_ratio = [aggr[s, m] / aggr[s, "hpa"] for s in syn for m in ML]
ck("IV.4.2", "ML/HPA 배율 최소 1.0", 1.0, min(ml_ratio), 0.05)
ck("IV.4.2", "ML/HPA 배율 최대 2.5", 2.5, max(ml_ratio), 0.05)
ck("IV.4.2", "GRU/HPA step 1.10배", 1.10, aggr["step", "gru"] / aggr["step", "hpa"], 0.006)
ck("IV.4.2", "GRU/HPA ramp 1.03배", 1.03, aggr["ramp", "gru"] / aggr["ramp", "hpa"], 0.006)
le = [aggr[s, m] / aggr[s, "hpa"] for s in syn for m in ("lstm", "ensemble")]
ck("IV.4.2", "LSTM·Ensemble/HPA 최소 1.3", 1.3, min(le), 0.05)
ck("IV.4.2", "LSTM·Ensemble/HPA 최대 2.5", 2.5, max(le), 0.05)

# ---------------------------------------------------------------- IV.4.3 oscillation (periodic)
for m, (jp, dr) in {"ensemble": (6, 5), "lstm": (7, 2), "gru": (0, 0)}.items():
    j = d = 0
    for n in (1, 2, 3):
        for r in rows("alibaba_periodic", m, n, "lead_time"):
            a, b = int(r["from_replicas"]), int(r["to_replicas"])
            if r["event_type"] == "scale_out" and b - a >= 20:
                j += 1
            if r["event_type"] == "scale_down" and a >= 15 and b <= 3:
                d += 1
    ck("IV.4.3", f"periodic {m} 대형 점프(Δ≥20)", jp, j, 0)
    ck("IV.4.3", f"periodic {m} 급락(≥15→≤3)", dr, d, 0)

# ---------------------------------------------------------------- Table 7 / Table 8
for m, want in (("lstm", -111.6), ("gru", -54.4), ("ensemble", -174.6)):
    ck("Table 7", f"통제 전(wiki) {m}", want, pct(lead["alibaba_wiki", m], lead["alibaba_wiki", "hpa"]), 0.6)
for m, want in (("lstm", -0.3), ("gru", 15.1), ("ensemble", -0.7)):
    ck("Table 7", f"통제 후(ramp) {m}", want, pct(lead["ramp", m], lead["ramp", "hpa"]), 0.15)
ck("Table 8", "HPA 베이스라인 변동 +7.8%", 7.8,
   (lead["alibaba_spike", "hpa"] / lead["aws_spike", "hpa"] - 1) * 100, 0.1)
for m, raw, hn in (("lstm", 13.7, 5.4), ("gru", 16.8, 8.3), ("ensemble", 81.7, 68.6)):
    # Table 8 은 Table 4 의 반올림 값(3.08, 3.32, 2.57, 4.67 …)으로 계산되어 있다
    a, b = t4("aws_spike", m), t4("alibaba_spike", m)
    ha, hb = t4("aws_spike", "hpa"), t4("alibaba_spike", "hpa")
    ck("Table 8", f"{m} Δ% (표 값 기준)", raw, (b / a - 1) * 100, 0.06)
    ck("Table 8", f"{m} Δ% HPA 정규화 (표 값 기준)", hn, ((b / hb) / (a / ha) - 1) * 100, 0.06)
    ra, rb = lead["aws_spike", m], lead["alibaba_spike", m]
    ROUNDED_NOTE.append((f"Table 8 {m} Δ% / 정규화", f"{raw}% / {hn}%",
                         f"{(rb / ra - 1) * 100:.1f}% / "
                         f"{((rb / lead['alibaba_spike', 'hpa']) / (ra / lead['aws_spike', 'hpa']) - 1) * 100:.1f}%"))

# ---------------------------------------------------------------- Fig 2 1위 횟수
for name, d, want in (("Lead", lead, (4, 0, 2, 1)), ("P95", p95, (2, 0, 4, 1)),
                      ("P99", p99, (2, 0, 4, 1)), ("Err", err, (3, 0, 2, 2))):
    c = Counter(min(M, key=lambda m: d[s, m]) for s in S)
    for i, m in enumerate(M):
        ck("Fig 2", f"{name} 1위 {m}", want[i], c[m], 0)

# ---------------------------------------------------------------- III.4 안전 장치 재적용
# ai_metrics_api.py 분기: (u<50 and rps<50) → 저부하 우회 / u>350 → 25 고정 / 나머지 → 모델+하한
tot = bypass = cap = 0
cap_s = Counter(); tot_s = Counter()
for s in S:
    for m in ML:
        for n in (1, 2, 3):
            for r in rows(s, m, n, "stats_history"):
                if r.get("Name") != "Aggregated":
                    continue
                u, q = float(r["User Count"]), float(r["Requests/s"])
                tot += 1; tot_s[s] += 1
                if u < 50 and q < 50:
                    bypass += 1
                elif u > 350:
                    cap += 1; cap_s[s] += 1
ck("III.4", "ML run 관측 수 31,477", 31477, tot, 0)
ck("III.4", "user_count>350 고정 38.7%", 38.7, cap / tot * 100, 0.06)
ck("III.4", "저부하 우회 9.5%", 9.5, bypass / tot * 100, 0.06)
ck("III.4", "나머지 51.9%", 51.9, (tot - cap - bypass) / tot * 100, 0.06)
ck("IV.3.1", "gen-spike 상한 고정 58.8%", 58.8, cap_s["general_spike"] / tot_s["general_spike"] * 100, 0.06)
ck("IV.3.3", "ramp 상한 고정 56.1%", 56.1, cap_s["ramp"] / tot_s["ramp"] * 100, 0.06)

# ---------------------------------------------------------------- 출력
ok = sum(r[4] for r in results)
print(f"검증 항목 {len(results)}개 중 통과 {ok}개, 불일치 {len(results) - ok}개\n")
bad = [r for r in results if not r[4]]
if bad:
    print("불일치 목록:")
    for sec, label, paper, data, _ in bad:
        print(f"  [{sec}] {label}: 논문 {paper} / 데이터 {data:.4f}")
print("반올림된 표 값으로 계산된 파생 수치 (논문 / 원시 데이터로 직접 계산):")
for label, paper, raw in ROUNDED_NOTE:
    print(f"  {label}: {paper} / {raw}")
sec_count = Counter(r[0] for r in results)
print("\n절별 항목 수:", dict(sec_count))
sys.exit(0 if not bad else 1)
