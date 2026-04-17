import math
from locust import HttpUser, task, between, LoadTestShape

class TicketBenchUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def load_test(self):
        self.client.get("/")

class PeriodicWaveShape(LoadTestShape):
    """
    [주기형 트래픽 시나리오: 낮/밤 사이클 재현]
    
    0~60초:   워밍업 (50명 고정)
    60~480초: 사인파 주기 트래픽 (50~550명, 주기 120초)
              → 낮에 몰리고 밤에 줄어드는 패턴을 압축 재현
    480~540초: 쿨다운 (10명)
    """
    
    WARMUP_DURATION   = 60
    WAVE_DURATION     = 420   # 7분
    COOLDOWN_DURATION = 60
    
    MIN_USERS  = 50
    MAX_USERS  = 550
    PERIOD     = 120          # 사이클 주기 (초)
    SPAWN_RATE = 30

    def tick(self):
        t = self.get_run_time()
        total = self.WARMUP_DURATION + self.WAVE_DURATION + self.COOLDOWN_DURATION
        
        if t > total:
            return None
        
        # 워밍업
        if t < self.WARMUP_DURATION:
            return (self.MIN_USERS, 10)
        
        # 쿨다운
        if t >= self.WARMUP_DURATION + self.WAVE_DURATION:
            return (10, 10)
        
        # 주기형 파동 구간
        wave_t = t - self.WARMUP_DURATION
        # sin 파형: -1~1 → MIN~MAX 유저 수로 매핑
        sin_val = math.sin(2 * math.pi * wave_t / self.PERIOD)
        amplitude = (self.MAX_USERS - self.MIN_USERS) / 2
        mid = (self.MAX_USERS + self.MIN_USERS) / 2
        users = int(mid + amplitude * sin_val)
        users = max(self.MIN_USERS, min(self.MAX_USERS, users))
        
        return (users, self.SPAWN_RATE)
