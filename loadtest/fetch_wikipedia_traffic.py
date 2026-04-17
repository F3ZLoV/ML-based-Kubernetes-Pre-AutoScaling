"""
Wikipedia 실제 시간별 트래픽 데이터를 Wikimedia Pageview API에서 가져와
Locust LoadTestShape 코드를 자동 생성하는 스크립트.

Usage:
    python fetch_wikipedia_traffic.py [--date 20241101] [--output locustfile_wikipedia.py]

API 엔드포인트:
    GET /metrics/pageviews/aggregate/{project}/{access}/{agent}/{granularity}/{start}/{end}
    - granularity: hourly 지원 (aggregate 엔드포인트만, per-article는 daily만)
    - 라이선스: CC0 1.0
"""

import requests
import json
import sys
import argparse
from datetime import datetime, timedelta


def fetch_hourly_pageviews(date_str: str = "20241101") -> list[dict]:
    """
    Wikimedia Pageview API에서 en.wikipedia의 시간별 pageview 데이터를 가져옴.
    
    Args:
        date_str: YYYYMMDD 형식의 날짜 (기본: 20241101)
    
    Returns:
        [{"hour": 0, "views": 12345678}, ...] 형태의 리스트 (24개)
    """
    start = f"{date_str}00"  # YYYYMMDD00 형식
    
    # 다음날 계산
    dt = datetime.strptime(date_str, "%Y%m%d")
    end_dt = dt + timedelta(days=1)
    end = end_dt.strftime("%Y%m%d") + "00"
    
    url = (
        f"https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate/"
        f"en.wikipedia.org/all-access/user/hourly/{start}/{end}"
    )
    
    headers = {
        "accept": "application/json",
        "User-Agent": "ML-Kubernetes-PreAutoScaling-Research/1.0 "
                      "(https://github.com/F3ZLoV/ML-based-Kubernetes-Pre-AutoScaling; "
                      "academic research)"
    }
    
    print(f"[*] Fetching: {url}")
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    
    data = resp.json()
    items = data.get("items", [])
    
    if len(items) != 24:
        print(f"[!] Warning: Expected 24 hourly entries, got {len(items)}")
    
    hourly_data = []
    for item in items:
        ts = item["timestamp"]  # e.g., "2024110100"
        hour = int(ts[8:10])    # 마지막 2자리가 시간
        views = item["views"]
        hourly_data.append({"hour": hour, "views": views})
    
    return hourly_data


def normalize_to_pattern(hourly_data: list[dict]) -> list[float]:
    """
    시간별 pageview 수를 0~1로 min-max 정규화.
    """
    views = [d["views"] for d in hourly_data]
    min_v = min(views)
    max_v = max(views)
    
    if max_v == min_v:
        return [0.5] * len(views)
    
    return [round((v - min_v) / (max_v - min_v), 4) for v in views]


def generate_locustfile(
    hourly_data: list[dict],
    pattern: list[float],
    date_str: str,
    output_path: str,
    max_users: int = 600,
    min_users: int = 20,
    total_duration: int = 600,  # 10분
):
    """
    실제 데이터 기반 Locust LoadTestShape 파일 생성.
    """
    step_secs = total_duration // len(pattern)
    
    # Raw data를 주석으로 포함 (재현 가능성 보장)
    raw_data_comment = "\n".join(
        f"    #   UTC {d['hour']:02d}:00 → {d['views']:>12,} views  (normalized: {p:.4f})"
        for d, p in zip(hourly_data, pattern)
    )
    
    views_list = [d["views"] for d in hourly_data]
    
    code = f'''"""
Wikipedia Real Traffic Pattern — Locust LoadTestShape

데이터 출처: Wikimedia Pageview API (CC0 1.0 License)
    Endpoint: /metrics/pageviews/aggregate/en.wikipedia.org/all-access/user/hourly/
    Date: {date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} (UTC)
    Project: en.wikipedia.org
    Access: all-access
    Agent: user (bot/spider 제외)

Raw hourly pageview counts:
{raw_data_comment}

    Total daily views: {sum(views_list):,}
    Peak hour (UTC): {hourly_data[pattern.index(max(pattern))]["hour"]:02d}:00 ({max(views_list):,} views)
    Low  hour (UTC): {hourly_data[pattern.index(min(pattern))]["hour"]:02d}:00 ({min(views_list):,} views)

정규화 방식: Min-Max Normalization (0~1)
압축 비율: 24시간 → {total_duration}초 ({total_duration // 60}분)
각 시간대 스텝: {step_secs}초

생성 스크립트: fetch_wikipedia_traffic.py
"""
from locust import HttpUser, task, between, LoadTestShape


class TicketBenchUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def load_test(self):
        self.client.get("/")


class WikipediaTrafficShape(LoadTestShape):
    """
    Wikipedia en.wikipedia.org 실제 시간별 트래픽 패턴 재현.
    Wikimedia Pageview API에서 추출한 {date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} 데이터 기반.
    """

    # 실제 API 응답에서 추출한 시간별 정규화 패턴 (0.0 ~ 1.0)
    # 각 값 = (해당 시간 views - min) / (max - min)
    HOURLY_PATTERN = {pattern}

    MAX_USERS   = {max_users}    # 최대 동시 사용자
    MIN_USERS   = {min_users}     # 최소 동시 사용자
    STEP_SECS   = {step_secs}     # 각 시간대당 {step_secs}초 (총 {total_duration}초 = {total_duration // 60}분)
    SPAWN_RATE  = 40      # 사용자 생성/제거 속도

    def tick(self):
        t = self.get_run_time()
        total = len(self.HOURLY_PATTERN) * self.STEP_SECS

        if t > total:
            return None

        hour_idx = min(int(t / self.STEP_SECS), len(self.HOURLY_PATTERN) - 1)
        ratio = self.HOURLY_PATTERN[hour_idx]
        users = int(self.MIN_USERS + (self.MAX_USERS - self.MIN_USERS) * ratio)

        return (users, self.SPAWN_RATE)
'''
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(code)
    
    print(f"\n[✓] Generated: {output_path}")
    print(f"    Pattern: {pattern}")
    print(f"    Duration: {total_duration}s ({total_duration // 60}min)")
    print(f"    Users: {min_users} ~ {max_users}")
    print(f"    Steps: {len(pattern)} × {step_secs}s each")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch real Wikipedia hourly traffic and generate Locust shape"
    )
    parser.add_argument(
        "--date", default="20241101",
        help="Date to fetch (YYYYMMDD format, default: 20241101)"
    )
    parser.add_argument(
        "--output", default="locustfile_wikipedia.py",
        help="Output locustfile path (default: locustfile_wikipedia.py)"
    )
    parser.add_argument(
        "--max-users", type=int, default=600,
        help="Maximum concurrent users (default: 600)"
    )
    parser.add_argument(
        "--min-users", type=int, default=20,
        help="Minimum concurrent users (default: 20)"
    )
    parser.add_argument(
        "--duration", type=int, default=600,
        help="Total test duration in seconds (default: 600 = 10min)"
    )
    
    args = parser.parse_args()
    
    # 1. API에서 실제 데이터 가져오기
    hourly_data = fetch_hourly_pageviews(args.date)
    
    print(f"\n[*] Raw hourly data for {args.date}:")
    for d in hourly_data:
        print(f"    UTC {d['hour']:02d}:00 → {d['views']:>12,} views")
    
    # 2. 정규화
    pattern = normalize_to_pattern(hourly_data)
    
    # 3. Locust 파일 생성
    generate_locustfile(
        hourly_data=hourly_data,
        pattern=pattern,
        date_str=args.date,
        output_path=args.output,
        max_users=args.max_users,
        min_users=args.min_users,
        total_duration=args.duration,
    )
    
    # 4. 검증 출력
    print(f"\n[*] Verification — expected user counts per step:")
    for i, (d, p) in enumerate(zip(hourly_data, pattern)):
        users = int(args.min_users + (args.max_users - args.min_users) * p)
        bar = "█" * int(p * 40)
        print(f"    [{i*25:4d}s] UTC {d['hour']:02d}:00  {users:4d} users  {bar}")


if __name__ == "__main__":
    main()
