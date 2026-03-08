# Model Switching Guide

Quick guide for switching between different models on DGX Spark.

## Quick Switch

### Linux/macOS (Bash)
```bash
# Switch to 35B model (faster, 262K context)
./utils/switch_model.sh 35b

# Switch to 122B model (slower, 65K context)
./utils/switch_model.sh 122b

# Stop all models
./utils/switch_model.sh stop

# Show status
./utils/switch_model.sh status
```

### Windows (PowerShell)
```powershell
# Switch to 35B model
.\utils\switch_model.ps1 35b

# Switch to 122B model
.\utils\switch_model.ps1 122b

# Stop all models
.\utils\switch_model.ps1 stop

# Show status
.\utils\switch_model.ps1 status
```

## Model Comparison

| Model | Speed | Context | Memory | Best For |
|-------|-------|---------|--------|----------|
| **35B-A3B** | 30-50 tok/s | 262K | ~90GB | General use, long context, coding |
| **122B-A10B** | 15-25 tok/s | 65K | ~120GB | Complex reasoning, quality over speed |

## Manual Switching

If you prefer manual control:

```bash
# Stop current model
docker compose down

# Start 35B
docker compose up -d qwen35-35b

# Start 122B (requires profile)
docker compose --profile large up -d qwen35-122b
```

## Adding New Models

To add a new model to the switching script:

1. **Add service to `docker compose.yml`:**

```yaml
services:
  my-new-model:
    image: vllm/vllm-openai:cu130-nightly
    container_name: my-new-model
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - HF_TOKEN=${HF_TOKEN}
    ports:
      - "0.0.0.0:8004:8000"  # Use unique external port
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
      org/model-name
      --served-model-name my-model
      --port 8000
      --host 0.0.0.0
      --max-model-len 32768
      --gpu-memory-utilization 0.80
    restart: unless-stopped
```

2. **Update switching scripts:**

**Bash (`utils/switch_model.sh`):**
```bash
declare -A MODELS=(
    ["35b"]="qwen35-35b"
    ["122b"]="qwen35-122b"
    ["mymodel"]="my-new-model"  # Add this line
)
```

**PowerShell (`utils/switch_model.ps1`):**
```powershell
$Models = @{
    "35b" = "qwen35-35b"
    "122b" = "qwen35-122b"
    "mymodel" = "my-new-model"  # Add this line
}
```

3. **Update usage text in both scripts** to document the new model.

## Monitoring After Switch

After switching models:

```bash
# Check startup progress
docker logs -f <container-name>

# Wait for "Application startup complete" message

# Verify with status checker
./utils/check_status.sh

# Monitor performance
python utils/monitor_metrics.py
```

## Troubleshooting

### Model won't start
- Check logs: `docker logs <container-name>`
- Verify GPU memory is free: `nvidia-smi`
- Ensure previous model is stopped: `docker ps`

### Out of memory
- Stop other containers: `docker compose down`
- Reduce `--gpu-memory-utilization` in docker compose.yml
- Use smaller model or shorter context

### Port conflicts
- Each model needs a unique external port
- Check used ports: `ss -tlnp | grep 800`
- Update `ports` in docker compose.yml

## Performance Tips

### For Speed (35B)
```yaml
--max-model-len 32768          # Shorter context
--gpu-memory-utilization 0.85  # More cache
```

### For Quality (122B)
```yaml
--max-model-len 65536          # Full context
--gpu-memory-utilization 0.75  # Stable memory
```

### For Long Context (35B)
```yaml
--max-model-len 262144         # Maximum context
--gpu-memory-utilization 0.80  # Balanced
```

## Client Configuration

After switching models, update your client:

```bash
# For 35B on port 8002
export ANTHROPIC_BASE_URL=http://192.168.68.40:8002
export ANTHROPIC_AUTH_TOKEN=dummy
claude --model qwen3.5-35b

# For 122B on port 8003
export ANTHROPIC_BASE_URL=http://192.168.68.40:8003
export ANTHROPIC_AUTH_TOKEN=dummy
claude --model qwen3.5-122b
```

## Quick Reference

```bash
# Switch models
./utils/switch_model.sh 35b|122b

# Check status
./utils/check_status.sh

# Monitor performance
python utils/monitor_metrics.py

# View logs
docker logs -f qwen35-35b
docker logs -f qwen35-122b

# Stop everything
docker compose down
```
