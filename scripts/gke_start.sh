#!/bin/bash
# gke_start.sh — GKE에 실험 환경 구성 (start.sh 의 DOKS 버전을 대체)
#
# 원 논문 환경(DOKS s-2vcpu-4gb × 3)에 맞춰 e2-standard-2 × 3 으로 구성한다.
# e2-medium 은 공유 코어라 GKE 할당 CPU 가 노드당 940m 뿐이고, 시스템 파드(~1.9 코어)를
# 빼면 TicketBench(100m) 파드가 7~9개밖에 뜨지 않아 max=25 실험이 성립하지 않는다.
# 무료 체험 계정은 리전당 외부 IP(IN_USE_ADDRESSES) 한도가 4 → 노드 3 + LoadBalancer 1 로 꽉 찬다.
# 노드 풀을 교체할 때는 기존 풀을 먼저 0대로 줄여야 새 노드가 IP 를 받는다.
#
# usage:
#   export PROJECT_ID=<gcp-project-id>
#   ./scripts/gke_start.sh
#
# 끝나면 반드시 ./scripts/gke_stop.sh 로 삭제할 것 (노드·LB 과금).

set -e
: "${PROJECT_ID:?PROJECT_ID 를 설정하세요 (export PROJECT_ID=...)}"
ZONE="${ZONE:-asia-northeast3-a}"        # 서울
CLUSTER="${CLUSTER:-ml-k8s-gke}"
KEDA_VERSION="${KEDA_VERSION:-2.16.1}"   # 논문: KEDA 2.16.x

echo "[1/5] 프로젝트 설정 및 GKE API 활성화"
gcloud config set project "${PROJECT_ID}"
gcloud services enable container.googleapis.com

echo "[2/5] 클러스터 생성 (${CLUSTER}, ${ZONE}, e2-standard-2 × 3)"
# pd-standard 30GB: 무료 체험 계정의 SSD 쿼터(기본 디스크 100GB × 3 초과)를 피하기 위함
gcloud container clusters create "${CLUSTER}" \
  --zone "${ZONE}" \
  --num-nodes 3 \
  --machine-type e2-standard-2 \
  --disk-type pd-standard \
  --disk-size 30 \
  --release-channel regular

echo "[3/5] kubectl 연결"
gcloud container clusters get-credentials "${CLUSTER}" --zone "${ZONE}"
kubectl get nodes

echo "[4/5] KEDA ${KEDA_VERSION} 설치"
helm repo add kedacore https://kedacore.github.io/charts >/dev/null 2>&1 || true
helm repo update >/dev/null
helm upgrade --install keda kedacore/keda --namespace keda --create-namespace --version "${KEDA_VERSION}"
kubectl -n keda rollout status deployment/keda-operator --timeout=180s

echo "[5/5] TicketBench 배포 및 LoadBalancer IP 대기"
kubectl apply -f infra/ticketbench.yaml
kubectl rollout status deployment/ticketbench-deploy --timeout=180s
for i in $(seq 1 40); do
  IP=$(kubectl get svc ticketbench-svc -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
  [ -n "${IP}" ] && break
  sleep 10
done

echo
echo "================================================"
echo "완료. 실험 전에 아래를 실행하세요:"
echo "  export TICKETBENCH_HOST=http://${IP:-<IP 할당 대기 중: kubectl get svc ticketbench-svc>}"
echo "  export TARGET_HOST=\$TICKETBENCH_HOST"
echo "끝나면: ./scripts/gke_stop.sh"
echo "================================================"
