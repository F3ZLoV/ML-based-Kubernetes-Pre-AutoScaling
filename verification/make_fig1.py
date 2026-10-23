#!/usr/bin/env python3
"""Fig 1 (전체 구조)을 본문(III.1, III.5)과 실제 구성에 맞게 다시 그린다.

- Locust · AI 추론 서버 · 리드 타임 측정 도구는 실험용 PC에서 실행 (추론 서버는 localhost:8089의 Locust 통계 API를 읽음)
- Prometheus는 모니터링 전용 (추론 경로에 없음)
- 측정 도구는 0.5초 간격 폴링
논문 한 단(약 8 cm)으로 줄여도 읽히도록 3열 격자에 글자를 크게 하고 박스 안 설명은 최소로 둔다.
사용: python verification/make_fig1.py <출력 png>
"""
import sys

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

plt.rcParams.update({"font.family": "DejaVu Sans"})
fig, ax = plt.subplots(figsize=(8.8, 7.6), dpi=300)
ax.set_xlim(0, 8.8)
ax.set_ylim(0, 7.6)
ax.axis("off")


def region(x, y, w, h, label, color, label_y):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                facecolor=color + "10", edgecolor=color, lw=2.5, ls=(0, (6, 4))))
    ax.text(x + 0.2, label_y, label, fontsize=20, fontweight="bold", color=color, va="center")


def box(cx, cy, title, sub, color, w=2.3, h=1.25):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.1",
                                facecolor=color + "22", edgecolor=color, lw=3))
    ax.text(cx, cy + (0.24 if sub else 0), title, ha="center", va="center", fontsize=21, fontweight="bold",
            linespacing=1.0)
    if sub:
        ax.text(cx, cy - 0.3, sub, ha="center", va="center", fontsize=15, color="#333333", linespacing=1.0)


def arrow(p, q, color, style="-"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=26, lw=3.2, color=color, ls=style,
                                 shrinkA=2, shrinkB=2))


def label(x, y, s, color, ha="center", fs=17):
    ax.text(x, y, s, ha=ha, va="center", fontsize=fs, color=color, fontweight="bold", linespacing=1.05)


# 3열 격자: 위 두 줄은 클러스터, 아래 한 줄은 실험용 PC. ngrok은 두 영역 사이 경계에 둔다.
X1, X2, X3 = 1.3, 4.4, 7.5
Y1, Y2, YH, YN = 6.0, 4.25, 1.45, 2.85
W, H = 2.3, 1.25
hw, hh = W / 2, H / 2

region(0.1, 3.35, 8.6, 4.15, "Kubernetes Cluster (DOKS)", "#B8860B", 7.15)
region(0.1, 0.1, 8.6, 2.3, "Experiment PC", "#7C3AED", 0.42)

box(X1, Y1, "Prometheus", "monitoring only", "#E74C3C")
box(X2, Y1, "TicketBench", "workload", "#2E86C1")
box(X3, Y1, "HPA", "", "#16A085")
box(X3, Y2, "KEDA", "", "#27AE60")

box(X1, YH, "Lead Time\nTracker", "", "#B8860B")
box(X2, YH, "Locust", "load generator", "#F08A24")
box(X3, YH, "AI Server", "LSTM / GRU /\nEnsemble", "#8E44AD", h=1.35)
box(X3, YN, "ngrok", "", "#7F8C8D", w=1.7, h=0.75)

# 클러스터 내부
arrow((X2 - hw, Y1), (X1 + hw, Y1), "#E74C3C", style=(0, (3, 2)))
arrow((X3 - hw, Y1), (X2 + hw, Y1), "#16A085")
label((X2 + X3) / 2, Y1 + 0.3, "scale", "#16A085", fs=16)
arrow((X3, Y2 + hh), (X3, Y1 - hh), "#27AE60")
label(X3 - 0.12, (Y1 + Y2) / 2, "replicas", "#27AE60", ha="right")
# 실험용 PC 내부 / 경계
arrow((X2 + hw, YH), (X3 - hw, YH), "#F08A24")
label((X2 + X3) / 2, YH + 0.3, "stats", "#F08A24", fs=16)
arrow((X3, YH + 0.675), (X3, YN - 0.375), "#8E44AD")
arrow((X3, YN + 0.375), (X3, Y2 - hh), "#27AE60")
label(X3 - 0.95, YN, "prediction\nevery 5 s", "#27AE60", ha="right")
# PC -> 클러스터
arrow((X2, YH + hh), (X2, Y1 - hh), "#F08A24")
label(X2 + 0.12, Y2, "HTTP\ntraffic", "#F08A24", ha="left")
arrow((X1 + 0.6, YH + hh), (X2 - hw + 0.3, Y1 - hh), "#B8860B", style=(0, (4, 3)))
label(X1 + 0.7, Y2, "polling\nevery 0.5 s", "#B8860B", ha="right")

fig.tight_layout()
fig.savefig(sys.argv[1] if len(sys.argv) > 1 else "fig1.png", bbox_inches="tight", facecolor="white")
print("saved")
