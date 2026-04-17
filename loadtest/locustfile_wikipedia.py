"""
Wikipedia 실제 트래픽 기반 Locust Shape

출처: Wikimedia Pageviews API
      https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate/
      en.wikipedia / all-access / all-agents / hourly
      기간: 2024-11-01 00:00 UTC ~ 2024-11-01 23:00 UTC

원본 데이터:
  최솟값: 10,969,769 views (UTC 06:00)
  최댓값: 16,206,962 views (UTC 18:00)
  → 0~1 정규화 후 20~600명 유저 수로 선형 매핑

24시간 패턴을 10분(600초)으로 압축
각 시간대당 25초 (600초 / 24시간대)
"""
from locust import HttpUser, task, between, LoadTestShape

class TicketBenchUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def load_test(self):
        self.client.get("/")

class WikipediaTrafficShape(LoadTestShape):

    # Wikimedia API 실측 데이터 (2024-11-01, UTC 00~23시)
    # 정규화: (views - min) / (max - min)
    HOURLY_PATTERN = [
        0.4976, 0.4961, 0.4550, 0.3487, 0.1832, 0.0194,  # 00~05
        0.0000, 0.0208, 0.0844, 0.1209, 0.1812, 0.2538,  # 06~11
        0.4616, 0.7109, 0.8042, 0.7936, 0.9238, 0.9650,  # 12~17
        1.0000, 0.9779, 0.9887, 0.9566, 0.8148, 0.7426,  # 18~23
    ]

    MAX_USERS  = 600
    MIN_USERS  = 20
    STEP_SECS  = 25    # 25초 × 24 = 600초 (10분)
    SPAWN_RATE = 40

    def tick(self):
        t = self.get_run_time()
        total = len(self.HOURLY_PATTERN) * self.STEP_SECS

        if t > total:
            return None

        hour_idx = min(int(t / self.STEP_SECS), len(self.HOURLY_PATTERN) - 1)
        ratio = self.HOURLY_PATTERN[hour_idx]
        users = int(self.MIN_USERS + (self.MAX_USERS - self.MIN_USERS) * ratio)

        return (users, self.SPAWN_RATE)