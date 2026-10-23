#!/usr/bin/env python3
"""GKE 확장 실험: 통제된 3개 시나리오에서 4개 스케일러 비교 (각 6회, run 101~106).

사용: python verification/analyze_ext2.py
입력: gke_ext1 (HPA·GRU), gke_ext2 (LSTM·Ensemble)
  lead_time_{model}_{scenario}_run{n}.csv, week8/{model}_{scenario}_run{n}_stats(.csv|_history.csv)

run 단위 지표 (논문과 같은 정의)
  lead   : scale_out 이벤트 리드 타임 평균 (s)
  onset  : 부하 시작(사용자 수 > 0)부터 3 replica 이상으로 처음 늘린 이벤트의 시작까지 (s)
  agg    : scale_out 이벤트당 늘린 replica 수 평균
  p95/p99: Locust Aggregated 응답 시간 (ms)
  err    : 실패 요청 비율 (%)
모델 간 비교는 run 단위 값에 Welch t-검정(양측).
"""
import csv
import os
import statistics as st
from datetime import datetime, timedelta, timezone

from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = {"hpa": "gke_ext1", "gru": "gke_ext1", "lstm": "gke_ext2", "ensemble": "gke_ext2"}
MODELS = ("hpa", "lstm", "gru", "ensemble")
SCENARIOS = ("general_spike", "step", "ramp")
METRICS = ("lead", "onset", "agg", "p95", "p99", "err")
KST = timezone(timedelta(hours=9))


def run_metrics(model, sc, n):
    d = os.path.join(HERE, SRC[model])
    w = os.path.join(d, "week8", f"{model}_{sc}_run{n}")
    hist = [(int(r["Timestamp"]), int(r["User Count"]))
            for r in csv.DictReader(open(w + "_stats_history.csv")) if r["Name"] == "Aggregated"]
    t0 = next(t for t, u in hist if u > 0)
    ev = []
    for r in csv.DictReader(open(os.path.join(d, f"lead_time_{model}_{sc}_run{n}.csv"))):
        if r["event_type"] != "scale_out":
            continue
        end = datetime.fromisoformat(r["timestamp"]).replace(tzinfo=KST).timestamp()
        lead = float(r["lead_time_sec"])
        ev.append((end - lead, lead, int(r["to_replicas"]) - int(r["from_replicas"]), int(r["to_replicas"])))
    ev.sort()
    agg = next(r for r in csv.DictReader(open(w + "_stats.csv")) if r["Name"] == "Aggregated")
    return {
        "lead": st.mean(e[1] for e in ev),
        "onset": next(s - t0 for s, _, _, to in ev if to >= 3),
        "agg": st.mean(e[2] for e in ev),
        "p95": float(agg["95%"]),
        "p99": float(agg["99%"]),
        "err": 100 * int(agg["Failure Count"]) / int(agg["Request Count"]),
    }


def main():
    data = {(m, sc): [run_metrics(m, sc, n) for n in range(101, 107)] for m in MODELS for sc in SCENARIOS}
    for sc in SCENARIOS:
        print(f"\n=== {sc} (n=6 each) ===")
        print(f"{'metric':6s} " + " ".join(f"{m:>9s}" for m in MODELS) + "   p(vs HPA): lstm / gru / ens    p(vs GRU): lstm / ens")
        for k in METRICS:
            v = {m: [r[k] for r in data[(m, sc)]] for m in MODELS}
            pv = lambda a, b: stats.ttest_ind(v[a], v[b], equal_var=False).pvalue
            print(f"{k:6s} " + " ".join(f"{st.mean(v[m]):9.2f}" for m in MODELS)
                  + f"   {pv('lstm', 'hpa'):.3f} / {pv('gru', 'hpa'):.3f} / {pv('ensemble', 'hpa'):.3f}"
                  + f"    {pv('lstm', 'gru'):.3f} / {pv('ensemble', 'gru'):.3f}")


if __name__ == "__main__":
    main()
