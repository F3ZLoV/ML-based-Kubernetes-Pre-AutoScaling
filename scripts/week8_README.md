# 8주차 실험 실행 패키지

## 개요

3개 신규 시나리오 × 4 모델 × 3 run = **36 run** 일괄 수행.

| Archetype | 파일 | 러닝 타임 | AAPA 매핑 |
|---|---|---|---|
| General Spike | `loadtest/locustfile_general_spike.py` | 320s | SPIKE |
| Step (계단형) | `loadtest/locustfile_step.py` | 480s | STATIONARY (level-shift) |
| Ramp (램프업) | `loadtest/locustfile_ramp.py` | 480s | RAMP |

예상 총 소요시간: 약 5.4h (run당 평균 ≈ 9분: 러닝 + 2분 쿨다운)

---

## 실험 전 체크리스트

### 1. 인프라 준비 (실험 시작 15분 전)
- [ ] DOKS 노드 풀을 **3개**로 조정 (doctl 대시보드, CLI는 불안정했음)
- [ ] `kubectl get nodes` 로 Ready 확인
- [ ] `ticketbench-deploy` 배포 및 `kubectl rollout status` 정상
- [ ] Prometheus/Grafana Pod Running 확인 (리소스 기아 방지)

### 2. AI 추론 서버
- [ ] 로컬 WSL에서 `uvicorn ai_metrics_api:app --host 0.0.0.0 --port 5005` 실행
- [ ] ngrok 터널 활성화 (`ngrok http 5005`) 후 현재 URL을 환경변수로 export:
      `export AI_SERVER_URL=https://<subdomain>.ngrok-free.dev`
      (`switch_scaler.sh ml` 이 이 값을 `infra/keda-scaler.yaml` 템플릿에 주입한다. yaml 직접 수정 불필요)
- [ ] 모델 전환 시 ai_metrics_api에서 로드되는 scaler/model 파일이 **Alibaba 기반**인지 확인
  - `alibaba_scaler.pkl` (⚠ aws_kaggle_scaler.pkl 아님)
  - look-back window 60 (⚠ 5 아님)
  - `fetch_live_traffic()`의 연결 실패 시 "마지막 값 유지" 로직 적용돼 있는지

### 3. 환경 변수
```bash
export TICKETBENCH_HOST=http://<cluster-lb-ip>   # locust --host 에 전달
export TARGET_HOST="$TICKETBENCH_HOST"           # locustfile 기본 host
export AI_SERVER_URL=https://<subdomain>.ngrok-free.dev
# 예: export TICKETBENCH_HOST=http://146.190.195.236
```

### 4. 권한
```bash
chmod +x scripts/switch_scaler.sh
```

---

## 실행

### 옵션 A: 전체 36 run 자동 실행 (권장)

```bash
source scripts/week8_helpers.sh
run_all          # general_spike -> step -> ramp, 36 run
```

- 시나리오 단위로 돌리려면 `run_scenario general_spike` / `run_scenario step` / `run_scenario ramp`,
  개별 run은 `run_one <model> <scenario> <run>`
- 각 non-hpa 모델 run 시작 직전 **"ai_metrics_api에서 해당 모델 로드됐는지 확인 후 Enter"** 프롬프트가 뜸 → 별도 터미널에서 모델 파일 교체 후 Enter
- 중단 시 `Ctrl+C` 두 번 (locust + tracker 각각)

### 옵션 B: 특정 시나리오만 수행

환경변수로 덮어쓰기:
```bash
# 시나리오 단위:  source scripts/week8_helpers.sh && run_scenario general_spike
# 또는 1회성으로 개별 실행:
./scripts/switch_scaler.sh hpa
python3 scripts/lead_time_tracker_v2.py hpa general_spike 1 &
locust -f loadtest/locustfile_general_spike.py \
  --host=$TICKETBENCH_HOST --headless -u 600 -r 10 \
  --run-time 330s --csv=results/week8/hpa_general_spike_run1 --only-summary
```

---

## 실행 중 모니터링

- Grafana 대시보드 RPS/Replicas 패널
- `watch -n 2 'kubectl get po -n default'` (Pod lifecycle)
- `tail -f logs/week8/leadtime_*.log` (실시간 스케일 이벤트)

### 이상 징후 대응
- Pod가 Pending 오래 지속 → 노드 부족. doctl에서 노드 1개 추가 후 해당 run 재실행
- `Scale-Out` 이벤트 로그만 나오고 `Ready` 안 뜸 → image pull 지연. Docker Hub rate limit 확인
- KEDA ScaledObject가 READY=False → `switch_scaler.sh cleanup` 후 `ml` 재실행

---

## 실험 후 집계

모든 run 완료 후:

```bash
python3 scripts/aggregate_master.py
```

생성물:
- `results/master_full.csv` — run-level raw (논문용)
- `results/master_full.xlsx` — 5시트 (lead_raw, locust_raw, run_level, agg, ppt_table)
- `results/ppt_summary.csv` — PPT 요약표 포맷

PPT 요약표 구조:
```
dataset | scenario | model | Lead_mean_s | Lead_std_s | P95_ms | P99_ms | Err_rate_pct |
                                          LT_Delta_pct | P95_Delta_pct | P99_Delta_pct
```
- `dataset ∈ {AWS, Alibaba}`
- `scenario ∈ {spike, periodic, wiki, general_spike, step, ramp}`
- `model ∈ {hpa, lstm, gru, ensemble}`
- `*_Delta_pct`: HPA 대비 상대 개선율 (양수 = ML이 더 좋음)

---

## 참고: 논문 작성 준비

9주차(논문 작성 착수) 예비 작업:
- `results/master_full.csv`에서 dataset/scenario/model별 통계 추출
- 주요 Figure 후보:
  1. 6-scenario × 4-model Lead Time 히트맵
  2. LT vs Err 의 Pareto plot (trade-off 시각화)
  3. Time-to-peak vs Per-event Lead-time 비교 (별도 지표)
- Related works 표 요소: Dang-Quang&Yoo 2021, Mondal 2023, Zhang et al. AAPA 2025

---

## 논문용 데이터셋

집계가 끝난 뒤, 논문에 보고한 84 run만 평면 배치한 디렉터리를 만들어 둔다.

- `results/paper_dataset/` — 7 시나리오 x 4 모델 x 3 run, run당 lead_time / stats /
  stats_history 3개 파일. `manifest.csv` 에 원본 경로가 기록되어 있고,
  `README.md` 에 Table 4~12 매핑 표와 재현 스니펫이 있다.
- `results/backup_2node/` 는 2노드 예비 배치로 **논문에 미포함**이며 git-ignore 대상이다.
