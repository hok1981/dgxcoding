#!/bin/bash
# test_models.sh - Test each model one by one, monitor memory, auto-kill if unsafe
#
# Usage:
#   ./utils/test_models.sh              # test all models
#   ./utils/test_models.sh qwen3a3b     # test one model by profile name
#
# Profile names: qwen3a3b, qwen332b, phi4, llama3370b, nemotron120b, gptoss120b, nemotronnano, parakeet, piper

set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$(cd "$(dirname "$0")/.." && pwd)/docker-compose.yml"
RESULTS_FILE="$(cd "$(dirname "$0")/.." && pwd)/model_test_results.txt"
PERF_SCRIPT="$SCRIPT_DIR/test_performance.py"

# Performance test settings for LLM models
PERF_RUNS=3        # iterations per model
PERF_TOKENS=2048   # max completion tokens per run (~1-2 min per model at 40 tok/s)

# Memory safety thresholds (MiB)
MEM_WARN_FREE=15360     # 15 GB free  → print warning
MEM_KILL_FREE=1024      #  1 GB free  → kill container immediately (swap is acceptable)

# Startup timeout (seconds) — first run may need to download the model
STARTUP_TIMEOUT=2400    # 40 minutes (large models like DeepSeek/Nemotron need extra time)

# Interval between memory samples (seconds)
MONITOR_INTERVAL=5

# Test prompt — /no_think suppresses reasoning traces on Qwen3/DeepSeek
TEST_PROMPT="Write a one-sentence summary of the Pythagorean theorem. /no_think"

# Models to test: "profile|container|port|name|type"
# type: openai (default) = LLM with /v1/chat/completions
#        nim-stt          = NVIDIA NIM STT, health at /v1/health/ready, test via /v1/audio/transcriptions
#        wyoming-tts      = Wyoming TTS (TCP), memory-only test
ALL_MODELS=(
  "qwen3a3b|qwen3-a3b|8002|Qwen3-30B-A3B-NVFP4|openai"
  "qwen332b|qwen3-32b|8003|Qwen3-32B-NVFP4|openai"
  "phi4|phi4-reasoning|8004|Phi-4-reasoning-plus-NVFP4|openai"
  "llama3370b|llama33-70b|8005|Llama-3.3-70B-Instruct-NVFP4|openai"
  # "nemotron120b|nemotron-120b|8007|Nemotron-3-Super-120B-A12B-NVFP4|openai"  # Weight footprint ~110 GiB (NVFP4 + scales) — consistently OOMs on 119.7 GiB regardless of free_gpu_memory_fraction (0.90/0.50/0.20 all failed)
  # "kimi|kimi-k25|8008|Kimi-K2.5|openai"  # TRT-LLM 1.3.0rc7 bug: inputs_quant_config is None
  "gptoss120b|gpt-oss-120b|8006|gpt-oss-120b|openai"
  "nemotronnano|nemotron-nano|8009|Nemotron-3-Nano-30B-A3B-NVFP4|openai"
  # "qwen3535b|qwen35-35b|8010|Qwen3.5-35B-A3B-FP8|openai"  # qwen3_5_moe arch not in transformers==4.57.1
  "parakeet|parakeet-ctc|9000|Parakeet-1.1B-CTC|nim-stt"
  "piper|wyoming-piper|10200|Wyoming-Piper-TTS|wyoming-tts"
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

mib_to_gib() {
  # Print MiB value as GiB with one decimal, or return input unchanged if not numeric
  local val="$1"
  [[ "$val" =~ ^[0-9]+$ ]] && python3 -c "print(f'{${val}/1024:.1f}')" || echo "$val"
}

log()   { echo -e "${CYAN}[$(date '+%H:%M:%S')]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[$(date '+%H:%M:%S')] WARNING:${RESET} $*"; }
error() { echo -e "${RED}[$(date '+%H:%M:%S')] ERROR:${RESET} $*"; }
ok()    { echo -e "${GREEN}[$(date '+%H:%M:%S')] OK:${RESET} $*"; }

# ── Safety watchdog (runs as background job) ─────────────────────────────────
# Tracks minimum free RAM seen. Writes mem_used_at_kill to /tmp/watchdog_fired.
watchdog() {
  local container="$1"
  local min_free_file="/tmp/wdog_minfree_${container}"
  local cur_min
  cur_min=$(mem_free_mib)   # seed with real value so fast-starting containers report correctly
  echo "$cur_min" > "$min_free_file"

  while true; do
    sleep "$MONITOR_INTERVAL"
    local free used
    free=$(mem_free_mib)
    used=$(mem_used_mib)

    # Track minimum free RAM seen
    if (( free < cur_min )); then
      cur_min=$free
      echo "$cur_min" > "$min_free_file"
    fi

    if (( free < MEM_KILL_FREE )); then
      error "SAFETY KILL — only ${free} MiB ($(mib_to_gib $free) GiB) free  [threshold: $(mib_to_gib $MEM_KILL_FREE) GiB]"
      error "RAM in use at kill: ${used} MiB ($(mib_to_gib $used) GiB)  |  min free seen: ${cur_min} MiB"
      docker kill "$container" 2>/dev/null || true
      echo "$used" > /tmp/watchdog_fired   # store mem_used so caller can compute delta
      return
    elif (( free < MEM_WARN_FREE )); then
      warn "Low memory: ${free} MiB ($(mib_to_gib $free) GiB) free  [warn: $(mib_to_gib $MEM_WARN_FREE) GiB, kill: $(mib_to_gib $MEM_KILL_FREE) GiB]"
    fi
  done
}

# ── Test one model ────────────────────────────────────────────────────────────
test_model() {
  local profile="$1" container="$2" port="$3" name="$4" api_type="${5:-openai}"

  echo ""
  echo -e "${BOLD}════════════════════════════════════════════════════════${RESET}"
  echo -e "${BOLD}  Testing: $name${RESET}"
  echo -e "${BOLD}  Profile: $profile  |  Port: $port${RESET}"
  echo -e "${BOLD}════════════════════════════════════════════════════════${RESET}"

  # Make sure no leftover container is running
  docker rm -f "$container" 2>/dev/null || true
  rm -f /tmp/watchdog_fired "/tmp/wdog_minfree_${container}"

  local mem_before mem_free_before
  mem_before=$(mem_used_mib)
  mem_free_before=$(mem_free_mib)
  log "Memory before start: $(mib_to_gib $mem_before) GiB used, $(mib_to_gib $mem_free_before) GiB free (of $(mib_to_gib $(mem_total_mib)) GiB total)"

  # Start the container
  log "Starting container via profile '$profile'..."
  docker compose -f "$COMPOSE_FILE" --profile "$profile" up -d "$container"

  # Launch watchdog
  watchdog "$container" &
  local watchdog_pid=$!

  # Wait for API to become ready, logging memory growth every 30s
  log "Waiting for API to be ready (timeout: ${STARTUP_TIMEOUT}s)..."
  local elapsed=0
  local ready=false
  local last_log_elapsed=-30   # force a log on first iteration

  while (( elapsed < STARTUP_TIMEOUT )); do
    if [[ -f /tmp/watchdog_fired ]]; then
      local killed_mem_used killed_delta min_free_seen
      killed_mem_used=$(cat /tmp/watchdog_fired 2>/dev/null || echo "$mem_before")
      killed_delta=$(( killed_mem_used - mem_before ))
      min_free_seen=$(cat "/tmp/wdog_minfree_${container}" 2>/dev/null || echo "N/A")
      error "Watchdog killed container at ${elapsed}s!"
      error "  RAM consumed: +$(mib_to_gib $killed_delta) GiB  |  total in use: $(mib_to_gib $killed_mem_used) GiB  |  min free: $(mib_to_gib $min_free_seen) GiB"
      error "  System has $(mib_to_gib $(mem_total_mib)) GiB total — model needed > $(mib_to_gib $killed_delta) GiB"
      kill "$watchdog_pid" 2>/dev/null || true
      record_result "$name" "KILLED_BY_WATCHDOG" "$mem_before" "$killed_mem_used" "$killed_mem_used" "N/A" "N/A" "$min_free_seen"
      return
    fi

    local api_ready=false
    case "$api_type" in
      openai)
        curl -sf "http://localhost:${port}/v1/models" > /dev/null 2>&1 && api_ready=true ;;
      nim-stt)
        curl -sf "http://localhost:${port}/v1/health/ready" > /dev/null 2>&1 && api_ready=true ;;
      wyoming-tts)
        timeout 2 bash -c "(echo '' > /dev/tcp/localhost/${port})" 2>/dev/null && api_ready=true ;;
    esac
    if [[ "$api_ready" == "true" ]]; then
      ready=true
      break
    fi

    sleep 10
    elapsed=$(( elapsed + 10 ))

    # Log memory progress every 30s
    if (( elapsed - last_log_elapsed >= 30 )); then
      local cur_used cur_delta cur_free
      cur_used=$(mem_used_mib)
      cur_delta=$(( cur_used - mem_before ))
      cur_free=$(mem_free_mib)
      log "  ${elapsed}s — RAM: +$(mib_to_gib $cur_delta) GiB loaded, $(mib_to_gib $cur_free) GiB free remaining"
      last_log_elapsed=$elapsed
    fi
  done

  if [[ "$ready" != "true" ]]; then
    local min_free_seen
    min_free_seen=$(cat "/tmp/wdog_minfree_${container}" 2>/dev/null || echo "N/A")
    error "Timed out waiting for $name to become ready (${STARTUP_TIMEOUT}s)"
    log "  Min free RAM seen during startup: $(mib_to_gib $min_free_seen) GiB"
    kill "$watchdog_pid" 2>/dev/null || true
    docker logs --tail 20 "$container" 2>&1 | sed 's/^/    /'
    docker rm -f "$container" 2>/dev/null || true
    record_result "$name" "TIMEOUT" "$mem_before" "N/A" "N/A" "N/A" "N/A" "$min_free_seen"
    return
  fi

  ok "API is ready after ${elapsed}s"

  # Sample memory at steady state
  local mem_loaded gpu_loaded mem_delta min_free_seen
  mem_loaded=$(mem_used_mib)
  gpu_loaded=$(gpu_mem_used_mib)
  mem_delta=$(( mem_loaded - mem_before ))
  min_free_seen=$(cat "/tmp/wdog_minfree_${container}" 2>/dev/null || echo "N/A")
  log "Loaded: +$(mib_to_gib $mem_delta) GiB RAM  |  GPU: ${gpu_loaded} MiB / $(gpu_mem_total_mib) MiB  |  min free: $(mib_to_gib $min_free_seen) GiB"

  # Run test inference (varies by api_type)
  log "Running test inference..."
  local infer_ok=false toks_per_sec="N/A"

  if [[ "$api_type" == "openai" ]]; then
    log "Running performance benchmark (${PERF_RUNS} runs × ${PERF_TOKENS} tokens)..."
    local perf_json
    if perf_json=$(python3 "$PERF_SCRIPT" "$port" \
        --runs "$PERF_RUNS" --tokens "$PERF_TOKENS" --json 2>&1 \
      | tail -1); then
      local ttft decode_tps e2e_tps ctokens
      ttft=$(echo    "$perf_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{d[\"ttft_s\"]:.2f}±{d[\"ttft_stdev\"]:.2f}')"   2>/dev/null || echo "N/A")
      decode_tps=$(echo "$perf_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{d[\"decode_tps\"]:.1f}±{d[\"decode_stdev\"]:.1f}')" 2>/dev/null || echo "N/A")
      e2e_tps=$(echo "$perf_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{d[\"e2e_tps\"]:.1f}')"    2>/dev/null || echo "N/A")
      ctokens=$(echo "$perf_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(int(d['completion_tokens']))" 2>/dev/null || echo "0")
      toks_per_sec=$(echo "$perf_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['decode_tps'])" 2>/dev/null || echo "N/A")
      ok "TTFT: ${ttft}s  |  decode: ${decode_tps} tok/s  |  e2e: ${e2e_tps} tok/s  |  ~${ctokens} tokens/run"
      echo "PERF [${name}]: TTFT=${ttft}s decode=${decode_tps} tok/s e2e=${e2e_tps} tok/s tokens=${ctokens}" >> "$RESULTS_FILE"
      infer_ok=true
    else
      error "Performance test failed"
    fi

  elif [[ "$api_type" == "nim-stt" ]]; then
    # Generate 1s of 440Hz sine wave @ 16kHz — VAD detects tone as audio (silence is rejected)
    python3 -c "
import wave, io, math, struct
buf = io.BytesIO()
with wave.open(buf, 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    frames = [struct.pack('<h', int(16000 * math.sin(2*math.pi*440*i/16000))) for i in range(16000)]
    w.writeframes(b''.join(frames))
buf.seek(0)
with open('/tmp/test_audio.wav', 'wb') as f:
    f.write(buf.read())" 2>/dev/null
    # POST audio: no model field, just language — matches VideoTranscript's working HTTP fallback
    local http_code asr_response
    asr_response=$(curl -s --max-time 60 -w "\n__HTTP_CODE__%{http_code}" \
      -X POST "http://localhost:${port}/v1/audio/transcriptions" \
      -F "file=@/tmp/test_audio.wav;type=audio/wav" \
      -F "language=en-US" 2>&1)
    http_code=$(echo "$asr_response" | grep -o '__HTTP_CODE__[0-9]*' | grep -o '[0-9]*')
    asr_response=$(echo "$asr_response" | sed 's/__HTTP_CODE__[0-9]*//')
    if [[ "$http_code" == "200" ]]; then
      local transcript
      transcript=$(echo "$asr_response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('text','(empty)'))" 2>/dev/null || echo "(empty)")
      ok "Transcription succeeded (HTTP 200): '${transcript}'"
      echo "RESPONSE [${name}]: tone → '${transcript}'" >> "$RESULTS_FILE"
      infer_ok=true
    else
      error "Transcription failed (HTTP ${http_code}): ${asr_response}"
      log "  Tip: check /v1/models output above for correct model name"
      echo "RESPONSE [${name}]: FAILED HTTP ${http_code}: ${asr_response}" >> "$RESULTS_FILE"
    fi

  elif [[ "$api_type" == "wyoming-tts" ]]; then
    ok "TTS service ready on port ${port} (Wyoming protocol — CPU only, no HTTP test)"
    echo "RESPONSE [${name}]: Wyoming TTS ready" >> "$RESULTS_FILE"
    infer_ok=true
    toks_per_sec="CPU"
  fi

  # Peak memory after inference
  local mem_peak gpu_peak
  mem_peak=$(mem_used_mib)
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
  log "Memory after stop: $(mib_to_gib $(mem_used_mib)) GiB used, $(mib_to_gib $(mem_free_mib)) GiB free"

  local status="OK"
  [[ "$infer_ok" != "true" ]] && status="LOADED_NO_INFER"
  record_result "$name" "$status" "$mem_before" "$mem_loaded" "$mem_peak" "$gpu_peak" "$toks_per_sec" "$min_free_seen"
}

# ── Record result as TSV (tab-separated) for clean table parsing ──────────────
# Fields: name, status, ram_delta_mib, ram_peak_mib, gpu_peak_mib, toks_per_sec, min_free_mib
record_result() {
  local name="$1" status="$2" mem_before="$3" mem_loaded="$4" mem_peak="$5" \
        gpu_peak="$6" toks_per_sec="${7:-N/A}" min_free="${8:-N/A}"
  local delta="N/A"
  [[ "$mem_loaded" != "N/A" && "$mem_before" =~ ^[0-9]+$ && "$mem_loaded" =~ ^[0-9]+$ ]] \
    && delta=$(( mem_loaded - mem_before ))

  printf "RESULT\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "$name" "$status" "$delta" "$mem_peak" "$gpu_peak" "$toks_per_sec" "$min_free" \
    >> "$RESULTS_FILE"
}

# ── Print summary table ───────────────────────────────────────────────────────
print_summary() {
  local count="$1"
  local sep="╠══════════════════════════════════╪══════════════════════╪═════════╪═════════╪═════════╪════════╣"
  local top="╔══════════════════════════════════╤══════════════════════╤═════════╤═════════╤═════════╤════════╗"
  local bot="╚══════════════════════════════════╧══════════════════════╧═════════╧═════════╧═════════╧════════╝"
  local hdr="╠══════════════════════════════════╪══════════════════════╪═════════╪═════════╪═════════╪════════╣"

  echo ""
  echo -e "${BOLD}${top}${RESET}"
  printf "${BOLD}║ %-32s │ %-20s │ %7s │ %7s │ %7s │ %6s ║${RESET}\n" \
    "Model" "Status" "RAM +GiB" "Peak GiB" "Free GiB" "Perf"
  echo -e "${BOLD}${hdr}${RESET}"

  while IFS=$'\t' read -r _ name status delta peak _gpu toks minfree; do
    local delta_g peak_g free_g
    delta_g=$(mib_to_gib "$delta")
    peak_g=$(mib_to_gib "$peak")
    free_g=$(mib_to_gib "$minfree")
    # Truncate name to 32 chars
    name="${name:0:32}"
    printf "║ %-32s │ %-20s │ %7s │ %7s │ %7s │ %6s ║\n" \
      "$name" "$status" "$delta_g" "$peak_g" "$free_g" "$toks"
  done < <(grep "^RESULT" "$RESULTS_FILE" | tail -"$count")

  echo -e "${BOLD}${bot}${RESET}"
  echo ""
  echo "  RAM +GiB  = memory consumed by the model at steady state"
  echo "  Peak GiB  = highest RAM usage (includes inference spike)"
  echo "  Free GiB  = minimum free RAM seen (kill threshold: $(mib_to_gib $MEM_KILL_FREE) GiB)"
  echo "  Perf      = decode tok/s, mean of ${PERF_RUNS} runs at ${PERF_TOKENS} tokens (LLMs) | CPU/N/A for STT/TTS"
  echo ""
  echo "Full results (with responses) saved to: $RESULTS_FILE"
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
  echo -e "${BOLD}Model Memory Test Suite${RESET}"
  echo "Results will be saved to: $RESULTS_FILE"
  echo ""
  echo "Safety thresholds:  warn < $(mib_to_gib $MEM_WARN_FREE) GiB free  |  kill < $(mib_to_gib $MEM_KILL_FREE) GiB free"
  echo "System: $(mib_to_gib $(mem_total_mib)) GiB total, $(mib_to_gib $(mem_free_mib)) GiB free at start"
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

  # List mode
  if [[ "${1:-}" == "--list" ]]; then
    echo "Available models (pass profile name to test a single model):"
    echo ""
    printf "  %-16s  %-10s  %-40s  %s\n" "PROFILE" "TYPE" "MODEL" "PORT"
    printf "  %-16s  %-10s  %-40s  %s\n" "-------" "----" "-----" "----"
    for entry in "${ALL_MODELS[@]}"; do
      IFS='|' read -r profile _container port name api_type <<< "$entry"
      printf "  %-16s  %-10s  %-40s  %s\n" "$profile" "${api_type:-openai}" "$name" "$port"
    done
    echo ""
    echo "Usage:"
    echo "  ./utils/test_models.sh               # test all models"
    echo "  ./utils/test_models.sh qwen3a3b      # test one model"
    echo "  ./utils/test_models.sh qwen3a3b phi4 # test multiple models"
    exit 0
  fi

  # Determine which models to test
  local targets=()
  if [[ $# -gt 0 ]]; then
    for entry in "${ALL_MODELS[@]}"; do
      IFS='|' read -r profile _ _ _ _ <<< "$entry"
      for arg in "$@"; do
        [[ "$profile" == "$arg" ]] && targets+=("$entry") && break
      done
    done
  else
    targets=("${ALL_MODELS[@]}")
  fi

  if [[ ${#targets[@]} -eq 0 ]]; then
    error "No matching models found. Run --list to see valid profile names."
    exit 1
  fi

  for entry in "${targets[@]}"; do
    IFS='|' read -r profile container port name api_type <<< "$entry"
    test_model "$profile" "$container" "$port" "$name" "${api_type:-openai}"
  done

  print_summary "${#targets[@]}"
}

main "$@"
