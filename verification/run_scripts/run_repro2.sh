#!/bin/bash
# GKE 재실험 2차: ramp, HPA·GRU 교대 3회. GRU run 직전마다 추론 서버를 새로 띄워 이전 run 기억을 지운다.
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
for run in 1 2 3; do
  run_one hpa ramp "$run" < /dev/null
  bash $S/ai_restart.sh gru "$W/logs/ai_gru_run${run}.log" || { echo "AI 서버 재시작 실패 — 중단"; exit 1; }
  run_one gru ramp "$run" < /dev/null
done
./scripts/switch_scaler.sh cleanup
echo "REPRO2_DONE $(date)"
