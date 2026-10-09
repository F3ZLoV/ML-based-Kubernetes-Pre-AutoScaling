#!/bin/bash
# 추론 서버를 새로 띄워 이전 run 의 기억(traffic_memory, last_known_traffic)을 지운다.
# usage: ai_restart.sh <model> <logfile>
MODEL="$1"; LOG="$2"
for p in $(pgrep -f "[u]vicorn ai_metrics_api"); do kill "$p"; done
for i in $(seq 1 20); do pgrep -f "[u]vicorn ai_metrics_api" >/dev/null || break; sleep 0.5; done
cd /mnt/d/ml-autoscaling-project/server
t0=$(date +%s)
PYTHONUNBUFFERED=1 MODEL_TYPE="$MODEL" TF_CPP_MIN_LOG_LEVEL=2 nohup ../venv/bin/python -m uvicorn ai_metrics_api:app \
  --host 0.0.0.0 --port 5005 > "$LOG" 2>&1 &
# /metrics 로 준비 확인 (/predict 를 부르면 그 호출 자체가 기억에 쌓이므로 쓰지 않는다)
for i in $(seq 1 600); do
  curl -s -o /dev/null -m 2 http://localhost:5005/metrics && { echo "AI_READY $MODEL $(( $(date +%s) - t0 ))s"; exit 0; }
  sleep 1
done
echo "AI_FAIL $MODEL"; exit 1
