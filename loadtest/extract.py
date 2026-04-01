import re
import json
import pandas as pd

# 1. 방금 올려주신 진짜 HTML 리포트 파일명
html_file = 'Locust_2026-03-16-22h37_locustfile.py_http___146.190.195.236_.html'

try:
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 2. HTML 코드 안에 숨어있는 JSON 데이터(stats_history)를 정규식으로 추출
    match = re.search(r'\[{"current_fail_per_sec".*?\}\]', content)
    
    if match:
        raw_json = match.group(0)
        data = json.loads(raw_json)
        
        # 3. LSTM 학습에 필요한 알맹이만 골라내기
        extracted = []
        for row in data:
            extracted.append({
                'Timestamp': row.get('time', ''),
                'User Count': row.get('user_count', [None, 0])[1],
                'Requests/s': row.get('current_rps', [None, 0])[1],
                'Total Average Response Time': row.get('total_avg_response_time', [None, 0])[1]
            })
            
        # 4. 진짜 시계열 데이터 CSV로 예쁘게 저장
        df = pd.DataFrame(extracted)
        df.to_csv('real_stats_history.csv', index=False)
        
        print("🎉 대성공! HTML에서 진짜 데이터를 구출했습니다.")
        print(df.head())
        print(f"\n총 {len(df)}개의 시간대별 데이터가 'real_stats_history.csv'로 저장되었습니다.")
    else:
        print("데이터를 찾을 수 없습니다. HTML 파일이 원본이 맞는지 확인해 주세요.")
        
except Exception as e:
    print(f"에러 발생: {e}")