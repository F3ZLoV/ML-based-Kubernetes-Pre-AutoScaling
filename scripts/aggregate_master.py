"""
aggregate_master.py — 전체 실험 결과 통합 집계 (논문/PPT용)

입력:
  results/**/lead_time_*.csv  (AWS + Alibaba 4개 시나리오 + 8주차 3개 신규)
  results/**/*_stats.csv

출력:
  results/master_full.csv   (run 단위 raw, 논문용)
  results/master_full.xlsx  (시트 분리: lead_raw / locust_raw / summary / ppt_table)
  results/ppt_summary.csv   (PPT 요약표 한 장짜리 포맷)
"""
import pandas as pd
import numpy as np
import glob
import re
import os
from pathlib import Path

RESULTS_ROOT = "results"
OUT_CSV = "results/master_full.csv"
OUT_XLSX = "results/master_full.xlsx"
OUT_PPT_CSV = "results/ppt_summary.csv"

# -----------------------------------------------------------------------------
# 1) Lead-time 수집
# -----------------------------------------------------------------------------
def load_lead_times():
    files = glob.glob(f"{RESULTS_ROOT}/**/lead_time_*.csv", recursive=True)
    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f)
            df["__source"] = os.path.basename(f)
            dfs.append(df)
        except Exception as e:
            print(f"  [skip] {f}: {e}")
    if not dfs:
        return pd.DataFrame()
    all_df = pd.concat(dfs, ignore_index=True)
    all_df["lead_time_sec"] = pd.to_numeric(all_df["lead_time_sec"], errors="coerce")

    # dataset 컬럼 추론:
    #   - AWS 시나리오는 파일명이 lead_time_<model>_spike_run<n>.csv (AWS 전용 폴더에만 존재)
    #   - Alibaba 시나리오는 동일 포맷이지만 scenario ∈ {spike, periodic, wiki}
    #   - 8주차 신규 시나리오는 scenario ∈ {general_spike, step, ramp}
    def infer_dataset(row):
        src = row["__source"]
        if "Aws-dataset" in src or "aws" in src.lower():
            return "AWS"
        if row["scenario"] in {"general_spike", "step", "ramp"}:
            return "Alibaba"   # 8주차 신규도 Alibaba로 학습한 모델 사용
        return "Alibaba"

    all_df["dataset"] = all_df.apply(infer_dataset, axis=1)
    return all_df


# -----------------------------------------------------------------------------
# 2) Locust stats 수집
# -----------------------------------------------------------------------------
def load_locust_stats():
    files = glob.glob(f"{RESULTS_ROOT}/**/*_stats.csv", recursive=True)
    rows = []
    for f in files:
        fname = os.path.basename(f)
        # 지원 포맷:
        #   locust_<model>_<scenario>_run<N>_stats.csv          (AWS/기존)
        #   alibaba_<model>_<scenario>_run<N>_stats.csv        (Alibaba 기존)
        #   <model>_<scenario>_run<N>_stats.csv                (8주차 신규, run_week8_batch 출력)
        m = re.match(
            r"(?:alibaba_|locust_)?([a-z]+)_([a-z_]+?)_run(\d+)_stats\.csv$",
            fname,
        )
        if not m:
            continue
        model, scenario, run = m.group(1), m.group(2), int(m.group(3))
        try:
            df = pd.read_csv(f)
            agg = df[df["Name"] == "Aggregated"]
            if agg.empty:
                continue
            r = agg.iloc[0]
            total = float(r.get("Request Count", 0) or 0)
            fails = float(r.get("Failure Count", 0) or 0)
            rows.append({
                "model": model,
                "scenario": scenario,
                "run": run,
                "total_req": int(total),
                "fail": int(fails),
                "err_rate_%": (fails/total*100) if total > 0 else 0.0,
                "median_ms": float(r.get("Median Response Time", 0) or 0),
                "avg_ms":    float(r.get("Average Response Time", 0) or 0),
                "p95_ms":    float(r.get("95%", 0) or 0),
                "p99_ms":    float(r.get("99%", 0) or 0),
                "max_ms":    float(r.get("Max Response Time", 0) or 0),
                "rps":       float(r.get("Requests/s", 0) or 0),
                "__source":  fname,
            })
        except Exception as e:
            print(f"  [skip] {f}: {e}")
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------------
# 3) Run 단위 요약 (lead + locust 결합)
# -----------------------------------------------------------------------------
def build_summary(lead_df, stats_df):
    if lead_df.empty:
        return pd.DataFrame()

    # Lead time per-run aggregation
    out = lead_df[lead_df["event_type"] == "scale_out"].copy()
    lead_run = out.groupby(
        ["dataset", "scenario", "model", "run"]
    )["lead_time_sec"].agg(
        events="count",
        lead_mean="mean",
        lead_std="std",
        lead_median="median",
        lead_p95=lambda x: np.percentile(x, 95) if len(x) > 0 else np.nan,
    ).reset_index()

    merged = lead_run.merge(
        stats_df[["model","scenario","run","total_req","fail","err_rate_%",
                  "p95_ms","p99_ms","rps"]],
        on=["model","scenario","run"], how="left"
    )

    # scenario-model 단위 평균 (논문의 main table)
    agg = merged.groupby(["dataset","scenario","model"]).agg(
        n_runs=("run", "nunique"),
        n_events=("events", "sum"),
        lead_mean_s=("lead_mean", "mean"),
        lead_std_s=("lead_mean", "std"),       # run 간 변동
        lead_pooled_std=("lead_std", "mean"),  # run 내 변동 평균
        p95_mean_ms=("p95_ms", "mean"),
        p99_mean_ms=("p99_ms", "mean"),
        err_mean_pct=("err_rate_%", "mean"),
        req_total=("total_req", "sum"),
    ).round(3).reset_index()
    return merged, agg


# -----------------------------------------------------------------------------
# 4) PPT용 요약표 포맷 (HPA 대비 Δ% 계산)
# -----------------------------------------------------------------------------
def build_ppt_table(agg_df):
    rows = []
    for (ds, sc), grp in agg_df.groupby(["dataset", "scenario"]):
        base = grp[grp["model"] == "hpa"]
        if base.empty:
            continue
        b = base.iloc[0]
        for _, r in grp.iterrows():
            def pct(new, old):
                if pd.isna(old) or old == 0: return np.nan
                return round((old - new) / old * 100, 2)
            rows.append({
                "dataset":   ds,
                "scenario":  sc,
                "model":     r["model"],
                "Lead_mean_s":      r["lead_mean_s"],
                "Lead_std_s":       r["lead_pooled_std"],
                "P95_ms":           r["p95_mean_ms"],
                "P99_ms":           r["p99_mean_ms"],
                "Err_rate_pct":     r["err_mean_pct"],
                "LT_Delta_pct":     pct(r["lead_mean_s"],    b["lead_mean_s"])
                                        if r["model"] != "hpa" else 0.0,
                "P95_Delta_pct":    pct(r["p95_mean_ms"],    b["p95_mean_ms"])
                                        if r["model"] != "hpa" else 0.0,
                "P99_Delta_pct":    pct(r["p99_mean_ms"],    b["p99_mean_ms"])
                                        if r["model"] != "hpa" else 0.0,
            })
    return pd.DataFrame(rows)


# =============================================================================
def main():
    print("="*80)
    print("  Master aggregation — AWS + Alibaba × (spike/periodic/wiki/general_spike/step/ramp)")
    print("="*80)

    lead_df  = load_lead_times()
    stats_df = load_locust_stats()
    print(f"  lead events:  {len(lead_df):>6d}  from {lead_df['__source'].nunique() if not lead_df.empty else 0} files")
    print(f"  locust rows:  {len(stats_df):>6d}  from {stats_df['__source'].nunique() if not stats_df.empty else 0} files")

    if lead_df.empty or stats_df.empty:
        print("  [ERROR] 수집된 데이터 없음 — results/ 아래 CSV 확인")
        return

    run_df, agg_df = build_summary(lead_df, stats_df)
    ppt_df         = build_ppt_table(agg_df)

    # CSV 출력
    run_df.to_csv(OUT_CSV, index=False)
    ppt_df.to_csv(OUT_PPT_CSV, index=False)
    print(f"\n  [saved] {OUT_CSV}     (run-level raw, {len(run_df)} rows)")
    print(f"  [saved] {OUT_PPT_CSV}  (PPT summary, {len(ppt_df)} rows)")

    # XLSX 출력 (다중 시트)
    try:
        with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as xw:
            lead_df.to_excel(xw, sheet_name="lead_raw", index=False)
            stats_df.to_excel(xw, sheet_name="locust_raw", index=False)
            run_df.to_excel(xw, sheet_name="run_level", index=False)
            agg_df.to_excel(xw, sheet_name="agg", index=False)
            ppt_df.to_excel(xw, sheet_name="ppt_table", index=False)
        print(f"  [saved] {OUT_XLSX}  (5 sheets)")
    except Exception as e:
        print(f"  [xlsx skip] {e}")

    # 콘솔 요약
    print("\n  === PPT summary (sorted) ===")
    print(ppt_df.sort_values(["dataset","scenario","model"]).to_string(index=False))


if __name__ == "__main__":
    main()
