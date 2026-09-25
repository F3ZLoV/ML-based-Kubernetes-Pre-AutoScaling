# 논문 역검증 보고서

**대상 논문**: Evaluating Predictive Autoscaling Models Across Kubernetes Traffic Archetypes (JKSCI 투고본, 12쪽, 표 9개·그림 4개)
**검증 일시**: 2026-09-25 ~ 26
**검증 범위**: (1) 논문 수치 ↔ 원시 데이터 (2) 논문 서술 ↔ 코드·설정 (3) 다른 클라우드(GCP GKE)에서의 축소 재실험

---

## 요약

| 검증 | 결과 |
|---|---|
| 논문 수치 165개 항목을 84 run 원시 데이터로 재계산 | **165개 전부 일치** |
| 안전 장치·KEDA/HPA 설정·리드 타임 측정 도구·모델 구조·학습 설정 대조 | **서술과 코드가 전부 일치** |
| GKE 재실험 — Ensemble 진동 (IV.4.3) | **재현** (대형 점프 6·급락 5, 논문과 동일 수치) |
| GKE 재실험 — GRU 진동 없음 (IV.4.3) | **재현** (0·0) |
| GKE 재실험 — ramp에서 GRU의 P99 개선 | **재현** (21~26% 낮음, 논문 21.8%) |
| GKE 재실험 — ramp에서 GRU의 리드 타임 우위 (+15.1%) | **재현되지 않음** (GKE에서는 GRU가 0.55초 느림) — 원인 분석은 3.5절 |

논문에 **틀린 수치나 코드와 어긋나는 서술은 없었습니다.** 재실험에서 논문의 경향 중 Ensemble 진동과 GRU의 꼬리 지연 개선은 다른 클라우드에서도 재현되었고, ramp의 리드 타임 우위는 환경에 따라 달라지는 것으로 나타났습니다.

---

## 1. 데이터 기반 수치 검증

`results/paper_dataset/`의 84 run 원시 CSV(252개)에서 논문의 모든 수치를 다시 계산해 대조했습니다. 집계 규칙은 논문과 같습니다(Lead·Aggressiveness는 3 run의 이벤트를 합친 평균, P95·P99·Err는 run별 값의 평균).

| 대상 | 항목 수 | 결과 |
|---|---|---|
| Table 4 (7 시나리오 × 4 모델 리드 타임) | 28 | 일치 |
| Table 5 (P95·P99·Err) | 36 | 일치 |
| Table 6 (TTP·Aggressiveness) | 24 | 일치 |
| Table 7 (통제 전후 대조) | 6 | 일치 |
| Table 8 (학습 데이터 민감도) | 7 | 일치 |
| Table 9 근거 수치, Fig 2 (1위 횟수 16칸) | 17 | 일치 |
| 본문·초록 수치 (이벤트 수 912건, 15.1%, 25.9%, 7배·10배·39배·108배, 0.24초·0.44초, 안전 장치 38.7%·9.5%·51.9%, 58.8%·56.1%, 진동 횟수 등) | 47 | 일치 |
| **합계** | **165** | **165개 일치** |

실행: `python verification/verify_paper.py` → 결과 `verification/verify_paper_output.txt`

**참고 — 반올림된 표 값으로 계산된 파생 수치 4건.** 논문은 아래 수치를 표에 적힌 반올림 값으로 계산했습니다. 표를 보고 독자가 계산하면 논문 값이 나오므로 내부적으로 일관되며, 원시 데이터로 직접 계산해도 결론은 같습니다.

| 항목 | 논문 | 원시 데이터 직접 계산 |
|---|---|---|
| general spike GRU−HPA 리드 타임 차 | 0.12 s | 0.127 s |
| Table 8 LSTM Δ% / 정규화 | 13.7% / 5.4% | 13.6% / 5.4% |
| Table 8 GRU Δ% / 정규화 | 16.8% / 8.3% | 16.9% / 8.5% |
| Table 8 Ensemble Δ% / 정규화 | 81.7% / 68.6% | 81.4% / 68.3% |

---

## 2. 코드·설정 대조

| 논문 서술 | 확인한 파일 | 결과 |
|---|---|---|
| III.4 안전 장치: 저부하 우회(사용자·RPS 모두 50 미만 → 실측 지연 기반 1~3), 상한 고정(예측 2,500 ms 초과 또는 사용자 350 초과 → 25), 규칙 하한 max(1, ⌊user/20⌋), 최종 1~25 클램프 | `server/ai_metrics_api.py` | 일치 |
| III.1 추론 서버가 Locust `/stats/requests`에서 user_count·total_rps·median_response_time을 읽음 | `server/ai_metrics_api.py` | 일치 (부하 엔드포인트가 `GET /` 하나라 `stats[0]` 중앙값 = 전체 중앙값) |
| III.3·Table 1 KEDA: metrics-api, `predicted_replicas`, targetValue 1, 폴링 5 s, 쿨다운 10 s, 최소 1·최대 25, 5 s당 40 파드 또는 900% 중 큰 값 | `infra/keda-scaler.yaml` | 일치 |
| Table 1 HPA: CPU 50%, 최소 2·최대 25, 15 s당 900% | `infra/hpa-baseline.yaml` | 일치 |
| III.5 리드 타임: `.spec.replicas` 증가 감지 → `readyReplicas` 도달 시 기록, 진행 중 재상향은 한 이벤트로 흡수, 하향 시 `scale_out_partial` 별도 기록 | `scripts/lead_time_tracker_v2.py` | 일치 |
| III.2.2 모델: LSTM·GRU 64 units·ReLU·단일 레이어 + Dense(1), Ensemble = 두 모델 → Average | `server/models/*.keras` (로드해 레이어 확인) | 일치 |
| III.2.3 학습: Alibaba 2018 machine_usage 72시간 25,920행, `user_count←mem`, `rps←cpu`, `response_time = 100 + 0.5·cpu^1.5`, 1초 선형 보간, look-back 60, 80:20 분할, Adam·MSE, batch 512, epoch 20, EarlyStopping(3, 최적 가중치 복원), ReduceLROnPlateau(0.5, 2) | `Alibaba_Retrain_Colab_v3 (1).ipynb` | 일치 |

**참고 사항 (오류는 아님)**

1. **측정 주기.** 트래커 루프는 `0.5초 대기 + kubectl 호출 시간`이라 실제 주기는 0.5초보다 약간 깁니다. 논문의 "0.5초 간격 폴링" 서술은 대기 시간 기준입니다.
2. **학습 창과 추론 창의 시간 폭.** 학습 때 60-step 창은 60초(1초 간격)입니다. 추론 때는 추론 서버가 호출된 최근 60회인데, 재실험에서 호출 간격을 측정하니 평균 3.73초(중앙값 5.00초)로 **창의 시간 폭이 약 224초**였습니다. 논문은 두 사실을 각각 적었지만(III.2.1 "추론 서버 폴링 주기 기준 최근 60개 관측", III.2.3 "60초 구간") 차이를 명시하지는 않습니다. 세 ML 모델이 같은 조건을 공유하므로 모델 간 비교는 공정하며, 논문이 "순수 예측 성능이 아니라 동일 조건 아래의 운영 결과를 비교한다"고 범위를 한정한 근거와도 맞닿습니다.
3. **Table 5 Step/HPA 에러율 `0.00`.** 실제로는 721,777건 중 31건 실패(0.0043%)로, 반올림 결과 0.00입니다. `<0.01` 표기가 더 정확합니다.

---

## 3. GKE 축소 재실험

원 실험 환경(DigitalOcean)의 크레딧이 만료되어 GCP GKE에서 핵심 주장 두 가지를 재실험했습니다. 원 실험 스크립트(`scripts/week8_helpers.sh`, 초기 상태 통제 프로토콜 포함)를 그대로 사용했고, 원본 결과 파일을 덮어쓰지 않도록 별도 작업 폴더에서 실행했습니다.

- **ramp** (논문의 유일한 유의 우위 주장): HPA × 3, GRU × 3
- **periodic** (Ensemble 진동 주장, IV.4.3): GRU × 3, Ensemble × 3

### 3.1 환경 차이

| 항목 | 논문 (DOKS) | 재실험 (GKE) |
|---|---|---|
| 노드 | s-2vcpu-4gb × 3 | e2-standard-2 × 3 (노드당 할당 CPU 1,930m) |
| 리전 | 싱가포르 | 서울 (asia-northeast3-a) |
| Kubernetes | 1.31.x | 1.35.8 |
| KEDA | 2.16.x | 2.16.1 |
| TensorFlow / scikit-learn (추론 서버) | 2.16 / 1.6.1 | 2.21 / 1.7.2 (모델·스케일러 파일은 동일, 정상 로드 확인) |
| Locust | 2.43.x | 2.43.3 |
| 부하 스크립트, TicketBench 이미지(`f3zlov/ticketbench:v5`), 파드 자원, KEDA·HPA 설정 | — | 동일 |

클라우드·노드 구현이 다르므로 **절대 수치가 아니라 GKE 안에서의 모델 간 경향**을 논문과 비교했습니다.

### 3.2 진행 중 발생한 문제와 조치

| 문제 | 조치 | 결과 영향 |
|---|---|---|
| 처음 고른 `e2-medium`은 공유 코어라 노드당 할당 CPU가 940m. 시스템 파드(1,905m)를 빼면 TicketBench 파드가 7~9개만 떠서, 목표 22개 중 15개가 Pending | 첫 run 즉시 중단·폐기, 노드를 `e2-standard-2`로 교체. 25개 파드가 18초 만에 전부 Ready 되는 것을 확인한 뒤 재시작 | 없음 (폐기한 run은 집계에 넣지 않음) |
| 무료 체험 계정의 리전 외부 IP 한도(4개)로 새 노드 생성 실패 | 기존 노드 풀을 0대로 줄인 뒤 새 풀 생성 | 없음 |
| **21:49~22:01(KST) 클러스터 전체가 일시적으로 느려짐** — 이 시간대에 걸린 HPA run3과 GRU run1은 **모든** scale-out이 12~15초 (정상 run은 약 2.3초). GKE 작업 이력·경고 이벤트에는 해당 시간대 기록이 없어 원인은 특정하지 못함 | 두 run을 원 기록은 보존한 채 **run 4로 재측정**. 두 집계를 모두 보고 | 3.3절 표에 둘 다 표기 |

원 실험(DOKS) 데이터에는 이런 용량 부족 흔적이 없음을 확인했습니다 — 84 run 중 80 run이 25개 파드 전부 Ready에 도달했고, 나머지 4 run(18·23·23·24)은 논문 IV.4.1의 서술대로 부하가 먼저 내려간 경우이며, scale-out 545건이 모두 Ready 도달로 완료되었습니다.

### 3.3 ramp 결과

| | 논문 HPA | 논문 GRU | GKE HPA | GKE GRU |
|---|---|---|---|---|
| **지연 구간 run을 run 4로 대체** (HPA 1·2·4 / GRU 2·3·4) | | | | |
| 리드 타임 (s) | 2.92 | 2.48 | 2.26 | 2.80 |
| P95 (ms) | 580 | 430 | 293 | 337 |
| P99 (ms) | 733 | 573 | 583 | 460 |
| 에러율 (%) | 0.01 | 0.01 | 0.006 | 0.027 |
| Aggressiveness (이벤트당 추가 파드) | 3.14 | 3.24 | 3.18 | **5.59** |
| **원래 run 1~3** (지연 구간 포함) | | | | |
| 리드 타임 (s) | | | 5.92 | 6.40 |
| P95 / P99 (ms) | | | 420 / 727 | 390 / 537 |

run별 리드 타임 — HPA: 2.27 / 2.27 / (13.73) / 2.22, GRU: (13.59) / 2.97 / 2.63 / 2.81 (괄호는 지연 구간 run)

| GRU vs HPA | 논문 | GKE (대체 집계) | GKE (원래 run 1~3) |
|---|---|---|---|
| 리드 타임 | **0.44 s 빠름 (+15.1%)** | **0.55 s 느림 (−24.3%)** | 0.48 s 느림 (−8.1%) |
| P95 | 25.9% 낮음 | 14.8% 높음 | 7.1% 낮음 |
| P99 | 21.8% 낮음 | **21.1% 낮음** | **26.1% 낮음** |

### 3.4 periodic 결과 (IV.4.3 진동 검증)

| 3 run 합계 | 대형 점프 (Δ≥20) | 급락 (≥15 → ≤3) | 리드 타임 | P95 | P99 | 에러율 |
|---|---|---|---|---|---|---|
| 논문 Ensemble | 6 | 5 | | | | |
| **GKE Ensemble** | **6** | **5** | 3.66 s | 827 ms | 1,167 ms | 0.33% |
| 논문 GRU | 0 | 0 | | | | |
| **GKE GRU** | **0** | **0** | 3.48 s | 430 ms | 810 ms | 0.08% |

run별 Ensemble — 점프/급락: 1/1, 3/2, 2/2

논문의 periodic 데이터는 초기 상태 통제 **이전**(Ctrl = N)에 수집되었는데, 통제 프로토콜을 적용한 다른 클라우드에서 **같은 수치**가 나왔습니다. 확장 직후 급락(replica churn)이 Ensemble 고유의 행동이라는 논문의 해석과 V.2절 권고(변화율 제한·히스테리시스)를 뒷받침합니다.

### 3.5 해석 — ramp 리드 타임 우위가 재현되지 않은 이유

GKE에서 GRU는 한 번의 scale-out에 평균 **5.59개**, HPA는 **3.18개**의 파드를 추가했습니다(논문 환경에서는 3.24 vs 3.14로 거의 같음). 리드 타임은 "요청된 파드가 **모두** Ready가 될 때까지"를 재는 이벤트 단위 지표라서, 한 번에 많이 늘릴수록 길어집니다. 이 관계는 두 환경 모두에서 확인됩니다.

| | 이벤트 수 | 배치 크기 ↔ 리드 타임 상관 | 파드 1개 추가당 |
|---|---|---|---|
| 논문 원본 (DOKS) | 545 | r = 0.56 | +0.29 s |
| GKE 재실험 (ramp) | 39 | r = 0.64 | +0.14 s |

GKE에서 배치 크기 차이만으로 (5.59 − 3.18) × 0.14 ≈ **0.34초**가 설명되며, 이는 관측된 격차 0.55초의 대부분입니다. 즉 GKE에서 GRU는 "느리게" 늘린 것이 아니라 **더 큰 단위로 늘렸기 때문에 이벤트당 시간이 길게 측정**된 것입니다. 논문 Fig 3(Aggressiveness–Lead Time 산점도)이 이 관계를 이미 보여주고 있습니다.

이 결과가 뜻하는 바:

- **논문의 ramp 수치 자체는 정확합니다**(1장). 다만 "GRU가 ramp에서 리드 타임을 15.1% 단축"은 **두 스케일러의 배치 크기가 비슷했던 DOKS 환경에서의 결과**이며, 다른 환경으로 일반화되지 않았습니다.
- 사용자 체감 지표 중 **P99 개선은 두 환경에서 일관되게 재현**(21~26%)되었습니다. P95는 집계 방식에 따라 방향이 달라 판단을 보류합니다.
- 논문이 스스로 "0.24초 변동 이내의 차이는 유의한 우열로 해석하지 않는다"고 범위를 좁히고, 비교 대상을 "동일 안전 장치 아래의 운영 결과"로 한정한 것은 이런 환경 의존성에 대한 적절한 방어입니다.

---

## 4. 재현 방법

```bash
# 1) 수치 검증 (클러스터 불필요)
python verification/verify_paper.py

# 2) GKE 재실험 (WSL, gcloud 로그인 후)
export PROJECT_ID=<gcp-project-id>
./scripts/gke_start.sh                       # e2-standard-2 × 3, KEDA 2.16.1, TicketBench 배포
bash verification/run_scripts/setup_repro.sh # 원본을 덮어쓰지 않는 작업 폴더 ~/repro_gke
#   추론 서버:  cd server && MODEL_TYPE=gru ../venv/bin/python -m uvicorn ai_metrics_api:app --port 5005
#   터널:      ngrok http 5005
bash verification/run_scripts/run_repro.sh    <ngrok-url>            # ramp HPA×3, GRU×3
bash verification/run_scripts/run_periodic.sh gru      <ngrok-url>  # periodic GRU×3
bash verification/run_scripts/run_periodic.sh ensemble <ngrok-url>  # (서버를 MODEL_TYPE=ensemble 로 재시작 후)
./scripts/gke_stop.sh                        # 반드시 삭제

# 3) 재실험 분석
python verification/analyze_repro.py
```

## 5. 파일

| 경로 | 내용 |
|---|---|
| `verification/verify_paper.py`, `verify_paper_output.txt` | 165개 항목 수치 검증 스크립트와 결과 |
| `verification/analyze_repro.py`, `analyze_repro_output.txt` | GKE 재실험 분석 스크립트와 결과 |
| `verification/gke_repro/` | GKE 재실험 원시 데이터 (lead_time CSV, Locust stats CSV) — 지연 구간 run 포함 전부 보존 |
| `verification/run_scripts/` | 재실험 실행 스크립트, 진행 대시보드 |
| `scripts/gke_start.sh`, `scripts/gke_stop.sh` | GKE 클러스터 생성·삭제 |
