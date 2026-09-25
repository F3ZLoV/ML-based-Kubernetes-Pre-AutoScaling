#!/bin/bash
# gke_stop.sh — GKE 실험 환경 삭제 및 과금 리소스 잔존 여부 확인
#
# usage:
#   export PROJECT_ID=<gcp-project-id>
#   ./scripts/gke_stop.sh

set -e
: "${PROJECT_ID:?PROJECT_ID 를 설정하세요 (export PROJECT_ID=...)}"
ZONE="${ZONE:-asia-northeast3-a}"
CLUSTER="${CLUSTER:-ml-k8s-gke}"

echo "[1/3] LoadBalancer 서비스 먼저 삭제 (외부 IP·포워딩 규칙 회수)"
kubectl delete svc ticketbench-svc --ignore-not-found=true --wait=true || true

echo "[2/3] 클러스터 삭제"
gcloud container clusters delete "${CLUSTER}" --zone "${ZONE}" --project "${PROJECT_ID}" --quiet

echo "[3/3] 남은 과금 리소스 확인 (비어 있어야 정상)"
echo "--- 포워딩 규칙 ---"; gcloud compute forwarding-rules list --project "${PROJECT_ID}"
echo "--- 디스크 ---";      gcloud compute disks list --project "${PROJECT_ID}"
echo "--- 고정 IP ---";     gcloud compute addresses list --project "${PROJECT_ID}"
echo "완료."
