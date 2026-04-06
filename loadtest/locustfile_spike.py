from locust import HttpUser, task, between, LoadTestShape

class TicketBenchUser(HttpUser):
    # 실제 유저들의 새로고침 속도 (0.1~0.5초)
    wait_time = between(0.1, 0.5) 

    @task
    def load_test(self):
        self.client.get("/") 

class SoftLandingTicketDropShape(LoadTestShape):
    """
    [실전 티켓팅 트래픽 시나리오: 연착륙(Soft-Landing) 하강 곡선]
    트래픽이 수직 낙하하지 않고 계단식으로 서서히 줄어들게 하여,
    AI가 '하강 기울기'를 인식하고 예측 지연시간을 안정적으로 낮추도록 유도합니다.
    """
    
    stages = [
        # 예열 및 대기
        {"duration": 30, "users": 50, "spawn_rate": 10},
        
        # 전조 증상 시작
        {"duration": 75, "users": 150, "spawn_rate": 20},

        {"duration": 135, "users": 350, "spawn_rate": 50},
        
        # 2분간 폭주 유지
        {"duration": 255, "users": 600, "spawn_rate": 100},
        
        # 1차 썰물: 매진 공지 확인 후 절반 이탈
        {"duration": 315, "users": 300, "spawn_rate": 30},
        
        # 2차 썰물: 남은 유저들 서서히 이탈
        {"duration": 375, "users": 100, "spawn_rate": 20},
        
        # 이벤트 완전 종료
        {"duration": 435, "users": 10, "spawn_rate": 10},
    ]

    def tick(self):
        run_time = self.get_run_time()

        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])

        return None