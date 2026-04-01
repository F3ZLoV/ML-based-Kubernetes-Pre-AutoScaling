import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense

# 데이터 로드 및 정규화
df = pd.read_csv('real_stats_history.csv')
scaler = MinMaxScaler()
features = df[['User Count', 'Requests/s', 'Total Average Response Time']]
scaled_data = scaler.fit_transform(features)

def create_dataset(dataset, look_back=5):
    X, y = [], []
    for i in range(len(dataset) - look_back):
        X.append(dataset[i:(i + look_back), :])
        y.append(dataset[i + look_back, 2]) # 타겟: Response Time
    return np.array(X), np.array(y)

LOOK_BACK = 5
X, y = create_dataset(scaled_data, look_back=LOOK_BACK)

# 데이터 분할 (80 : 20)
train_size = int(len(X) * 0.8)
X_train, X_test = X[:train_size], X[train_size:]
y_train, y_test = y[:train_size], y[train_size:]

# LSTM 모델 생성
model = Sequential()
model.add(LSTM(50, activation='relu', input_shape=(LOOK_BACK, 3)))
model.add(Dense(1)) 
model.compile(optimizer='adam', loss='mse')


# 모델 학습
history = model.fit(X_train, y_train, epochs=50, batch_size=4, validation_data=(X_test, y_test), verbose=1)

# 예측 시도
predictions = model.predict(X)

# 6. 0~1로 압축했던 데이터를 다시 밀리초(ms) 단위로 원상복구
dummy_pred = np.zeros((len(predictions), 3))
dummy_pred[:, 2] = predictions[:, 0]
predictions_ms = scaler.inverse_transform(dummy_pred)[:, 2]

dummy_actual = np.zeros((len(y), 3))
dummy_actual[:, 2] = y
actual_ms = scaler.inverse_transform(dummy_actual)[:, 2]

# 실제 결과 vs AI 예측 결과 비교 그래프 출력
plt.figure(figsize=(10, 5))
plt.plot(actual_ms, label='Actual Response Time (Real)', color='blue', marker='o')
plt.plot(predictions_ms, label='AI Predicted Time', color='red', linestyle='--', marker='x')
plt.title('LSTM Model: Actual vs Predicted Response Time')
plt.xlabel('Time Steps')
plt.ylabel('Response Time (ms)')
plt.legend()
plt.grid(True)
plt.show()