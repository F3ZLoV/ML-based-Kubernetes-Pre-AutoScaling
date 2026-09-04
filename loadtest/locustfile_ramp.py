"""
Pure Ramp-up Scenario — AAPA 'RAMP' archetype mapping

목적:
  시간에 따라 선형으로 증가하는 '완만한' 트래픽.
  wiki 시나리오(24h 압축)와 달리 하강 없이 상승만 재현.
  예측 기반 선제 대응이 오히려 과잉 반응으로 작동하는지 재검증.

구조:
  10초마다 20명씩 꾸준히 증가. 0s → 300s (5분) 간 선형 ramp.
  300s ~ 420s: 600 users 유지 구간.
  420s ~ 480s: 감쇠(cooldown).

총 길이: 480s (8분)
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


class LinearRampShape(LoadTestShape):
    """선형 증가 램프 — 완만한 상승에서 ML 선제 대응의 적정성 검증."""

    RAMP_DURATION    = 300    # 0~300s: 선형 증가
    SUSTAIN_DURATION = 120    # 300~420s: 600명 유지
    COOLDOWN         = 60     # 420~480s: 하강
    MIN_USERS        = 0
    MAX_USERS        = 600
    SPAWN_RATE       = 20

    def tick(self):
        t = self.get_run_time()
        total = self.RAMP_DURATION + self.SUSTAIN_DURATION + self.COOLDOWN

        if t > total:
            return None

        # 1) 선형 상승 구간
        if t < self.RAMP_DURATION:
            ratio = t / self.RAMP_DURATION
            users = int(self.MIN_USERS + (self.MAX_USERS - self.MIN_USERS) * ratio)
            users = max(1, users)          # locust 최소 1명 필요
            return (users, self.SPAWN_RATE)

        # 2) 피크 유지 구간
        if t < self.RAMP_DURATION + self.SUSTAIN_DURATION:
            return (self.MAX_USERS, self.SPAWN_RATE)

        # 3) 감쇠 구간
        dec_t = t - (self.RAMP_DURATION + self.SUSTAIN_DURATION)
        ratio = 1.0 - (dec_t / self.COOLDOWN)
        users = int(self.MAX_USERS * ratio)
        users = max(10, users)
        return (users, self.SPAWN_RATE)
