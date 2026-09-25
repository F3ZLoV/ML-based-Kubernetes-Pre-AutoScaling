#!/bin/bash
# GKE 축소 재현: ramp 시나리오, HPA × 3 → GRU × 3
# 원본 results/ 를 덮어쓰지 않도록 ~/repro_gke 에서 실행한다.
# 인자: AI_SERVER_URL (ngrok 공개 주소)

REPO=/mnt/d/ml-autoscaling-project
W=$HOME/repro_gke
export PATH=$W/bin:$HOME/google-cloud-sdk/bin:$PATH
export AI_SERVER_URL="${1:?ngrok URL 필요}"
cd "$W"

IP=$(kubectl get svc ticketbench-svc -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
export TICKETBENCH_HOST="http://${IP}"
export TARGET_HOST="$TICKETBENCH_HOST"
echo "TICKETBENCH_HOST=$TICKETBENCH_HOST  AI_SERVER_URL=$AI_SERVER_URL"

source scripts/week8_helpers.sh
hard_reset
for model in hpa gru; do
  for run in 1 2 3; do
    # ML run 의 "Enter 확인" 프롬프트는 /dev/null 로 넘긴다 (서버는 이미 GRU 로 기동됨)
    run_one "$model" ramp "$run" < /dev/null
  done
done
./scripts/switch_scaler.sh cleanup
echo "REPRO_DONE $(date)"
