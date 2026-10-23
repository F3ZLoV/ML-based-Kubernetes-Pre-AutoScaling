#!/bin/bash
# 확장 2단계: 통제된 3개 시나리오에서 LSTM·Ensemble 각 6회 (run 101~106).
# 라운드마다 시나리오를 돌아가며 LSTM → Ensemble 교대 실행, 매 실행 직전 해당 모델로 추론 서버 재시작.
export AI_SERVER_URL="${1:?ngrok URL}"
S=$(cd "$(dirname "$0")" && pwd)
W=$HOME/repro_gke2
export PATH=$W/bin:$HOME/google-cloud-sdk/bin:$PATH
cd "$W"
IP=$(kubectl get svc ticketbench-svc -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
export TICKETBENCH_HOST="http://${IP}" TARGET_HOST="http://${IP}"
echo "host=$TICKETBENCH_HOST ai=$AI_SERVER_URL"
setsid bash $S/podlog.sh "$W/logs/podlog_ext2" < /dev/null > /dev/null 2>&1 &
LOGPID=$!
source scripts/week8_helpers.sh
hard_reset
for i in 1 2 3 4 5 6; do
  r=$((100 + i))
  for sc in general_spike step ramp; do
    for m in lstm ensemble; do
      bash $S/ai_restart.sh "$m" "$W/logs/ai_${m}_${sc}_run${r}.log" || { echo "AI_FAIL — 중단"; exit 1; }
      run_one "$m" "$sc" "$r" < /dev/null
    done
  done
  echo "ROUND_DONE $i $(date +%H:%M)"
done
./scripts/switch_scaler.sh cleanup
kill -- -$LOGPID 2>/dev/null
echo "EXT2_DONE $(date)"
