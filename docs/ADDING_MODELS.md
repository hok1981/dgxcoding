# Adding New Models to DGX Spark

Quick guide for adding and testing new models.

## Quick Add

### 1. Add to docker-compose.yml

```yaml
services:
  deepseek-v3:
    image: vllm/vllm-openai:cu130-nightly
    container_name: deepseek-v3
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - HF_TOKEN=${HF_TOKEN}
    ports:
      - "0.0.0.0:8004:8000"  # Use next available port
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    shm_size: '64gb'
    ipc: host
    ulimits:
      memlock: -1
      stack: 67108864
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    command: >
      deepseek-ai/DeepSeek-V3
      --served-model-name deepseek-v3
      --port 8000
      --host 0.0.0.0
      --max-model-len 32768
      --gpu-memory-utilization 0.75
      --enable-prefix-caching
    restart: unless-stopped
```

### 2. Update switch_model.sh

```bash
get_service_name() {
    case "$1" in
        35b) echo "qwen35-35b" ;;
        122b) echo "qwen35-122b" ;;
        deepseek) echo "deepseek-v3" ;;  # Add this
        *) echo "" ;;
    esac
}
```

Update the usage text:
```bash
echo "  deepseek - DeepSeek-V3 (30-40 tok/s, 128K context)"
```

### 3. Update switch_model.ps1

```powershell
$Models = @{
    "35b" = "qwen35-35b"
    "122b" = "qwen35-122b"
    "deepseek" = "deepseek-v3"  # Add this
}
```

Update the usage text similarly.

### 4. Test the Model

```bash
# Switch to new model
./utils/switch_model.sh deepseek

# Monitor startup
docker logs -f deepseek-v3

# Check status
./utils/check_status.sh

# Test API
curl http://localhost:8004/v1/models

# Monitor performance
python utils/monitor_metrics.py http://localhost:8004
```

## Model-Specific Configurations

### For Coding Models
```yaml
command: >
  Qwen/Qwen2.5-Coder-32B-Instruct
  --served-model-name qwen-coder
  --port 8000
  --host 0.0.0.0
  --max-model-len 32768
  --gpu-memory-utilization 0.75
  --enable-prefix-caching
  --trust-remote-code
```

### For MoE Models (DeepSeek, Mixtral)
```yaml
command: >
  deepseek-ai/DeepSeek-V3
  --served-model-name deepseek-v3
  --port 8000
  --host 0.0.0.0
  --max-model-len 32768
  --gpu-memory-utilization 0.75
  --enable-prefix-caching
  --tensor-parallel-size 1
```

### For FP8 Quantized Models
```yaml
command: >
  meta-llama/Llama-3.3-70B-Instruct
  --served-model-name llama-3.3-70b
  --port 8000
  --host 0.0.0.0
  --max-model-len 32768
  --quantization fp8
  --gpu-memory-utilization 0.80
  --enable-prefix-caching
```

### For Vision Models
```yaml
command: >
  Qwen/Qwen2-VL-72B-Instruct
  --served-model-name qwen2-vl
  --port 8000
  --host 0.0.0.0
  --max-model-len 32768
  --gpu-memory-utilization 0.75
  --enable-prefix-caching
  --trust-remote-code
  --max-num-seqs 5
```

## Memory Guidelines

| Model Size | BF16 Memory | FP8 Memory | Recommended GPU Util |
|------------|-------------|------------|---------------------|
| 7-14B | ~28-56GB | ~14-28GB | 0.85 |
| 30-35B | ~60-90GB | ~30-45GB | 0.80 |
| 70B | ~140GB | ~70GB | 0.75 (FP8 only) |
| 120B+ | Too large | ~60-100GB | 0.70 (FP8 only) |

**Your DGX Spark has 119GB unified memory**, so:
- ✅ Up to 35B models in BF16
- ✅ Up to 70B models in FP8
- ✅ MoE models (sparse activation)
- ❌ 120B+ dense models in BF16

## Port Assignments

Keep track of used ports:

| Port | Model | Status |
|------|-------|--------|
| 8002 | qwen35-35b | Active |
| 8003 | qwen35-122b | Reserved |
| 8004 | Available | - |
| 8005 | Available | - |
| 8006 | Available | - |

## Troubleshooting

### Model won't load
```bash
# Check logs
docker logs <container-name>

# Check memory
free -h
nvidia-smi

# Try reducing memory
--gpu-memory-utilization 0.65
--max-model-len 16384
```

### Out of memory
```bash
# Stop all models
docker compose down

# Try with FP8 quantization
--quantization fp8

# Or use smaller model
```

### Slow performance
```bash
# Reduce context length
--max-model-len 16384

# Increase GPU utilization
--gpu-memory-utilization 0.85

# Enable prefix caching (if not already)
--enable-prefix-caching
```

## Recommended Models by Use Case

### Best for Coding
1. Qwen2.5-Coder-32B-Instruct
2. DeepSeek-Coder-V2-Lite-Instruct
3. Qwen3.5-35B-A3B (current)

### Best for Reasoning
1. DeepSeek-V3
2. Qwen3.5-35B-A3B (current)
3. Llama-3.3-70B-Instruct (FP8)

### Best for Speed
1. Qwen2.5-14B-Instruct
2. DeepSeek-Coder-V2-Lite-Instruct
3. Gemma-2-27B-IT

### Best for Long Context
1. Qwen3.5-35B-A3B (262K) ⭐
2. Llama-3.3-70B-Instruct (128K)
3. DeepSeek-V3 (128K)

## Finding More Models

Browse HuggingFace for vLLM-compatible models:
- https://huggingface.co/models?pipeline_tag=text-generation&sort=trending
- Filter by: "vLLM compatible", "ARM64", "< 100GB"
- Check model card for memory requirements

## Quick Test Script

```bash
#!/bin/bash
# test_model.sh <model_name> <port>

MODEL=$1
PORT=${2:-8004}

echo "Testing $MODEL on port $PORT..."

# Test health
curl -s http://localhost:$PORT/health

# Test models endpoint
curl -s http://localhost:$PORT/v1/models | jq

# Test completion
curl -s http://localhost:$PORT/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "'$MODEL'",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 50
  }' | jq
```

## Client Configuration

After switching models, update Claude Code:

```bash
# For model on port 8004
export ANTHROPIC_BASE_URL=http://192.168.68.40:8004
export ANTHROPIC_AUTH_TOKEN=dummy
claude --model <model-name>
```

PowerShell:
```powershell
$env:ANTHROPIC_BASE_URL = "http://192.168.68.40:8004"
$env:ANTHROPIC_AUTH_TOKEN = "dummy"
claude --model <model-name>
```
