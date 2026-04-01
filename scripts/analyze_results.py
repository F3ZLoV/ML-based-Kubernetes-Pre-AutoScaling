# analyze_results.py
import pandas as pd
import glob
import numpy as np

print("=" * 70)
print("  논문용 실험 결과 종합 분석")
print("=" * 70)

# 1. 리드 타임 분석
lead_files = glob.glob("results/lead_time_*.csv")
all_lead = pd.concat([pd.read_csv(f) for f in lead_files], ignore_index=True)
all_lead = all_lead[all_lead['event_type'] == 'scale_out']
all_lead['lead_time_sec'] = all_lead['lead_time_sec'].astype(float)

lead_summary = all_lead.groupby(['model', 'scenario']).agg(
    runs=('run', 'nunique'),
    total_events=('lead_time_sec', 'count'),
    mean_lead=('lead_time_sec', 'mean'),
    std_lead=('lead_time_sec', 'std'),
    min_lead=('lead_time_sec', 'min'),
    max_lead=('lead_time_sec', 'max'),
    p95_lead=('lead_time_sec', lambda x: np.percentile(x, 95)),
).round(3)

print("\n[Table 1] 스케일링 리드 타임 비교")
print(lead_summary.to_string())

# 2. Locust P95/P99 레이턴시 분석
stats_files = glob.glob("results/locust_*_stats.csv")
for f in stats_files:
    df = pd.read_csv(f)
    agg = df[df['Name'] == 'Aggregated']
    if not agg.empty:
        row = agg.iloc[0]
        label = f.split('/')[-1].replace('_stats.csv', '')
        print(f"\n[{label}]")
        print(f"  Total Requests: {row.get('Request Count', 'N/A')}")
        print(f"  Failure Count:  {row.get('Failure Count', 'N/A')}")
        print(f"  Median (ms):    {row.get('Median Response Time', 'N/A')}")
        print(f"  P95 (ms):       {row.get('95%', 'N/A')}")
        print(f"  P99 (ms):       {row.get('99%', 'N/A')}")
        
        total = row.get('Request Count', 0)
        fails = row.get('Failure Count', 0)
        if total > 0:
            print(f"  Error Rate:     {fails/total*100:.2f}%")

print("\n" + "=" * 70)
print("  CSV 원본 저장 위치: results/ 디렉토리")
print("=" * 70)