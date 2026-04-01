import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
import joblib
import matplotlib.pyplot as plt

def preprocess_kaggle_data(file_path, look_back=5):
    print("⏳ Kaggle 데이터 로드 및 전처리 시작...")
    
    # 1. 데이터 로드
    df = pd.read_csv(file_path, usecols=['accessed_date', 'ip', 'network_protocol'])
    
    # 2. Locust 구조와 똑같이 맞추기 위해 컬럼 이름 변경
    df.rename(columns={'accessed_date': 'event_time', 'ip': 'user_id', 'network_protocol': 'event_type'}, inplace=True)
    
    # 3. 시간 단위 인덱싱 (초 단위 변환)
    df['event_time'] = pd.to_datetime(df['event_time'])
    df.set_index('event_time', inplace=True)
    
    # 4. 1초 단위(1S)로 리샘플링하여 메트릭 추출
    resampled = pd.DataFrame()
    resampled['User Count'] = df['user_id'].resample('1S').nunique()
    resampled['Requests/s'] = df['event_type'].resample('1S').count()
    
    # 5. 가상의 스파이크 응답시간 합성
    resampled['Total Average Response Time'] = 100 + (resampled['Requests/s'] ** 1.5) * 0.5
    resampled.fillna(0, inplace=True)

    # 시각화 (Dual Axis - 이중 Y축 그래프 그리기)
    fig, ax1 = plt.subplots(figsize=(12, 6))

    # 첫 번째 축: 트래픽 (RPS) - 파란색 영역
    color1 = '#3498db'
    ax1.set_xlabel('Time (1s Interval)', fontsize=12)
    ax1.set_ylabel('Requests Per Second (RPS)', color=color1, fontsize=12, fontweight='bold')
    ax1.plot(resampled.index, resampled['Requests/s'], color=color1, alpha=0.8, linewidth=2, label='RPS (Traffic)')
    ax1.fill_between(resampled.index, resampled['Requests/s'], color=color1, alpha=0.1) # 아래 영역 색칠
    ax1.tick_params(axis='y', labelcolor=color1)

    # 두 번째 축: 지연 시간 (Latency) - 빨간색 선
    ax2 = ax1.twinx()  
    color2 = '#e74c3c'
    ax2.set_ylabel('Latency / Response Time (ms)', color=color2, fontsize=12, fontweight='bold')
    ax2.plot(resampled.index, resampled['Total Average Response Time'], color=color2, linewidth=2.5, label='Latency')
    ax2.tick_params(axis='y', labelcolor=color2)

    # AI 오토스케일링 개입 기준선(Threshold) 표시
    ax2.axhline(y=150, color='#f39c12', linestyle='--', linewidth=2, label='AI Trigger Threshold (150ms)')

    # 타이틀 및 여백 정리
    plt.title('Kaggle E-commerce Data: Synthesized Bottleneck Pattern', fontsize=16, fontweight='bold', pad=15)
    fig.tight_layout()

    # 그래프 출력 및 저장 (PPT 삽입용)
    plt.savefig('kaggle_spike_simulation.png', dpi=300)
    plt.show()
    
    # 6. 정규화 (MinMaxScaler)
    scaler = MinMaxScaler()
    scaled_data = scaler.fit_transform(resampled[['User Count', 'Requests/s', 'Total Average Response Time']])
    
    # Scaler 저장 (나중에 FastAPI 서버에서 필요)
    joblib.dump(scaler, 'kaggle_scaler.pkl')
    
    # 7. 시계열 윈도우 생성 (과거 5초를 보고 다음 1초 예측)
    X, y = [], []
    for i in range(len(scaled_data) - look_back):
        X.append(scaled_data[i:(i + look_back), :])
        y.append(scaled_data[i + look_back, 2]) # 2번 인덱스가 Response Time
        
    X = np.array(X)
    y = np.array(y)
    
    print(f"✅ 전처리 완료! 입력 데이터 X 형태: {X.shape}")
    
    # 8. 다음 파일(train_compare.py)에서 쓸 수 있도록 전처리된 데이터 저장!
    np.save('X_train_kaggle.npy', X)
    np.save('y_train_kaggle.npy', y)
    print("💾 데이터를 'X_train_kaggle.npy', 'y_train_kaggle.npy'로 성공적으로 저장했습니다!")
    
    return X, y

if __name__ == "__main__":
    file_name = 'E-commerce Website Logs.csv'
    X_train, y_train = preprocess_kaggle_data(file_name, look_back=5)