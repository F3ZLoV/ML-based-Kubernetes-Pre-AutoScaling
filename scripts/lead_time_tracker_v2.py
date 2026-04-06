# lead_time_tracker_v2.py
import subprocess
import time
import csv
import sys
from datetime import datetime

DEPLOYMENT_NAME = "ticketbench-deploy"

# 실험 메타 정보를 인자로 받음
MODEL_NAME = sys.argv[1] if len(sys.argv) > 1 else "ensemble"
SCENARIO_NAME = sys.argv[2] if len(sys.argv) > 2 else "spike"
RUN_NUMBER = sys.argv[3] if len(sys.argv) > 3 else "1"

OUTPUT_FILE = f"results/lead_time_{MODEL_NAME}_{SCENARIO_NAME}_run{RUN_NUMBER}.csv"

def get_replicas():
    try:
        cmd = f"kubectl get deployment {DEPLOYMENT_NAME} -o jsonpath='{{.spec.replicas}},{{.status.readyReplicas}}'"
        result = subprocess.check_output(cmd, shell=True).decode('utf-8').strip().split(',')
        desired = int(result[0]) if result[0] else 0
        ready = int(result[1]) if len(result) > 1 and result[1] else 0
        return desired, ready
    except Exception:
        return 0, 0

# CSV 파일 초기화
import os
os.makedirs("results", exist_ok=True)

with open(OUTPUT_FILE, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([
        'timestamp', 'model', 'scenario', 'run',
        'event_type', 'from_replicas', 'to_replicas', 
        'lead_time_sec'
    ])

print("=" * 60)
print(f" [v2] K8s 리드 타임 정밀 추적기")
print(f" Model: {MODEL_NAME} | Scenario: {SCENARIO_NAME} | Run: {RUN_NUMBER}")
print("=" * 60)

last_desired, last_ready = get_replicas()
scale_out_times = []
scaling_in_progress = False
scale_start_time = 0
from_replicas = 0

try:
    while True:
        desired, ready = get_replicas()

        if desired > last_desired and not scaling_in_progress:
            from_replicas = last_ready
            scale_start_time = time.time()
            scaling_in_progress = True
            print(f"🚨 [Scale-Out] {from_replicas}개 -> {desired}개")

        elif scaling_in_progress and ready == desired:
            lead_time = time.time() - scale_start_time
            scale_out_times.append(lead_time)

            # CSV에 즉시 기록
            with open(OUTPUT_FILE, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(), MODEL_NAME, SCENARIO_NAME, RUN_NUMBER,
                    'scale_out', from_replicas, ready, f"{lead_time:.3f}"
                ])

            print(f"✅ [Ready] {ready}개 도달 ({lead_time:.2f}s)")
            scaling_in_progress = False

        elif scaling_in_progress and desired < last_desired:
            # 목표치가 하향 조정됨 → 현재 ready 기준으로 완료 처리
            lead_time = time.time() - scale_start_time
            scale_out_times.append(lead_time)
            
            with open(OUTPUT_FILE, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(), MODEL_NAME, SCENARIO_NAME, RUN_NUMBER,
                    'scale_out_partial', from_replicas, ready, f"{lead_time:.3f}"
                ])
            
            print(f"⚠️ [목표 변경] {ready}개에서 목표 재조정 ({lead_time:.2f}s)")
            scaling_in_progress = False

        elif desired < last_desired:
            with open(OUTPUT_FILE, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(), MODEL_NAME, SCENARIO_NAME, RUN_NUMBER,
                    'scale_down', last_ready, desired, '0'
                ])
            scaling_in_progress = False

        last_desired = desired
        last_ready = ready
        time.sleep(0.5)

except KeyboardInterrupt:
    print(f"\n📊 결과 저장 완료: {OUTPUT_FILE}")
    if scale_out_times:
        print(f"  총 {len(scale_out_times)}회 | 평균 {sum(scale_out_times)/len(scale_out_times):.2f}s")
        print(f"  최소 {min(scale_out_times):.2f}s | 최대 {max(scale_out_times):.2f}s")