# week8_helpers.sh v2 — 재실험용, 초기 상태 일관성 보장
#
# 사용법:
#   source scripts/week8_helpers.sh
#   export TICKETBENCH_HOST=http://<cluster-lb-ip>
#
#   # 개별 run
#   run_one hpa general_spike 1
#
#   # 시나리오 전체 (12 run 자동 + 모델 전환 프롬프트 3회)
#   run_scenario general_spike
#   run_scenario step
#   run_scenario ramp
#
#   # 전체 36 run
#   run_all
#
# v2 변경점:
#   - wait_for_pods_settle(): 다음 run 시작 전 파드가 1~2개로 수렴할 때까지 대기
#   - run_scenario(): 시나리오 시작 전 강제 완전 리셋
#   - verify_run(): run 직후 결과 CSV에 scale_out 이벤트 있는지 검증
#   - 모든 run을 매 시작 전 파드 개수 확인 → 비정상이면 강제 리셋

# ----------------------------------------------------------------------------
# 파드 완전 수렴 대기
# ----------------------------------------------------------------------------
wait_for_pods_settle() {
    local target="${1:-2}"    # 기본 2개 이하로 수렴 대기
    local max_wait="${2:-180}"
    local waited=0
    echo "  ⏳ 파드 수렴 대기 (target ≤ ${target}, max ${max_wait}s)"
    while [ $waited -lt $max_wait ]; do
        local n=$(kubectl get po -l app=ticketbench --no-headers 2>/dev/null | grep -c "Running" || echo 0)
        if [ "$n" -le "$target" ]; then
            echo "  ✓ 파드 ${n}개로 수렴 완료 (${waited}s 소요)"
            return 0
        fi
        echo "    ...현재 ${n}개, ${waited}s 경과"
        sleep 15
        waited=$((waited + 15))
    done
    echo "  ⚠ ${max_wait}s 내 수렴 실패 — 강제 리셋"
    kubectl scale deployment/ticketbench-deploy --replicas=1 2>/dev/null
    kubectl rollout status deployment/ticketbench-deploy --timeout=60s 2>/dev/null
    return 1
}

# ----------------------------------------------------------------------------
# 강제 완전 리셋 (시나리오 시작 전, 문제 상황 복구)
# ----------------------------------------------------------------------------
hard_reset() {
    echo "🧹 클러스터 완전 초기화"
    ./scripts/switch_scaler.sh cleanup 2>&1 | tail -5
    kubectl scale deployment/ticketbench-deploy --replicas=1 2>/dev/null
    kubectl rollout status deployment/ticketbench-deploy --timeout=120s 2>/dev/null
    sleep 10
    wait_for_pods_settle 1 120
    echo "  ✓ 리셋 완료 (현재 $(kubectl get po -l app=ticketbench --no-headers 2>/dev/null | wc -l)개 파드)"
}

# ----------------------------------------------------------------------------
# 단일 run 실행
# ----------------------------------------------------------------------------
run_one() {
    local model="$1" scenario="$2" run="$3"
    
    # 시나리오별 설정
    local locfile dur
    case "$scenario" in
        general_spike) locfile="loadtest/locustfile_general_spike.py"; dur=330 ;;
        step)          locfile="loadtest/locustfile_step.py";          dur=490 ;;
        ramp)          locfile="loadtest/locustfile_ramp.py";          dur=490 ;;
        *) echo "[ERROR] unknown scenario: $scenario"; return 1 ;;
    esac
    
    local tag="${model}_${scenario}_run${run}"
    local stats_prefix="results/week8/${tag}"
    local tracker_log="logs/week8/leadtime_${tag}.log"
    local lead_csv="results/lead_time_${tag}.csv"
    
    mkdir -p results/week8 logs/week8
    
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "▶ [${tag}] $(date +'%H:%M:%S') (duration ${dur}s)"
    echo "═══════════════════════════════════════════════════════════════"
    
    # ── 초기 상태 검증 ──
    local current_pods=$(kubectl get po -l app=ticketbench --no-headers 2>/dev/null | grep -c "Running" || echo 0)
    echo "  현재 파드: ${current_pods}개"
    if [ "$current_pods" -gt 2 ]; then
        echo "  ⚠ 파드가 ${current_pods}개 → 강제 수렴 대기"
        wait_for_pods_settle 2 120
    fi
    
    # ── 스케일러 전환 ──
    if [ "${model}" = "hpa" ]; then
        ./scripts/switch_scaler.sh hpa
    else
        ./scripts/switch_scaler.sh ml
        echo ""
        echo "  🔄 AI 서버 상태 확인:"
        echo "     터미널 A에서 MODEL_TYPE=${model} 로 로드되어 있어야 함"
        echo "     (모델 바뀌었으면 Ctrl+C → MODEL_TYPE=${model} uvicorn ... 재실행)"
        echo "     (같은 모델이면 그냥 Enter)"
        echo ""
        read -p "  ▶ 확인 후 Enter: " _
    fi
    
    # ── 파드 초기값 2개 보장 ──
    wait_for_pods_settle 2 60
    
    # ── 트래커 백그라운드 ──
    python3 scripts/lead_time_tracker_v2.py "${model}" "${scenario}" "${run}" \
        > "${tracker_log}" 2>&1 &
    local trk_pid=$!
    sleep 2
    
    # ── Locust 실행 ──
    timeout $((dur + 30)) locust -f "${locfile}" \
        --host="${TICKETBENCH_HOST}" \
        --autostart --autoquit 0 \
        --run-time "${dur}s" \
        --csv="${stats_prefix}" \
        --only-summary
    local locust_rc=$?
    
    # ── 트래커 종료 ──
    kill -SIGINT ${trk_pid} 2>/dev/null
    sleep 2
    kill -9 ${trk_pid} 2>/dev/null
    wait ${trk_pid} 2>/dev/null
    
    # ── 결과 검증 ──
    if [ ${locust_rc} -ne 0 ] && [ ${locust_rc} -ne 124 ]; then
        echo "  ⚠ locust exit code ${locust_rc}"
    fi
    
    if [ -f "${lead_csv}" ]; then
        local n_events=$(grep -c ",scale_out," "${lead_csv}" 2>/dev/null || echo 0)
        local init_pod=$(awk -F, 'NR==2 {print $6}' "${lead_csv}")
        echo "  ✅ ${tag}: ${n_events} scale_out events, init_pod=${init_pod}"
        if [ "${init_pod}" != "2" ] && [ "${init_pod}" != "1" ]; then
            echo "  ⚠ 초기 파드가 ${init_pod}개 — 이 run은 재실험 대상일 수 있음"
        fi
    else
        echo "  ⚠ ${lead_csv} 생성 안 됨"
    fi
    
    # ── 쿨다운 + 수렴 대기 ──
    echo "  ⏸ cooldown 120s + 파드 수렴 대기"
    sleep 120
    wait_for_pods_settle 2 120
    echo ""
}

# ----------------------------------------------------------------------------
# 시나리오 전체 (12 run 자동)
# ----------------------------------------------------------------------------
run_scenario() {
    local scenario="$1"
    
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  🎬 SCENARIO: ${scenario}"
    echo "║  시작: $(date)"
    echo "╚══════════════════════════════════════════════════════════════╝"
    
    hard_reset    # 시나리오 시작 전 완전 리셋
    
    for model in hpa lstm gru ensemble; do
        for run in 1 2 3; do
            run_one "$model" "$scenario" "$run" || {
                echo "❌ ${model}_${scenario}_run${run} 실패 — 중단"
                return 1
            }
        done
    done
    
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  ✅ SCENARIO '${scenario}' 완료: $(date)"
    echo "╚══════════════════════════════════════════════════════════════╝"
}

# ----------------------------------------------------------------------------
# 특정 run부터 이어서 실행
# ----------------------------------------------------------------------------
run_scenario_from() {
    local scenario="$1" start_model="$2" start_run="$3"
    local reached=0
    
    hard_reset
    
    for model in hpa lstm gru ensemble; do
        for run in 1 2 3; do
            if [ "$reached" = "0" ] && [ "$model" = "$start_model" ] && [ "$run" = "$start_run" ]; then
                reached=1
            fi
            if [ "$reached" = "1" ]; then
                run_one "$model" "$scenario" "$run" || return 1
            fi
        done
    done
}

# ----------------------------------------------------------------------------
# 전체 36 run
# ----------------------------------------------------------------------------
run_all() {
    echo "🚀 전체 36 run 시작: $(date)"
    for sc in general_spike step ramp; do
        run_scenario "$sc" || { echo "❌ ${sc} 실패"; return 1; }
    done
    echo "🎉 전체 완료: $(date)"
}

# ----------------------------------------------------------------------------
# 상태 확인 유틸
# ----------------------------------------------------------------------------
week8_status() {
    echo "═══ 현재 상태 ═══"
    echo ""
    echo "파드:"
    kubectl get po -l app=ticketbench 2>/dev/null | head -10
    echo ""
    echo "오토스케일러:"
    kubectl get hpa,scaledobject 2>/dev/null
    echo ""
    echo "완료된 run (results/lead_time_*.csv):"
    local count=$(ls results/lead_time_*_run*.csv 2>/dev/null | wc -l)
    echo "  총 ${count}개 파일"
    ls results/lead_time_*_run*.csv 2>/dev/null | sed 's|.*lead_time_||; s|.csv$||' | sort
}

echo "✓ week8_helpers v2 로드 완료"
echo "  명령:  run_one / run_scenario / run_scenario_from / run_all / week8_status"
echo "  필수:  export TICKETBENCH_HOST=http://<cluster-lb-ip>"