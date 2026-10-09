#!/bin/bash
# 파드 상태 변화를 ms 단위 로컬 시각과 함께 기록 + 노드 CPU 10초마다. usage: podlog.sh <outdir>
OUT="$1"; mkdir -p "$OUT"
export PATH=$HOME/google-cloud-sdk/bin:$PATH
( while true; do
    kubectl get pods -l app=ticketbench -w --output-watch-events \
      -o custom-columns=EV:.type,NAME:.object.metadata.name,NODE:.object.spec.nodeName,PHASE:.object.status.phase,STARTED:.object.status.containerStatuses[0].started,READY:.object.status.containerStatuses[0].ready,DEL:.object.metadata.deletionTimestamp \
      2>/dev/null | while IFS= read -r l; do echo "$(date +%s.%3N) $l"; done
    sleep 1   # watch 연결이 끊기면 다시 붙음
  done ) >> "$OUT/pods.log" &
( while true; do
    kubectl top nodes --no-headers 2>/dev/null | while IFS= read -r l; do echo "$(date +%s) $l"; done
    sleep 10
  done ) >> "$OUT/nodes.log" &
wait
