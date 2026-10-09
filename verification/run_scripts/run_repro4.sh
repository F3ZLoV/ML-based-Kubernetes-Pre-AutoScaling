#!/bin/bash
# 4차: 1차가 느렸던 원인 확인.
#  A (run 11~13): 1차 방식 그대로 — 서버 한 번만 띄움, HPA×3 → GRU×3 연속
#  B (run 21~23): 비교용 — HPA → GRU 교대, GRU 직전마다 서버 재시작
export AI_SERVER_URL="${1:?ngrok URL}"
S=$(cd "$(dirname "$0")" && pwd)
W=$HOME/repro_gke2
export PATH=$W/bin:$HOME/google-cloud-sdk/bin:$PATH
cd "$W"
IP=$(kubectl get svc ticketbench-svc -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
export TICKETBENCH_HOST="http://${IP}" TARGET_HOST="http://${IP}"
echo "host=$TICKETBENCH_HOST ai=$AI_SERVER_URL"
setsid bash $S/podlog.sh "$W/logs/podlog4" < /dev/null > /dev/null 2>&1 &
LOGPID=$!
source scripts/week8_helpers.sh
hard_reset
echo "BLOCK_A $(date +%s)"
bash $S/ai_restart.sh gru "$W/logs/ai_blockA.log" || { echo "AI 서버 시작 실패 — 중단"; exit 1; }
for r in 11 12 13; do run_one hpa ramp "$r" < /dev/null; done
for r in 11 12 13; do run_one gru ramp "$r" < /dev/null; done
echo "BLOCK_B $(date +%s)"
for r in 21 22 23; do
  run_one hpa ramp "$r" < /dev/null
  bash $S/ai_restart.sh gru "$W/logs/ai_gru_run${r}.log" || { echo "AI 서버 재시작 실패 — 중단"; exit 1; }
  run_one gru ramp "$r" < /dev/null
done
./scripts/switch_scaler.sh cleanup
kill -- -$LOGPID 2>/dev/null
echo "REPRO4_DONE $(date)"
