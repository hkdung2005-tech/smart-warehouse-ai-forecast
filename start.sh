#!/usr/bin/env bash
set -Eeuo pipefail

pids=()

start_process() {
    local directory=$1
    shift
    (cd "/app/$directory" && exec "$@") &
    pids+=("$!")
}

stop_processes() {
    local pid
    for pid in "${pids[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    for pid in "${pids[@]}"; do
        wait "$pid" 2>/dev/null || true
    done
}

start_process api uvicorn main:app --host 0.0.0.0 --port 8000
start_process . python -m worker
start_process gemini uvicorn mock_server:app --host 0.0.0.0 --port 9000

trap 'stop_processes; exit 130' INT
trap 'stop_processes; exit 143' TERM

set +e
wait -n "${pids[@]}"
status=$?
set -e

stop_processes
exit "$status"
