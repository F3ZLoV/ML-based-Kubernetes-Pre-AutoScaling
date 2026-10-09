#!/bin/bash
# GKE 재실험 3차: 교대 실행은 그대로 두고, 서버 초기화 효과만 따로 보기 위해
# 라운드마다 HPA → GRU(재시작, run 4~6) → GRU(재시작 없음, run 7~9).
# 재시작 없는 GRU 는 바로 앞 GRU run 의 기억을 이어받으므로 1차 실험 조건과 같다.
export AI_SERVER_URL="${1:?ngrok URL}"
S=$(cd "$(dirname "$0")" && pwd)
W=$HOME/repro_gke2
export PATH=$W/bin:$HOME/google-cloud-sdk/bin:$PATH
cd "$W"
IP=$(kubectl get svc ticketbench-svc -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
export TICKETBENCH_HOST="http://${IP}" TARGET_HOST="http://${IP}"
echo "host=$TICKETBENCH_HOST ai=$AI_SERVER_URL"
source scripts/week8_helpers.sh
hard_reset
for i in 1 2 3; do
  r=$((i + 3)); nr=$((i + 6))
  run_one hpa ramp "$r" < /dev/null
  bash $S/ai_restart.sh gru "$W/logs/ai_gru_run${r}.log" || { echo "AI 서버 재시작 실패 — 중단"; exit 1; }
  run_one gru ramp "$r" < /dev/null
  echo "NO_RESTART gru run${nr}"
  run_one gru ramp "$nr" < /dev/null
done
./scripts/switch_scaler.sh cleanup
echo "REPRO3_DONE $(date)"
