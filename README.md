# ML-based Kubernetes Pre-AutoScaling

**Evaluating Predictive Autoscaling Models Across Kubernetes Traffic Archetypes**

Kubernetes 기본 오토스케일러 HPA의 사후 대응(reactive) 구조가 유발하는 cold start
지연을, ML 트래픽 예측 기반의 선제적(proactive) 스케일 아웃으로 완화할 수 있는지
DigitalOcean Kubernetes(DOKS)에서 실측 검증한 연구입니다. KEDA External Metrics API로
LSTM·GRU·Ensemble의 출력을 스케일링 트리거에 연동하고, HPA와 함께 4개 트래픽
archetype에 걸쳐 총 84회를 비교했습니다.

> 📄 한국컴퓨터정보학회(KSCI/JKSCI) 투고 논문
> *"Evaluating Predictive Autoscaling Models Across Kubernetes Traffic Archetypes"* 의
> 구현·실험 코드와 원시 계측 데이터입니다.

---

## Key Findings

- **No Universal Winner** — 단일 모델이 모든 트래픽 archetype에서 우월하지 않음
  (리드 타임 기준 HPA 4승 / GRU 2승 / Ensemble 1승 / LSTM 0승, 7개 시나리오)
- **GRU**가 RAMP 시나리오에서 HPA 대비 리드 타임 **15.1%**, P95 지연 **25.9%** 개선.
  SPIKE에서는 리드 타임이 대등(0.12초 차, 측정 변동 범위 내)하나 P95를 절반으로 낮춤
- 실험 시작 시점의 **클러스터 초기 상태 통제** 여부에 따라 모델 간 상대 순위가 뒤집힘 —
  ML 오토스케일러 평가에서 초기 상태 통제가 전제 조건임을 보임
- 단순 평균 결합 **Ensemble**은 학습 분포 변화에 가장 취약(리드 타임 +81.7%, HPA
  정규화 +68.6%)하고, periodic 트래픽에서 확장 직후 급락(replica churn)을 유발

## Architecture

```
Locust ──traffic──▶ TicketBench (FastAPI)
  │                      │
  │ stats API            └──▶ Prometheus ──▶ Grafana   (모니터링 전용)
  ▼
AI Server (FastAPI + LSTM/GRU/Ensemble)
  │  predicted_replicas (ngrok HTTPS)
  ▼
KEDA (External Metrics API, polling 5s)
  │  scale
  ▼
HPA ──▶ Deployment Replicas
```

추론 서버는 Locust의 통계 API(`/stats/requests`)에서 `user_count` / `total_rps` /
`median_response_time`을 직접 읽습니다. **Prometheus와 Grafana는 실험 모니터링 전용이며
추론 경로에는 포함되지 않습니다.**

모델은 다음 시점의 **응답 시간(ms)** 을 회귀 예측하고, 규칙 기반 변환기가 이를 권장 파드
수(1~25)로 환산합니다. 변환기에는 저부하 우회(`user_count<50 and rps<50`), 고부하 상한
고정(`user_count>350` 또는 예측 지연 >2500ms → 25), 규칙 하한(`⌊user_count/20⌋`)이
포함되어 있으며, 세부 동작은 `server/ai_metrics_api.py`를 참조하세요.

**리드 타임 측정 도구** — `scripts/lead_time_tracker_v2.py`가 Deployment의
`.spec.replicas`와 `.status.readyReplicas`를 0.5초 간격으로 폴링하여, 목표 replica 증가가
관측된 시점부터 요청된 replica가 모두 Ready에 도달할 때까지의 시간을 이벤트별로 CSV에
기록합니다.

## Evaluation

| 항목 | 값 |
|---|---|
| Scalers | HPA, LSTM, GRU, Ensemble (LSTM+GRU 균등 결합 후 추가 학습) |
| Traffic archetypes | SPIKE, STATIONARY, RAMP, PERIODIC |
| Conditions | 7 (= 6개 load shape; AWS/Alibaba spike는 동일 부하, 학습 데이터만 상이) |
| Runs | 7 × 4 스케일러 × 3회 = **84 runs** (스케일링 이벤트 912건) |
| Metrics | Lead Time, P95/P99 Latency, Error Rate, Time-to-Peak, Aggressiveness |

## Tech Stack

`Kubernetes (DOKS)` · `KEDA 2.16` · `HPA` · `Prometheus + Grafana` · `Locust 2.43` ·
`FastAPI + Uvicorn` · `TensorFlow 2.16` · `Python 3.12` · `ngrok`

**Models**: 60-step look-back (1초 간격) · 3-feature(user_count / rps / response_time) ·
MinMaxScaler · 64 hidden units · Adam / MSE · batch 512 · 최대 20 epoch ·
EarlyStopping + ReduceLROnPlateau · Alibaba Cluster Trace 2018 재학습 (Google Colab T4)

학습 feature는 Alibaba trace의 자원 사용률에서 유도한 대리 지표입니다
(`user_count ← mem_util`, `rps ← cpu_util`, `response_time = 100 + 0.5·cpu^1.5`).
원 데이터의 10초 간격은 1초로 선형 보간했습니다. 자세한 내용은
`Alibaba_Retrain_Colab_v3 (1).ipynb` 참조.

## Repository Structure

```
server/
  ai_metrics_api.py            FastAPI 추론 서버 (MODEL_TYPE 으로 모델 전환)
  models/                      *.keras, alibaba_scaler.pkl, aws_kaggle_scaler.pkl
infra/
  ticketbench.yaml             워크로드 Deployment + Service
  hpa-baseline.yaml            HPA baseline (min 2, CPU 50%, 900%/15s)
  keda-scaler.yaml             KEDA ScaledObject 템플릿 (min 1, polling 5s, 40 pods/5s)
loadtest/
  locustfile_*.py              시나리오별 custom LoadShape
  fetch_wikipedia_traffic.py   Wikimedia Pageview API → LoadShape 변환
scripts/
  lead_time_tracker_v2.py      리드 타임 계측기 (0.5초 폴링)
  switch_scaler.sh             HPA ↔ KEDA 전환 + 초기 상태 리셋
  week8_helpers.sh             36 run 배치 실행 (run_one / run_scenario / run_all)
  aggregate_master.py          전체 run 집계 → master_full.csv / xlsx
  week8_README.md              실험 실행 절차
results/
  paper_dataset/               ★ 논문에 보고한 84 run (평면 배치 + manifest + README)
  week8/, run-zip-files/       작업용 원시 출력
model/                         초기(AWS/Kaggle) 학습 스크립트
Alibaba_Retrain_Colab_v3 (1).ipynb   Alibaba 재학습 노트북
```

## Data

논문의 모든 표·그림은 **[`results/paper_dataset/`](results/paper_dataset/)** 의 84개 run에서
산출됩니다. 해당 디렉터리의 [README](results/paper_dataset/README.md)에 Table 4~12 매핑
표와 Table 4 재현 스니펫이 있습니다.

Table 4의 각 셀은 **pooled mean**(3개 run의 모든 scale-out 이벤트를 합쳐 한 번에 평균)
입니다. run별 평균을 다시 평균하면 다른 값이 나옵니다.

> ⚠️ 논문 IV.6절(학습 데이터 민감도)에 사용한 **AWS 학습 모델 가중치는 보존되지 않아**
> 해당 절 실험은 이 저장소로 재현할 수 없습니다. 재학습에 필요한 전처리 스크립트와
> 스케일러(`server/models/aws_kaggle_scaler.pkl`)만 포함되어 있습니다.

## Getting Started

```bash
# 0. 환경 변수
export TICKETBENCH_HOST=http://<cluster-lb-ip>   # locust --host
export TARGET_HOST="$TICKETBENCH_HOST"           # locustfile 기본 host
export AI_SERVER_URL=https://<subdomain>.ngrok-free.dev

# 1. 클러스터 준비 (DOKS 3-node) 및 KEDA 설치
kubectl apply -f infra/ticketbench.yaml
helm repo add kedacore https://kedacore.github.io/charts && \
  helm install keda kedacore/keda -n keda --create-namespace

# 2. AI 추론 서버 실행 (MODEL_TYPE ∈ lstm | gru | ensemble)
cd server && MODEL_TYPE=gru uvicorn ai_metrics_api:app --host 0.0.0.0 --port 5005

# 3. ngrok 터널 노출 후 스케일러 적용
ngrok http 5005
./scripts/switch_scaler.sh ml     # AI_SERVER_URL 을 템플릿에 주입해 적용
./scripts/switch_scaler.sh hpa    # baseline 으로 전환
./scripts/switch_scaler.sh cleanup

# 4. 부하 테스트 (36 run 배치)
source scripts/week8_helpers.sh
run_all

# 5. 집계
python3 scripts/aggregate_master.py
```

실험 절차와 체크리스트는 [`scripts/week8_README.md`](scripts/week8_README.md)에 있습니다.

## Limitations

- HPA baseline과 KEDA ScaledObject의 확장 정책·최소 replica 수가 동일하지 않아,
  Aggressiveness 비교에는 모델 특성과 스케일러 설정 차이가 함께 반영되어 있습니다.
- 안전 장치가 전체 관측의 약 48%에서 모델 출력을 우회하거나 상한으로 고정하므로,
  모델 간 비교는 순수 예측 성능이 아니라 동일 안전 장치 아래의 운영 결과 비교입니다.
- 조건당 반복이 3회이고 유의성 검정을 수행하지 않았습니다. 계측 해상도(0.5초) 및 관측된
  run 간 변동(0.24초)보다 작은 차이는 유의한 우열로 해석하지 않았습니다.
- 초기 상태 통제 프로토콜은 7개 시나리오 중 3개(36 run)에만 적용되었습니다.

## Data Sources

- **AWS CloudWatch** (Kaggle) — 초기 학습 데이터
- **Alibaba Cluster Trace 2018** — 재학습 데이터 ([alibaba/clusterdata](https://github.com/alibaba/clusterdata),
  `datacentertracesdatasets` 패키지 경유)
- **Wikimedia Pageview API** (en.wikipedia, 2024-11-01, CC0 1.0) — wiki 시나리오

## Author

**박태준 (Tae-Joon Park)** — Inha Technical College, Computer Science and Engineering
지도교수: 조규철 (Kyu-Cheol Jo)

## License

MIT
