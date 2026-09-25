#!/bin/bash
# ramp 재측정: 21:49~22:01 일시 지연 구간에 걸린 HPA run3, GRU run1 을 대체할 run 4 (원본 기록은 보존)
export AI_SERVER_URL="${1:?ngrok URL}"
W=$HOME/repro_gke
export PATH=$W/bin:$HOME/google-cloud-sdk/bin:$PATH
cd "$W"
IP=$(kubectl get svc ticketbench-svc -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
export TICKETBENCH_HOST="http://${IP}" TARGET_HOST="http://${IP}"
source scripts/week8_helpers.sh
hard_reset
run_one hpa ramp 4 < /dev/null
run_one gru ramp 4 < /dev/null
./scripts/switch_scaler.sh cleanup
echo "RERUN_DONE $(date)"
