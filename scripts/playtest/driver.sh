#!/bin/bash
# Playtest Driver Script
#
# Runs comprehensive LLM playtesting with proper parallelism and state tracking.
# Uses a work directory to track progress and avoid repeating work.
#
# The script reads persona definitions from the scenario files themselves,
# ensuring consistency between scenarios and their AI opponents.
#
# Usage:
#   ./scripts/playtest/driver.sh [--games-per-matchup 3] [--parallel 4] [--work-dir playtest_work]
#
# The script is resumable - it checks the work directory for completed matchups
# and only runs missing ones.

set -euo pipefail

# Default configuration
GAMES_PER_MATCHUP=3
PARALLEL_JOBS=3  # Keep low to avoid OOM
WORK_DIR="playtest_work"
SCENARIOS=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --games-per-matchup)
            GAMES_PER_MATCHUP="$2"
            shift 2
            ;;
        --parallel)
            PARALLEL_JOBS="$2"
            shift 2
            ;;
        --work-dir)
            WORK_DIR="$2"
            shift 2
            ;;
        --scenarios)
            SCENARIOS="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Create work directory structure
mkdir -p "$WORK_DIR"/{jobs,results,logs}

echo "=== Playtest Driver ==="
echo "Games per matchup: $GAMES_PER_MATCHUP"
echo "Parallel jobs: $PARALLEL_JOBS"
echo "Work directory: $WORK_DIR"
echo ""

# Generate jobs from scenario files
generate_jobs() {
    local job_file="$WORK_DIR/jobs/all_jobs.txt"
    > "$job_file"

    for scenario_file in scenarios/*.json; do
        # Skip .gitkeep
        [[ -f "$scenario_file" ]] || continue
        [[ "$scenario_file" != *".gitkeep"* ]] || continue

        # Extract scenario ID (from filename) and personas using python
        local info
        info=$(uv run python -c "
import json
from pathlib import Path
scenario_path = Path('$scenario_file')
# Use filename stem as scenario ID (this is what FileScenarioRepository expects)
sid = scenario_path.stem
with open(scenario_path) as f:
    s = json.load(f)
    p = s.get('personas', {})
    pa = p.get('side_a', {}).get('persona', '')
    pb = p.get('side_b', {}).get('persona', '')
    if sid and pa and pb:
        print(f'{sid}|historical:{pa}|historical:{pb}')
" 2>/dev/null)

        if [[ -z "$info" ]]; then
            echo "Warning: No personas defined for $scenario_file, skipping"
            continue
        fi

        IFS='|' read -r scenario hist_a hist_b <<< "$info"

        # Filter if scenarios specified
        if [[ -n "$SCENARIOS" ]]; then
            if [[ ! "$SCENARIOS" == *"$scenario"* ]]; then
                continue
            fi
        fi

        # Generate 3 matchups for each scenario
        # Matchup 1: Historical A vs Historical B
        echo "$scenario|$hist_a|$hist_b|hist_vs_hist" >> "$job_file"

        # Matchup 2: Smart vs Historical B
        echo "$scenario|smart|$hist_b|smart_vs_hist_b" >> "$job_file"

        # Matchup 3: Historical A vs Smart
        echo "$scenario|$hist_a|smart|hist_a_vs_smart" >> "$job_file"
    done

    local job_count
    job_count=$(wc -l < "$job_file")
    echo "Generated $job_count jobs from scenario files"
}

# Check if a job is complete
is_job_complete() {
    local scenario=$1
    local matchup_type=$2

    local result_file="$WORK_DIR/results/${scenario}__${matchup_type}.json"
    [[ -f "$result_file" ]]
}

# Run a single job
run_job() {
    local job_line=$1
    IFS='|' read -r scenario player_a player_b matchup_type <<< "$job_line"

    local result_file="$WORK_DIR/results/${scenario}__${matchup_type}.json"
    local log_file="$WORK_DIR/logs/${scenario}__${matchup_type}.log"

    # Skip if already complete
    if [[ -f "$result_file" ]]; then
        echo "SKIP: $scenario $matchup_type (already complete)"
        return 0
    fi

    echo "RUN: $scenario $matchup_type ($player_a vs $player_b)"

    if uv run python scripts/playtest/run_matchup.py \
        --scenario "$scenario" \
        --player-a "$player_a" \
        --player-b "$player_b" \
        --games "$GAMES_PER_MATCHUP" \
        --output "$result_file" \
        > "$log_file" 2>&1; then
        echo "DONE: $scenario $matchup_type"
    else
        echo "FAIL: $scenario $matchup_type (see $log_file)"
    fi
}

# Run jobs with controlled parallelism
run_jobs_parallel() {
    local job_file="$WORK_DIR/jobs/all_jobs.txt"
    local pending_file="$WORK_DIR/jobs/pending_jobs.txt"

    # Filter to only pending jobs
    > "$pending_file"
    while IFS= read -r line; do
        IFS='|' read -r scenario player_a player_b matchup_type <<< "$line"
        if ! is_job_complete "$scenario" "$matchup_type"; then
            echo "$line" >> "$pending_file"
        fi
    done < "$job_file"

    local pending_count
    pending_count=$(wc -l < "$pending_file")

    if [[ $pending_count -eq 0 ]]; then
        echo "No pending jobs"
        return 0
    fi

    echo "Running $pending_count jobs with parallelism=$PARALLEL_JOBS"

    # Export function and variables for xargs subshells
    export -f run_job is_job_complete
    export WORK_DIR GAMES_PER_MATCHUP

    # Use xargs for parallel execution with controlled concurrency
    cat "$pending_file" | xargs -P "$PARALLEL_JOBS" -I {} bash -c 'run_job "$@"' _ {}
}

# Main execution
main() {
    generate_jobs

    local job_file="$WORK_DIR/jobs/all_jobs.txt"
    local total_jobs
    total_jobs=$(wc -l < "$job_file")
    local pending_jobs=0
    local completed_jobs=0

    # Count pending/completed
    while IFS= read -r line; do
        IFS='|' read -r scenario player_a player_b matchup_type <<< "$line"
        if is_job_complete "$scenario" "$matchup_type"; then
            completed_jobs=$((completed_jobs + 1))
        else
            pending_jobs=$((pending_jobs + 1))
        fi
    done < "$job_file"

    echo ""
    echo "Jobs: $total_jobs total, $completed_jobs complete, $pending_jobs pending"
    echo ""

    if [[ $pending_jobs -eq 0 ]]; then
        echo "All jobs complete!"
    else
        echo "Running $pending_jobs pending jobs with parallelism=$PARALLEL_JOBS..."
        echo ""
        run_jobs_parallel
    fi

    echo ""
    echo "=== Generating Report ==="
    uv run python scripts/playtest/generate_report.py \
        --work-dir "$WORK_DIR" \
        --output docs/COMPREHENSIVE_PLAYTEST_REPORT.md

    echo ""
    echo "=== Complete ==="
    echo "Results in: $WORK_DIR/results/"
    echo "Report: docs/COMPREHENSIVE_PLAYTEST_REPORT.md"
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main
fi
