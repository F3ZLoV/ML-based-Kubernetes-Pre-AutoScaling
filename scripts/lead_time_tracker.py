import subprocess
import time
from datetime import datetime

DEPLOYMENT_NAME = "ticketbench-deploy"

def get_replicas():
    try:
        # spec.replicas(목표치)와 status.readyReplicas(실제 준비완료) 가져오기
        cmd = f"kubectl get deployment {DEPLOYMENT_NAME} -o jsonpath='{{.spec.replicas}},{{.status.readyReplicas}}'"
        result = subprocess.check_output(cmd, shell=True).decode('utf-8').strip().split(',')
        desired = int(result[0]) if result[0] else 0
        ready = int(result[1]) if len(result)>1 and result[1] else 0
        return desired, ready
    except Exception:
        return 0, 0

print("="*60)
print(" ⏱️ [논문 데이터 추출용] K8s 스케일링 리드 타임 정밀 추적기")
print("="*60)

last_desired, last_ready = get_replicas()
print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 모니터링 시작 (초기 파드: {last_ready}개)\n")

scale_out_times = []
scaling_in_progress = False
start_time = 0

try:
    while True:
        desired, ready = get_replicas()
        
        # 1. 확장이 시작된 순간 포착 (목표치가 실제보다 커짐)
        if desired > last_desired and not scaling_in_progress:
            print(f"🚨 [Scale-Out 감지] 모델 확장 명령! ({last_ready}개 -> {desired}개)")
            start_time = time.time()
            scaling_in_progress = True
            
        # 2. 확장이 완료된 순간 포착 (실제 파드가 목표치에 도달)
        elif scaling_in_progress and ready == desired:
            lead_time = time.time() - start_time
            scale_out_times.append(lead_time)
            print(f"✅ [도달 완료] 파드 {ready}개 Ready! (소요 시간: {lead_time:.2f}초)\n")
            scaling_in_progress = False
            
        # 3. 축소 감지 (기록용)
        elif desired < last_desired:
            print(f"📉 [Scale-Down 감지] 파드 축소 ({last_ready}개 -> {desired}개)\n")
            scaling_in_progress = False # 축소 중에는 시간 측정 리셋
            
        last_desired = desired
        last_ready = ready
        time.sleep(0.5) # 0.5초 단위 정밀 측정

except KeyboardInterrupt:
    # Ctrl+C를 누르면 최종 실험 결과 리포트 출력
    print("\n" + "="*60)
    print(" 📊 [실험 결과 요약 리포트]")
    print("="*60)
    if scale_out_times:
        print(f"총 확장 이벤트 횟수 : {len(scale_out_times)}회")
        print(f"평균 리드 타임      : {sum(scale_out_times)/len(scale_out_times):.2f}초")
        print(f"최소 리드 타임      : {min(scale_out_times):.2f}초")
        print(f"최대 리드 타임      : {max(scale_out_times):.2f}초")
    else:
        print("측정된 확장 이벤트가 없습니다.")
    print("="*60)