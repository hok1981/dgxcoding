#!/bin/bash
set -euo pipefail

if [ -z "${MODEL_HANDLE:-}" ]; then
  echo "ERROR: MODEL_HANDLE environment variable is not set"
  exit 1
fi

if [ -n "${PRE_INSTALL:-}" ]; then
  echo "Installing: $PRE_INSTALL"
  pip install --quiet $PRE_INSTALL
fi

echo "Downloading: $MODEL_HANDLE"
hf download "$MODEL_HANDLE"

echo "Starting trtllm-serve: $MODEL_HANDLE"
exec trtllm-serve "$MODEL_HANDLE" \
  --host 0.0.0.0 \
  --max_batch_size "${MAX_BATCH_SIZE:-32}" \
  --trust_remote_code \
  --port 8000 \
  --extra_llm_api_options /tmp/extra-llm-api-config.yml
