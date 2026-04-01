#!/bin/bash

echo "[1/4] DigitalOcean K8s 클러스터 생성을 시작합니다."
doctl kubernetes cluster create ml-k8s-cluster --region sgp1 --size s-2vcpu-4gb --count 2

echo "[2/4] 로컬 환경(kubectl)과 클러스터를 연결합니다."
doctl kubernetes cluster kubeconfig save ml-k8s-cluster

echo "[3/4] Helm 저장소를 최신화합니다."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

echo "[4/4] Prometheus와 Grafana 모니터링 스택을 설치합니다."
helm install prometheus prometheus-community/kube-prometheus-stack

echo "모든 인프라 세팅이 완료되었습니다. Lens에서 상태를 확인해 보세요."
