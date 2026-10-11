#!/usr/bin/env python3
"""Fig 2 (지표별 1위 횟수)를 유의성 기준으로 다시 그린다.

빗금 = 1위가 2위와 통계적으로 구분되지 않음 (run 단위 Welch t-test, p ≥ 0.05).
사용: python verification/make_fig2.py <출력 png>
"""
import contextlib
import io
import os
import statistics as st
import sys

import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from scipy import stats

sys.path.insert(0, os.path.dirname(__file__))
with contextlib.redirect_stdout(io.StringIO()):  # significance_check 는 import 시 검정 결과를 출력한다
    from significance_check import M, SC, metric  # noqa: E402

COL = {"hpa": "#EF4B3F", "lstm": "#3B8ED8", "gru": "#34AE55", "ensemble": "#9353B7"}
LIGHT = {"hpa": "#F7A39C", "lstm": "#9DC6EB", "gru": "#99D6AA", "ensemble": "#C9A9DB"}
NAME = {"hpa": "HPA", "lstm": "LSTM", "gru": "GRU", "ensemble": "Ensemble"}
METRICS = [("lead", "Lead Time"), ("p95", "P95"), ("p99", "P99"), ("err", "Error Rate")]

solid = {k: dict.fromkeys(M, 0) for k, _ in METRICS}
hatch = {k: dict.fromkeys(M, 0) for k, _ in METRICS}
for key, _ in METRICS:
    for sc in SC:
        v = {m: metric(sc, m, key) for m in M}
        rank = sorted(M, key=lambda m: st.mean(v[m]))
        p = stats.ttest_ind(v[rank[0]], v[rank[1]], equal_var=False).pvalue
        (solid if p < 0.05 else hatch)[key][rank[0]] += 1
        print(f"{key:4s} {sc:17s} {rank[0]:9s} p = {p:.4f}")

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 15})
fig, ax = plt.subplots(figsize=(10, 6), dpi=282)
w = 0.2
for i, (key, _) in enumerate(METRICS):
    for j, m in enumerate(M):
        x = i + (j - 1.5) * w
        s, h = solid[key][m], hatch[key][m]
        if s:
            ax.bar(x, s, w, color=COL[m], edgecolor="black", linewidth=1)
        if h:
            ax.bar(x, h, w, bottom=s, color=LIGHT[m], edgecolor="#333333", linewidth=1, hatch="///")
        tot = s + h
        ax.text(x, tot + 0.15, str(tot), ha="center", va="bottom", fontsize=17,
                fontweight="bold" if tot else "normal", color="black" if tot else "#666666")
ax.set_xticks(range(len(METRICS)))
ax.set_xticklabels([t for _, t in METRICS], fontsize=20, fontweight="bold")
ax.set_ylabel("# scenarios won (out of 7)", fontsize=17)
ax.set_ylim(0, 5.6)
ax.set_yticks(range(6))
ax.yaxis.grid(True, color="#E0E0E0")
ax.set_axisbelow(True)
for side in ("top", "right"):
    ax.spines[side].set_visible(False)
handles = [Patch(facecolor=COL[m], edgecolor="black", label=NAME[m]) for m in M]
handles.append(Patch(facecolor="white", edgecolor="black", hatch="///", label="not distinguishable from runner-up (p ≥ 0.05)"))
ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 1.2), ncol=3, fontsize=13, frameon=True)
fig.tight_layout()
fig.savefig(sys.argv[1] if len(sys.argv) > 1 else "fig2_significance.png", bbox_inches="tight")
print("solid", solid, "\nhatch", hatch)
