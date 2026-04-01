import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler

# 데이터 로드
df = pd.read_csv('real_stats_history.csv')

# 데이터 정규화 (MinMaxScaler)
# 인공지능은 단위(명, 초, ms)가 다르면 헷갈려하므로 모든 값을 0~1 사이로 압축해 줍니다.
scaler = MinMaxScaler()
features = df[['User Count', 'Requests/s', 'Total Average Response Time']]
scaled_data = scaler.fit_transform(features)

# 시계열 윈도우 생성 
# look_back=5 로 설정하면 "과거 25초(5개)의 흐름을 보고 다음 5초 뒤를 예측"하게 됩니다.
def create_dataset(dataset, look_back=5):
    X, y = [], []
    for i in range(len(dataset) - look_back):
        X.append(dataset[i:(i + look_back), :])
        y.append(dataset[i + look_back, 2]) # index 2: Response Time (우리가 예측할 타겟)
    return np.array(X), np.array(y)

LOOK_BACK = 5
X, y = create_dataset(scaled_data, look_back=LOOK_BACK)

print("LSTM 입력용 변환 완료!")
print(f"입력 데이터 X 형태: {X.shape} -> (총 31세트, 5칸씩 묶음, 3개 지표)")
print(f"정답 데이터 y 형태: {y.shape} -> (총 31개의 정답)")

# 그래프 띄우기
plt.figure(figsize=(10, 4))
plt.plot(df['Total Average Response Time'], label='Real Response Time (ms)', color='red', linewidth=2, marker='o')
plt.title('Real Load Test Data from Locust')
plt.xlabel('Time Steps (5s intervals)')
plt.ylabel('Milliseconds')
plt.grid(True)
plt.legend()
plt.show()