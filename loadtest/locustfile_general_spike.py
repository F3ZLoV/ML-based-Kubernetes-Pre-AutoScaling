"""
General Spike Scenario — AAPA 'SPIKE' archetype mapping

목적:
  기존 locustfile_spike.py(티켓팅 연착륙 특화) 대비 "순수한" 스파이크.
  저부하 구간 → 급등 → 피크 유지 → 급하강 의 사각파에 가까운 형태.
  학습 데이터(Alibaba CPU trace)와 분포 거리가 더 먼 OOD 자극원.

구조:
  0   ~  60s  : baseline 30 users  (사전 학습 구간)
  60  ~  70s  : 10초 만에 600 users로 급등 (spawn_rate 60)
  70  ~ 250s  : 600 users 유지 (3분간 피크)
  250 ~ 260s  : 10초 만에 30 users로 급하강
  260 ~ 320s  : 하강 이후 baseline 30 users

총 길이: 320s (≈5.3분)
"""
import os

from locust import HttpUser, task, between, LoadTestShape


class TicketBenchUser(HttpUser):
    # Cluster LoadBalancer endpoint. Override per environment:
    #   export TARGET_HOST=http://<cluster-lb-ip>
    # (locust --host=... still takes precedence over this default.)
    host = os.getenv("TARGET_HOST", "http://localhost:8000")
    wait_time = between(0.1, 0.5)

    @task
    def load_test(self):
        self.client.get("/")


class GeneralSpikeShape(LoadTestShape):
    """순수 사각파 스파이크 — AAPA SPIKE archetype과 1:1 매핑."""

    stages = [
        {"duration": 60,  "users": 30,  "spawn_rate": 10},
        {"duration": 70,  "users": 600, "spawn_rate": 60},   # 10s 급등
        {"duration": 250, "users": 600, "spawn_rate": 10},   # 3분 피크 유지
        {"duration": 260, "users": 30,  "spawn_rate": 60},   # 10s 급하강
        {"duration": 320, "users": 30,  "spawn_rate": 10},
    ]

    def tick(self):
        t = self.get_run_time()
        for stage in self.stages:
            if t < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])
        return None
