#!/bin/bash
# switch_scaler.sh — 모델 전환 시 클러스터 상태 정리
#
# usage:
#   ./switch_scaler.sh hpa      → HPA baseline 활성화, KEDA ScaledObject 제거
#   ./switch_scaler.sh ml       → KEDA ScaledObject(AI) 활성화, HPA 제거
#   ./switch_scaler.sh cleanup  → 둘 다 제거 + replicas=2로 초기화 (run 간 중립 상태)
#
# memory에 기록된 "HPA 재생성 이슈 + stale controller 간섭" 대응용

set -e
MODE="${1:-cleanup}"
NS="default"
DEPLOY="ticketbench-deploy"

echo "================================================"
echo "[switch_scaler] mode = ${MODE}"
echo "================================================"

echo "[1/3] 기존 오토스케일러 제거"
kubectl delete hpa --all -n ${NS} --ignore-not-found=true
kubectl delete scaledobject --all -n ${NS} --ignore-not-found=true

echo "[2/3] replicas 초기 상태로 되돌림 (2개)"
kubectl scale deployment/${DEPLOY} -n ${NS} --replicas=2
# Ready 상태가 될 때까지 대기
kubectl rollout status deployment/${DEPLOY} -n ${NS} --timeout=120s

echo "[3/3] 새 오토스케일러 적용"
case "${MODE}" in
  hpa)
    kubectl apply -f infra/hpa-baseline.yaml
    echo "    → HPA baseline 활성화 완료"
    ;;
  ml)
    # AI 추론 서버(ngrok) 살아있는지 간단 체크
    URL=$(grep -oP '(?<=url: ")[^"]+' infra/keda-scaler.yaml | head -1)
    if [ -n "$URL" ]; then
      echo "    → AI 추론 서버 health check: ${URL}"
      if ! curl -s -o /dev/null -w "%{http_code}" "${URL}" | grep -qE '^(200|404|405)$'; then
        echo "    [WARN] AI 추론 서버 응답 없음 — uvicorn 실행 확인 필요"
      fi
    fi
    kubectl apply -f infra/keda-scaler.yaml
    echo "    → KEDA ScaledObject(AI) 활성화 완료"
    ;;
  cleanup)
    echo "    → 오토스케일러 없는 중립 상태 (다음 run 준비)"
    ;;
  *)
    echo "    [ERROR] mode must be one of: hpa | ml | cleanup"
    exit 1
    ;;
esac

echo
echo "현재 상태:"
kubectl get hpa,scaledobject -n ${NS} 2>/dev/null || true
kubectl get deployment ${DEPLOY} -n ${NS} -o custom-columns=NAME:.metadata.name,DESIRED:.spec.replicas,READY:.status.readyReplicas
echo "================================================"
