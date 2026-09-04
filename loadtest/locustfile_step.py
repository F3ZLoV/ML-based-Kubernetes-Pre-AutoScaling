"""
Step Scenario — AAPA 'STATIONARY (level-shift)' archetype mapping

목적:
  안정적 level에 머무르다 '정적 단계 전환(level shift)'을 일으키는 패턴.
  각 plateau 구간이 길어, HPA의 threshold 기반 동작 vs ML의 선제 확장
  차이를 명확히 관찰 가능.

구조:
  5개 plateau, 각 80초 유지:
    0   ~  80s : 50  users
    80  ~ 160s : 150 users
    160 ~ 240s : 300 users
    240 ~ 320s : 450 users
    320 ~ 400s : 600 users
    400 ~ 480s : 150 users (하강 계단)

총 길이: 480s (8분)

전환 시점:
  각 stage 경계에서 spawn_rate=30으로 빠르게 전이(약 5초 내 완료)
  전이 이후는 level 유지 → 안정 상태에서의 스케일링 안정성 비교
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


class StepShape(LoadTestShape):
    """계단식 level-shift — HPA/ML의 과도기 응답 차이 측정용."""

    stages = [
        {"duration":  80, "users":  50, "spawn_rate": 10},
        {"duration": 160, "users": 150, "spawn_rate": 30},
        {"duration": 240, "users": 300, "spawn_rate": 30},
        {"duration": 320, "users": 450, "spawn_rate": 30},
        {"duration": 400, "users": 600, "spawn_rate": 30},
        {"duration": 480, "users": 150, "spawn_rate": 30},   # 하강 step
    ]

    def tick(self):
        t = self.get_run_time()
        for stage in self.stages:
            if t < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])
        return None
