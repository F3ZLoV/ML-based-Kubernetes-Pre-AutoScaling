from locust import HttpUser, task, between, LoadTestShape

class TicketBenchUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def load_test(self):
        self.client.get("/")

class GradualRampShape(LoadTestShape):
    """
    [점진적 계단 증가 시나리오]
    30초 간격으로 100명씩 계단식 증가 → 유지 → 하강
    HPA가 '따라잡기 쉬운' 패턴 vs ML이 '선제 대응'하는 차이를 극대화
    """
    stages = [
        {"duration": 30,  "users": 50,  "spawn_rate": 10},
        {"duration": 60,  "users": 100, "spawn_rate": 20},
        {"duration": 90,  "users": 200, "spawn_rate": 30},
        {"duration": 120, "users": 300, "spawn_rate": 30},
        {"duration": 150, "users": 400, "spawn_rate": 30},
        {"duration": 210, "users": 500, "spawn_rate": 30},  # 1분 유지
        {"duration": 270, "users": 600, "spawn_rate": 30},  # 1분 유지 (피크)
        {"duration": 300, "users": 400, "spawn_rate": 20},
        {"duration": 330, "users": 200, "spawn_rate": 20},
        {"duration": 360, "users": 50,  "spawn_rate": 10},
        {"duration": 420, "users": 10,  "spawn_rate": 10},
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])
        return None