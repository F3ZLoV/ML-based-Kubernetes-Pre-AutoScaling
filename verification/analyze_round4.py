#!/usr/bin/env python3
"""4차 재실험: 1차가 느렸던 원인 확인.

사용: python verification/analyze_round4.py [verification/gke_repro4]
입력: lead_time_{hpa,gru}_ramp_run{11..13,21..23}.csv, podlog/pods.log, podlog/nodes.log

A (run 11~13) = 1차 방식 그대로 (서버 한 번만 띄움, HPA×3 → GRU×3 연속)
B (run 21~23) = 비교용 (HPA → GRU 교대, GRU 직전 서버 재시작)

scale_out 이벤트마다 리드 타임을 둘로 나눈다.
  tracker : 측정 스크립트가 잰 값 (0.5 s 간격 폴링 → 폴링 지연 포함)
  k8s     : 파드 watch 기록으로 잰 실제 값 = 그 이벤트에서 생긴 파드 중 마지막 Ready 시각 - 시작 시각
  tracker - k8s = 측정 쪽에서 생긴 지연
"""
import csv
import os
import re
import statistics as st
import sys
from datetime import datetime, timedelta, timezone

D = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "gke_repro4")
KST = timezone(timedelta(hours=9))
NOISE = 0.24
BLOCKS = {"A": (11, 12, 13), "B": (21, 22, 23)}


def pods():
    """pod 이름 → {add, ready} (epoch s)"""
    p = {}
    with open(os.path.join(D, "podlog", "pods.log"), encoding="utf-8") as f:
        for line in f:
            v = line.split()
            if len(v) < 7 or v[1] not in ("ADDED", "MODIFIED"):
                continue
            t, name, ready = float(v[0]), v[2], v[6]
            d = p.setdefault(name, {})
            d.setdefault("add", t)
            if ready == "true" and "ready" not in d:
                d["ready"] = t
    return p


def events(model, n, P):
    rows = []
    with open(os.path.join(D, f"lead_time_{model}_ramp_run{n}.csv"), newline="") as f:
        for r in csv.DictReader(f):
            if r["event_type"] != "scale_out":
                continue
            end = datetime.fromisoformat(r["timestamp"]).replace(tzinfo=KST).timestamp()
            lead = float(r["lead_time_sec"])
            start = end - lead
            new = [d for d in P.values() if start - 1.0 <= d["add"] <= end and "ready" in d]
            k8s = max(d["ready"] for d in new) - start if new else None
            rows.append({"lead": lead, "k8s": k8s, "n": int(r["to_replicas"]) - int(r["from_replicas"]),
                         "pod": st.mean(d["ready"] - d["add"] for d in new) if new else None, "start": start})
    return rows


def node_cpu(t0, t1):
    vals = []
    with open(os.path.join(D, "podlog", "nodes.log"), encoding="utf-8") as f:
        for line in f:
            v = line.split()
            if len(v) >= 4 and t0 <= int(v[0]) <= t1:
                vals.append(int(v[3].rstrip("%")))
    return st.mean(vals) if vals else float("nan")


def summary(model, runs, P):
    ev = [e for n in runs for e in events(model, n, P)]
    k = [e["k8s"] for e in ev if e["k8s"] is not None]
    pod = [e["pod"] for e in ev if e["pod"] is not None]
    cpu = node_cpu(min(e["start"] for e in ev) - 30, max(e["start"] for e in ev) + 30)
    return {"lead": st.mean(e["lead"] for e in ev), "k8s": st.mean(k), "pod": st.mean(pod),
            "batch": st.mean(e["n"] for e in ev), "n": len(ev), "cpu": cpu,
            "runs": [round(st.mean(x["lead"] for x in events(model, n, P)), 2) for n in runs]}


if __name__ == "__main__":
    P = pods()
    print(f"파드 기록 {len(P)}개")
    for b, runs in BLOCKS.items():
        h, g = summary("hpa", runs, P), summary("gru", runs, P)
        print(f"\n[{b}] run {runs}")
        print(f"  {'':26s}{'HPA':>8s}{'GRU':>8s}{'GRU-HPA':>9s}")
        for key, label in [("lead", "리드 타임 (측정 스크립트)"), ("k8s", "리드 타임 (파드 기록)"),
                           ("pod", "파드 1개 생성→Ready"), ("batch", "한 번에 늘린 수"), ("cpu", "노드 CPU 평균 %")]:
            print(f"  {label:26s}{h[key]:8.2f}{g[key]:8.2f}{g[key] - h[key]:+9.2f}")
        print(f"  run별 리드 타임  HPA {h['runs']}  GRU {g['runs']}   이벤트 {h['n']} / {g['n']}")
        gap = g["lead"] - h["lead"]
        print(f"  → GRU-HPA {gap:+.2f}s : 오차 {NOISE}s {'초과 (GRU 느림)' if gap > NOISE else '이내 (같음)'}")
