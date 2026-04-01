import os
# TensorFlow의 C++ 레벨 에러/경고 로그를 완전히 차단 (0: 모두 출력, 3: FATAL만 출력)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import time
import numpy as np
import pandas as pd
import requests
import joblib
import tensorflow as tf
from fastapi import FastAPI
from collections import deque
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="TicketBench Ensemble AutoScaling API")
Instrumentator().instrument(app).expose(app)


# print("🚀 [System] LSTM 모델 로딩 중...")
# active_model = tf.keras.models.load_model('lstm_model.keras', compile=False)

# print("🚀 [System] GRU 모델 로딩 중...")
# active_model = tf.keras.models.load_model('gru_model.keras', compile=False)

print("🚀 [System] AI 앙상블 모델 로딩 중...")
active_model = tf.keras.models.load_model('ensemble_model.keras', compile=False)

scaler = joblib.load('aws_kaggle_scaler.pkl')
print("✅ [System] 로딩 완료! 실전 자율 방어 모드 가동.")

traffic_memory = deque(maxlen=5)
for _ in range(5):
    traffic_memory.append([1, 1, 100.0])

last_known_traffic = (0, 0.0, 100.0)

def fetch_live_traffic():
    global last_known_traffic
    try:
        response = requests.get("http://localhost:8089/stats/requests", timeout=0.5)
        data = response.json()
        
        user_count = data.get("user_count", 0)
        if user_count == 0:
            last_known_traffic = (0, 0.0, 100.0)
            return 0, 0.0, 100.0
            
        rps = data.get("total_rps", 0)
        latency = data["stats"][0].get("median_response_time", 100.0) if data.get("stats") else 100.0
        
        last_known_traffic = (user_count, rps, latency)
        return user_count, rps, latency
        
    except Exception as e:
            print(f"⚠️ [Locust 통신 실패] 이유: {e}")
            return last_known_traffic

@app.get("/api/v1/predict/ensemble")
def predict_ensemble():
    start_time = time.time()
    
    u_count, rps, latency = fetch_live_traffic()
    traffic_memory.append([u_count, rps, latency])
    
    live_df = pd.DataFrame(list(traffic_memory), columns=['User Count', 'Requests/s', 'Total Average Response Time'])
    live_scaled = scaler.transform(live_df)
    model_input = np.array([live_scaled])
    
    pred_scaled_value = active_model.predict(model_input, verbose=0)[0][0]
    
    temp_array = np.zeros((1, 3))
    temp_array[0, 2] = pred_scaled_value
    raw_prediction = scaler.inverse_transform(temp_array)[0, 2]
    
    # 5. [하이브리드 방어장치] - 공격적 스케일링 모드 적용
    if u_count < 50 and rps < 50:
        real_predicted_latency = latency 
        replicas = max(1, min(int(latency / 50), 3))
    elif raw_prediction > 2500 or u_count > 350:
        # 피크 타임 강제 방어: 예측치가 튀거나 유저가 350명 돌파 시 즉시 20개로 방어
        real_predicted_latency = max(raw_prediction, 2500.0)
        replicas = 25  # 40에서 20으로 수정
    else:
        real_predicted_latency = raw_prediction
        replicas = max(1, min(int(real_predicted_latency / 50), 25)) # 40에서 20으로 수정
            
    replicas = int(max(1, replicas))
    inference_time = (time.time() - start_time) * 1000
    
    # 로그 출력 최적화
    print(f"📊 [Live] 유저:{u_count}명 | RPS:{rps:.1f} | 현재지연:{latency:.1f}ms")
    print(f"⚡ [Ensemble 예측] 미래지연: {real_predicted_latency:.1f}ms -> 필요파드: {replicas}개 (추론: {inference_time:.2f}ms)\n")
    
    return {"predicted_replicas": replicas}