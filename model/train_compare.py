import time
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, GRU, Dense
import matplotlib.pyplot as plt

def build_model(model_type, input_shape):
    model = Sequential()
    if model_type == 'LSTM':
        # LSTM
        model.add(LSTM(50, activation='relu', input_shape=input_shape))
    elif model_type == 'GRU':
        # GRU
        model.add(GRU(50, activation='relu', input_shape=input_shape))
    
    model.add(Dense(1)) # 결과값 (예측된 트래픽 또는 응답시간)
    model.compile(optimizer='adam', loss='mse', metrics=['mae'])
    return model

def train_and_compare(X_train, y_train, epochs=10, batch_size=256):
    input_shape = (X_train.shape[1], X_train.shape[2])
    
    models = {
        'LSTM': build_model('LSTM', input_shape), 
        'GRU': build_model('GRU', input_shape)
    }
    
    results = {}
    
    for name, model in models.items():
        print(f"\n=========================================")
        print(f"[{name}] 모델 학습을 시작합니다...")
        print(f"=========================================")
        
        # 학습 시간 측정
        start_time = time.time()
        history = model.fit(X_train, y_train, epochs=epochs, batch_size=batch_size, validation_split=0.2, verbose=1)
        train_time = time.time() - start_time
        
        # 추론 속도 측정
        test_sample = X_train[:1] # 샘플 데이터 1개
        
        # 첫 번째 예측은 초기화 딜레이가 있으므로 한 번 허공에 날려줌(Warm-up)
        model.predict(test_sample, verbose=0) 
        
        inference_start = time.time()
        for _ in range(100):
            model.predict(test_sample, verbose=0)
        inference_time = (time.time() - inference_start) / 100 * 1000 # ms 단위로 변환
        
        # 모델 저장
        model.save(f'{name.lower()}_model.h5')
        print(f"{name} 모델 저장 완료 ({name.lower()}_model.h5)")
        
        results[name] = {
            'val_loss': history.history['val_loss'][-1],
            'train_time': train_time,
            'inference_time_ms': inference_time,
            'history': history
        }
        
        print(f"\n🎯 [{name} 최종 성적표]")
        print(f" - 검증 오차(Val Loss): {results[name]['val_loss']:.6f}")
        print(f" - 총 학습 시간: {train_time:.2f}초")
        print(f" - 1회 추론 속도: {inference_time:.2f} ms")

    # 4. [논문용 시각화] 학습 곡선 비교 플롯 생성
    plt.figure(figsize=(10, 5))
    plt.plot(results['LSTM']['history'].history['val_loss'], label='LSTM Val Loss', color='blue')
    plt.plot(results['GRU']['history'].history['val_loss'], label='GRU Val Loss', color='red', linestyle='--')
    plt.title('LSTM vs GRU Validation Loss Comparison (Kaggle Data)')
    plt.xlabel('Epochs')
    plt.ylabel('Loss (MSE)')
    plt.legend()
    plt.savefig('lstm_vs_gru_loss.png')
    print("\n📊 비교 결과 그래프가 'lstm_vs_gru_loss.png'로 저장되었습니다!")
    
    return results

if __name__ == "__main__":
    print("⏳ 전처리된 Kaggle 데이터 로드 중...")
    try:
        X_train = np.load('X_train_kaggle.npy')
        y_train = np.load('y_train_kaggle.npy')
        print(f"✅ 데이터 로드 완료! X 형태: {X_train.shape}")
        
        # 맞대결 시작!
        train_and_compare(X_train, y_train, epochs=10, batch_size=256)
        
    except FileNotFoundError:
        print("❌ 에러: 'X_train_kaggle.npy' 파일을 찾을 수 없습니다. 이전 단계(kaggle_preprocess.py)가 정상적으로 완료되었는지 확인해주세요.")