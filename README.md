# ML-based Kubernetes Pre-AutoScaling

**Evaluating Predictive Autoscaling Models Across Kubernetes Traffic Archetypes**

Kubernetes 기본 오토스케일러 HPA의 사후 대응(reactive) 구조가 유발하는 cold start
지연을, ML 트래픽 예측 기반의 선제적(proactive) 스케일 아웃으로 해결·검증한 실증 연구.
DigitalOcean Kubernetes(DOKS) 환경에서 KEDA External Metrics API로 LSTM·GRU·Ensemble
예측값을 스케일링 트리거로 연동하고, HPA와 함께 4개 트래픽 archetype에서 총 84회를 실측 비교.

> 📄 본 저장소는 한국컴퓨터정보학회(KSCI/JKSCI) 투고 논문
> *"Evaluating Predictive Autoscaling Models Across Kubernetes Traffic Archetypes"* 의
> 구현 및 실험 코드입니다.

---

## Key Findings

- **No Universal Winner** — 단일 모델이 모든 트래픽 archetype에서 우월하지 않음
  (HPA 4승 / GRU 2승 / Ensemble 1승 / LSTM 0승, 7개 시나리오 기준)
- **GRU**가 RAMP 시나리오에서 HPA 대비 리드 타임 **15.1%**, P95 지연 **25.9%** 개선
- 실험 시작 시점의 **클러스터 초기 상태 통제** 여부에 따라 동일 archetype에서 결론이
  반전 — ML 오토스케일러 평가의 전제 조건임을 실증
- 단순 가중 평균 **Ensemble**은 분포 변화에 가장 취약(리드 타임 +81.7%)하고
  periodic 트래픽에서 replica churn(oscillation) 유발

## Architecture

Locust ──traffic──▶ TicketBench (FastAPI)
│
Prometheus (15s scrape)
│ metrics
▼
AI Server (FastAPI + LSTM/GRU/Ensemble)
│ predicted_replicas (ngrok HTTPS)
▼
KEDA (External Metrics API)
│ scale
▼
HPA ──▶ Deployment Replicas


- **리드 타임 측정 도구**: Kubernetes Watch API로 `scale-out 명령 발행 → pod
  condition.Ready 전환` 시각 차이를 이벤트별 계측, CSV 로깅

## Evaluation

| 항목 | 값 |
|---|---|
| Scalers | HPA, LSTM, GRU, Ensemble (LSTM+GRU 0.5:0.5) |
| Traffic archetypes | SPIKE, STATIONARY, RAMP, PERIODIC |
| Scenarios | 7 (AWS/Alibaba/Wikipedia 실측 + 합성) |
| Runs | 7 시나리오 × 4 스케일러 × 3회 = **84 runs** (912 스케일링 이벤트) |
| Metrics | Lead Time, P95/P99 Latency, Error Rate, Time-to-Peak, Aggressiveness |

## Tech Stack

`Kubernetes (DOKS)` · `KEDA` · `HPA` · `Prometheus + Grafana` · `Locust` ·
`FastAPI + Uvicorn` · `TensorFlow 2.16` · `Python 3.12` · `ngrok`

**Models**: 60-step look-back window · 3-feature(user_count / rps / response_time) ·
MinMaxScaler · Alibaba Cluster Trace 2018 재학습 (Google Colab T4)

## Repository Structure

[실제 디렉터리 트리 삽입]
├── ai_server/ # FastAPI 추론 서버 (LSTM/GRU/Ensemble)
├── lead_time_tracker/# Watch API 리드 타임 측정 도구
├── k8s/ # ScaledObject, Deployment 매니페스트
├── locust/ # custom LoadShape 시나리오
├── models/ # *.keras, alibaba_scaler.pkl
└── ...


## Getting Started

```bash
# 1. 클러스터 준비 (DOKS) 및 KEDA 설치
[...]

# 2. AI 추론 서버 실행
uvicorn ai_metrics_api:app --host 0.0.0.0 --port 5000

# 3. ngrok 터널 노출 후 ScaledObject 적용
[...]

# 4. 부하 테스트 실행
[...]
```

## Data Sources

- **AWS CloudWatch** (Kaggle) — SPIKE
- **Alibaba Cluster Trace 2018** — 학습 데이터 및 SPIKE/PERIODIC
- **Wikimedia Pageview API** (2024-11-01, CC0 1.0) — RAMP-like

## Author

**박태준 (Tae-Joon Park)** — Inha Technical College, Computer Science and Engineering
지도교수: 조규철 (Kyu-Cheol Jo)

## License

[MIT 등 라이선스 지정]