import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import time
import numpy as np
import requests
import joblib
import tensorflow as tf
from fastapi import FastAPI
from collections import deque
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="TicketBench Multi-Model AutoScaling API")
Instrumentator().instrument(app).expose(app)

MODEL_TYPE = os.environ.get('MODEL_TYPE', 'ensemble')
model_paths = {
    'lstm': 'models/lstm_model.keras',
    'gru': 'models/gru_model.keras',
    'ensemble': 'models/ensemble_model.keras'
}

print(f"🚀 [System] {MODEL_TYPE.upper()} 모델 로딩 중...")
active_model = tf.keras.models.load_model(model_paths.get(MODEL_TYPE, 'models/ensemble_model.keras'), compile=False)
scaler = joblib.load('models/alibaba_scaler.pkl')  # ← Alibaba scaler
print(f"✅ [System] {MODEL_TYPE} 로딩 완료!")

traffic_memory = deque(maxlen=60)
for _ in range(60):
    traffic_memory.append([1, 1, 100.0])

last_known_traffic = (1, 1.0, 100.0)  # 0으로 초기화 X

def fetch_live_traffic():
    global last_known_traffic
    try:
        response = requests.get("http://localhost:8089/stats/requests", timeout=0.5)
        data = response.json()

        state = data.get("state", "unknown")
        if state == "stopped":
            last_known_traffic = (0, 0.0, 100.0)
            return 0, 0.0, 100.0

        user_count = data.get("user_count", 0)
        if user_count == 0:
            return last_known_traffic  # 일시적 0 → 마지막 값 유지

        rps = data.get("total_rps", 0)
        latency = data["stats"][0].get("median_response_time", 100.0) if data.get("stats") else 100.0
        last_known_traffic = (user_count, rps, latency)
        return user_count, rps, latency
    except Exception:
        return last_known_traffic  # 연결 실패 → 리셋 X, 마지막 값 유지

@app.get("/api/v1/predict")
def predict_metrics():
    start_time = time.time()
    u_count, rps, latency = fetch_live_traffic()
    traffic_memory.append([u_count, rps, latency])

    live_array = np.array(list(traffic_memory))
    live_scaled = scaler.transform(live_array)
    model_input = np.array([live_scaled])

    pred_scaled_value = active_model.predict(model_input, verbose=0)[0][0]
    temp_array = np.zeros((1, 3))
    temp_array[0, 2] = pred_scaled_value
    raw_prediction = scaler.inverse_transform(temp_array)[0, 2]

    if u_count < 50 and rps < 50:
        real_predicted_latency = latency
        replicas = max(1, min(int(latency / 50), 3))
    elif raw_prediction > 2500 or u_count > 350:
        real_predicted_latency = max(raw_prediction, 2500.0)
        replicas = 25
    else:
        real_predicted_latency = raw_prediction
        replicas = max(1, min(int(real_predicted_latency / 50), 25))

    # 유저 수 기반 최솟값 보정
    min_replicas_by_user = max(1, int(u_count / 20))
    replicas = max(replicas, min_replicas_by_user)
    replicas = int(max(1, min(replicas, 25)))

    inference_time = (time.time() - start_time) * 1000
    print(f"📊 [{MODEL_TYPE.upper()}] 유저:{u_count}명 | 필요파드: {replicas}개")
    return {"predicted_replicas": replicas}