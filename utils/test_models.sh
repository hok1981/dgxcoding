#!/bin/bash
# test_models.sh - Test each model one by one, monitor memory, auto-kill if unsafe
#
# Usage:
#   ./utils/test_models.sh              # test all models
#   ./utils/test_models.sh qwen35b      # test one model by profile name
#
# Profile names: qwen35b, qwen122b, deepseek, kimi, mimo

set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────────────
COMPOSE_FILE="$(cd "$(dirname "$0")/.." && pwd)/docker-compose.yml"
RESULTS_FILE="$(cd "$(dirname "$0")/.." && pwd)/model_test_results.txt"

# Memory safety thresholds (MiB)
MEM_WARN_FREE=15360     # 15 GB free  → print warning
MEM_KILL_FREE=8192      #  8 GB free  → kill container immediately

# Startup timeout (seconds) — first run may need to download the model
STARTUP_TIMEOUT=1200    # 20 minutes

# Interval between memory samples (seconds)
MONITOR_INTERVAL=5

# Test prompt
TEST_PROMPT="Write a one-sentence summary of the Pythagorean theorem."

# Models to test: "profile|container|port|name"
ALL_MODELS=(
  "qwen35a3b|qwen35-a3b|8002|Qwen3.5-35B-A3B"
  "qwen122a10b|qwen35-a10b|8003|Qwen3.5-122B-A10B"
  "deepseek|deepseek-v32-speciale|8004|DeepSeek-V3.2-Speciale"
  "kimi|kimi-k25|8005|Kimi-K2.5"
)

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

# ── Helpers ──────────────────────────────────────────────────────────────────
mem_free_mib() {
  awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo
}

mem_total_mib() {
  awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo
}

mem_used_mib() {
  echo $(( $(mem_total_mib) - $(mem_free_mib) ))
}

gpu_mem_used_mib() {
  nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1 || echo "N/A"
}

gpu_mem_total_mib() {
  nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 || echo "N/A"
}

log() { echo -e "${CYAN}[$(date '+%H:%M:%S')]${RESET} $*"; }
warn() { echo -e "${YELLOW}[$(date '+%H:%M:%S')] WARNING:${RESET} $*"; }
error() { echo -e "${RED}[$(date '+%H:%M:%S')] ERROR:${RESET} $*"; }
ok() { echo -e "${GREEN}[$(date '+%H:%M:%S')] OK:${RESET} $*"; }

# ── Safety watchdog (runs as background job) ─────────────────────────────────
watchdog() {
  local container="$1"
  while true; do
    sleep "$MONITOR_INTERVAL"
    local free
    free=$(mem_free_mib)
    if (( free < MEM_KILL_FREE )); then
      error "SAFETY KILL — only ${free} MiB free (threshold: ${MEM_KILL_FREE} MiB)"
      error "Killing container $container NOW"
      docker kill "$container" 2>/dev/null || true
      echo "KILLED_BY_WATCHDOG" > /tmp/watchdog_fired
      return
    elif (( free < MEM_WARN_FREE )); then
      warn "Low memory: ${free} MiB free (warn threshold: ${MEM_WARN_FREE} MiB)"
    fi
  done
}

# ── Test one model ────────────────────────────────────────────────────────────
test_model() {
  local profile="$1" container="$2" port="$3" name="$4"

  echo ""
  echo -e "${BOLD}════════════════════════════════════════════════════════${RESET}"
  echo -e "${BOLD}  Testing: $name${RESET}"
  echo -e "${BOLD}  Profile: $profile  |  Port: $port${RESET}"
  echo -e "${BOLD}════════════════════════════════════════════════════════${RESET}"

  # Make sure no leftover container is running
  docker rm -f "$container" 2>/dev/null || true
  rm -f /tmp/watchdog_fired

  local mem_before
  mem_before=$(mem_used_mib)
  local gpu_before
  gpu_before=$(gpu_mem_used_mib)
  log "Memory before start: ${mem_before} MiB used, $(mem_free_mib) MiB free"

  # Start the container
  log "Starting container via profile '$profile'..."
  docker compose -f "$COMPOSE_FILE" --profile "$profile" up -d "$container"

  # Launch watchdog
  watchdog "$container" &
  local watchdog_pid=$!

  # Wait for API to become ready
  log "Waiting for API to be ready (timeout: ${STARTUP_TIMEOUT}s)..."
  local elapsed=0
  local ready=false
  while (( elapsed < STARTUP_TIMEOUT )); do
    if [[ -f /tmp/watchdog_fired ]]; then
      error "Watchdog killed the container during startup!"
      kill "$watchdog_pid" 2>/dev/null || true
      record_result "$name" "KILLED_BY_WATCHDOG" "$mem_before" "N/A" "N/A" "N/A"
      return
    fi
    if curl -sf "http://localhost:${port}/v1/models" > /dev/null 2>&1; then
      ready=true
      break
    fi
    sleep 10
    elapsed=$(( elapsed + 10 ))
    log "  Still waiting... (${elapsed}s elapsed, $(mem_free_mib) MiB free)"
  done

  if [[ "$ready" != "true" ]]; then
    error "Timed out waiting for $name to become ready"
    kill "$watchdog_pid" 2>/dev/null || true
    docker logs --tail 20 "$container" 2>&1 | sed 's/^/    /'
    docker rm -f "$container" 2>/dev/null || true
    record_result "$name" "TIMEOUT" "$mem_before" "N/A" "N/A" "N/A"
    return
  fi

  ok "API is ready after ${elapsed}s"

  # Sample memory at steady state
  local mem_loaded
  mem_loaded=$(mem_used_mib)
  local gpu_loaded
  gpu_loaded=$(gpu_mem_used_mib)
  local mem_delta=$(( mem_loaded - mem_before ))
  log "Memory after load: ${mem_loaded} MiB used (+${mem_delta} MiB),  $(mem_free_mib) MiB free"
  log "GPU memory: ${gpu_loaded} MiB / $(gpu_mem_total_mib) MiB"

  # Run test inference
  log "Running test inference..."
  local model_id
  model_id=$(curl -sf "http://localhost:${port}/v1/models" | python3 -c "import sys,json; print(json.load(sys.stdin)['data'][0]['id'])" 2>/dev/null || echo "unknown")

  local response
  local infer_ok=false
  if response=$(curl -sf "http://localhost:${port}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "{
      \"model\": \"${model_id}\",
      \"messages\": [{\"role\": \"user\", \"content\": \"${TEST_PROMPT}\"}],
      \"max_tokens\": 100,
      \"temperature\": 0
    }" 2>&1); then
    local answer
    answer=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'])" 2>/dev/null || echo "(parse error)")
    ok "Inference succeeded: $answer"
    infer_ok=true
  else
    error "Inference failed: $response"
  fi

  # Peak memory after inference
  local mem_peak
  mem_peak=$(mem_used_mib)
  local gpu_peak
  gpu_peak=$(gpu_mem_used_mib)

  # Stop watchdog and container
  kill "$watchdog_pid" 2>/dev/null || true
  log "Stopping container..."
  docker compose -f "$COMPOSE_FILE" --profile "$profile" down "$container" 2>/dev/null || \
    docker rm -f "$container" 2>/dev/null || true

  # Wait for memory to free before next model
  log "Waiting for memory to release..."
  local wait=0
  while (( $(mem_used_mib) > mem_before + 2048 && wait < 60 )); do
    sleep 5; wait=$(( wait + 5 ))
  done
  log "Memory after stop: $(mem_used_mib) MiB used, $(mem_free_mib) MiB free"

  local status="OK"
  [[ "$infer_ok" != "true" ]] && status="LOADED_NO_INFER"
  record_result "$name" "$status" "$mem_before" "$mem_loaded" "$mem_peak" "$gpu_peak"
}

record_result() {
  local name="$1" status="$2" mem_before="$3" mem_loaded="$4" mem_peak="$5" gpu_peak="$6"
  local delta="N/A"
  [[ "$mem_loaded" != "N/A" && "$mem_before" != "N/A" ]] && delta=$(( mem_loaded - mem_before ))

  printf "%-30s  %-20s  before=%6s MiB  loaded=%6s MiB  delta=%6s MiB  gpu_peak=%6s MiB\n" \
    "$name" "$status" "$mem_before" "$mem_loaded" "$delta" "$gpu_peak" \
    | tee -a "$RESULTS_FILE"
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
  echo -e "${BOLD}Model Memory Test Suite${RESET}"
  echo "Results will be saved to: $RESULTS_FILE"
  echo ""
  echo "Safety thresholds:"
  echo "  Warn at:  $(( MEM_WARN_FREE / 1024 )) GB free"
  echo "  Kill at:  $(( MEM_KILL_FREE / 1024 )) GB free"
  echo ""
  echo "System: $(mem_total_mib) MiB total, $(mem_free_mib) MiB free at start"
  echo "GPU:    $(gpu_mem_total_mib) MiB total, $(gpu_mem_used_mib) MiB used at start"
  echo ""

  # Header in results file
  {
    echo "========================================"
    echo "Model test run: $(date)"
    echo "System RAM: $(mem_total_mib) MiB total"
    echo "GPU RAM:    $(gpu_mem_total_mib) MiB total"
    echo "========================================"
  } >> "$RESULTS_FILE"

  # Determine which models to test
  local targets=()
  if [[ $# -gt 0 ]]; then
    # Filter to requested profiles
    for entry in "${ALL_MODELS[@]}"; do
      local profile="${entry%%|*}"
      for arg in "$@"; do
        [[ "$profile" == "$arg" ]] && targets+=("$entry") && break
      done
    done
  else
    targets=("${ALL_MODELS[@]}")
  fi

  if [[ ${#targets[@]} -eq 0 ]]; then
    error "No matching models found. Valid profile names: qwen35b qwen122b deepseek kimi mimo"
    exit 1
  fi

  for entry in "${targets[@]}"; do
    IFS='|' read -r profile container port name <<< "$entry"
    test_model "$profile" "$container" "$port" "$name"
  done

  echo ""
  echo -e "${BOLD}════════════════ RESULTS SUMMARY ════════════════${RESET}"
  grep -v "^==\|^Model test\|^System\|^GPU" "$RESULTS_FILE" | tail -$(( ${#targets[@]} + 2 ))
  echo ""
  echo "Full results saved to: $RESULTS_FILE"
}

main "$@"
