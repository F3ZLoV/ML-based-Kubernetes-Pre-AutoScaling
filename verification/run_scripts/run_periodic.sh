#!/bin/bash
# GKE 재현: periodic 시나리오, 지정 모델 × 3
# usage: run_periodic.sh <model> <AI_SERVER_URL>
# 원본 week8_helpers.sh 는 수정하지 않고, periodic 항목만 추가한 사본을 재현 폴더에서 사용한다.
MODEL="${1:?model}"
export AI_SERVER_URL="${2:?ngrok URL}"
W=$HOME/repro_gke
export PATH=$W/bin:$HOME/google-cloud-sdk/bin:$PATH
cd "$W"

IP=$(kubectl get svc ticketbench-svc -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
export TICKETBENCH_HOST="http://${IP}"
export TARGET_HOST="$TICKETBENCH_HOST"

# periodic: 540s shape → 여유 10s (ramp 480s → 490s 와 같은 규칙)
sed '/ramp)          locfile=/i\        periodic)      locfile="loadtest/locustfile_periodic.py"; dur=550 ;;' \
    scripts/week8_helpers.sh > helpers_periodic.sh
grep -q 'locustfile_periodic' helpers_periodic.sh || { echo "ERROR: periodic 항목 추가 실패"; exit 1; }
source helpers_periodic.sh

echo "PERIODIC model=$MODEL host=$TICKETBENCH_HOST ai=$AI_SERVER_URL"
hard_reset
for run in 1 2 3; do
  run_one "$MODEL" periodic "$run" < /dev/null
done
./scripts/switch_scaler.sh cleanup
echo "PERIODIC_DONE $MODEL $(date)"
