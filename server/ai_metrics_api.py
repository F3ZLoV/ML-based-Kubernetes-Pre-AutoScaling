import os
# TensorFlow 로그 제어
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

app = FastAPI(title="TicketBench Multi-Model AutoScaling API")
Instrumentator().instrument(app).expose(app)

# [수정] 환경 변수에 따라 모델 로딩 분기
MODEL_TYPE = os.environ.get('MODEL_TYPE', 'ensemble')
model_paths = {
    'lstm': 'models/lstm_model.keras',
    'gru': 'models/gru_model.keras',
    'ensemble': 'models/ensemble_model.keras'
}

print(f"🚀 [System] {MODEL_TYPE.upper()} 모델 로딩 중...")
# 파일 경로 확인 후 로드
active_model = tf.keras.models.load_model(model_paths.get(MODEL_TYPE, 'models/ensemble_model.keras'), compile=False)
scaler = joblib.load('models/aws_kaggle_scaler.pkl')
print(f"✅ [System] {MODEL_TYPE} 로딩 완료!")

traffic_memory = deque(maxlen=60)
for _ in range(60):
    traffic_memory.append([1, 1, 100.0])

last_known_traffic = (0, 0.0, 100.0)

def fetch_live_traffic():
    global last_known_traffic
    try:
        response = requests.get("http://localhost:8089/stats/requests", timeout=0.5)
        data = response.json()
        user_count = data.get("user_count", 0)
        state = data.get("state", "unknown")  # 🌟 아까 날아갔던 상태값 부활
        
        # 🌟 부하 종료 시 좀비 유저 완벽 제거
        if state == "stopped":
            last_known_traffic = (0, 0.0, 100.0)
            return 0, 0.0, 100.0

        if user_count == 0:
            return last_known_traffic
            
        rps = data.get("total_rps", 0)
        latency = data["stats"][0].get("median_response_time", 100.0) if data.get("stats") else 100.0
        last_known_traffic = (user_count, rps, latency)
        return user_count, rps, latency
    except Exception:
        last_known_traffic = (0, 0.0, 100.0)
        return 0, 0.0, 100.0

@app.get("/api/v1/predict")
def predict_metrics():
    start_time = time.time()
    u_count, rps, latency = fetch_live_traffic()
    traffic_memory.append([u_count, rps, latency])

    # 🌟 경고 해결: 이름표가 달린 DataFrame으로 다시 변경!
    live_df = pd.DataFrame(list(traffic_memory), columns=['User Count', 'Requests/s', 'Total Average Response Time'])
    live_scaled = scaler.transform(live_df)
    model_input = np.array([live_scaled])

    pred_scaled_value = active_model.predict(model_input, verbose=0)[0][0]
    temp_array = np.zeros((1, 3))
    temp_array[0, 2] = pred_scaled_value
    raw_prediction = scaler.inverse_transform(temp_array)[0, 2]

    # 하이브리드 방어 로직
    if u_count < 50 and rps < 50:
        real_predicted_latency = latency
        replicas = max(1, min(int(latency / 50), 3))
    elif raw_prediction > 2500 or u_count > 350:
        real_predicted_latency = max(raw_prediction, 2500.0)
        replicas = 25
    else:
        real_predicted_latency = raw_prediction
        replicas = max(1, min(int(real_predicted_latency / 50), 25))

    # 유저 수 기반 최솟값 보정 (유저 20명당 파드 1개)
    min_replicas_by_user = max(1, int(u_count / 20))
    replicas = max(replicas, min_replicas_by_user)

    replicas = int(max(1, min(replicas, 25)))  # 상한 25 명시
    inference_time = (time.time() - start_time) * 1000

    print(f"📊 [{MODEL_TYPE.upper()}] 유저:{u_count}명 | 필요파드: {replicas}개")
    return {"predicted_replicas": replicas}