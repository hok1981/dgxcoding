# Docker Deployment Guide for Qwen3.5

## Pros of Using Docker

### **Advantages**
- **Isolation**: Clean environment, no conflicts with system packages
- **Reproducibility**: Same setup across different machines
- **Easy cleanup**: Remove container = clean slate
- **Version control**: Pin exact dependency versions
- **Multiple models**: Run different models on different ports simultaneously
- **Portability**: Share exact setup with team members
- **Resource limits**: Control memory/GPU allocation per container

### **Disadvantages**
- **Overhead**: Slight performance penalty (~2-5%)
- **Complexity**: Additional layer to debug
- **Storage**: Docker images take extra space
- **GPU passthrough**: Requires nvidia-docker runtime
- **Model downloads**: Need to handle HuggingFace cache properly

## Prerequisites

1. **Docker with NVIDIA GPU support**
   ```powershell
   # Install Docker Desktop for Windows
   # Enable WSL2 backend
   # Install NVIDIA Container Toolkit
   ```

2. **Verify GPU access**
   ```powershell
   docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
   ```

## Quick Start

### **Option 1: Docker Compose (Recommended)**

```powershell
# Build and start 122B model
docker-compose up -d qwen35-122b

# View logs
docker-compose logs -f qwen35-122b

# Stop
docker-compose down
```

### **Option 2: Direct Docker Build**

```powershell
# Build image
docker build -t qwen35:latest .

# Run 122B model
docker run -d \
  --name qwen35-122b \
  --gpus all \
  -p 8001:8001 \
  -v ${PWD}/models:/app/models \
  --shm-size 32g \
  qwen35:latest
```

## Running Multiple Models

```powershell
# Start 122B on port 8001
docker-compose up -d qwen35-122b

# Start 35B on port 8002 (if you have memory)
docker-compose --profile alternative up -d qwen35-35b
```

## Model Caching

Models are cached in a Docker volume to avoid re-downloading:

```powershell
# View cached models
docker volume inspect codingdgx_huggingface_cache

# Clear cache if needed
docker volume rm codingdgx_huggingface_cache
```

## Pre-download Models

To avoid downloading during container startup:

```powershell
# Download to local models directory
python -c "
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='Qwen/Qwen3.5-122B-A10B',
    local_dir='./models/Qwen3.5-122B-A10B'
)
"

# Update docker-compose.yml to use local path
# --model-path /app/models/Qwen3.5-122B-A10B
```

## Connecting Claude Code to Docker Container

```powershell
# Same as before - container exposes port 8001
$env:ANTHROPIC_BASE_URL = "http://localhost:8001/v1"
$env:ANTHROPIC_AUTH_TOKEN = "dummy"

claude --model Qwen/Qwen3.5-122B-A10B
```

## Monitoring

```powershell
# View logs
docker-compose logs -f qwen35-122b

# Check resource usage
docker stats qwen35-122b

# Access container shell
docker exec -it qwen35-122b bash
```

## Troubleshooting

### GPU not accessible
```powershell
# Verify NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

### Out of memory
```powershell
# Increase shared memory
# Edit docker-compose.yml: shm_size: '64gb'
```

### Slow startup
```powershell
# Pre-download models to avoid download during startup
# See "Pre-download Models" section above
```

## Production Recommendations

1. **Use Docker volumes** for model cache (already configured)
2. **Pre-download models** before deployment
3. **Set resource limits** in docker-compose.yml
4. **Use health checks** to monitor container status
5. **Enable logging** to persistent storage
6. **Consider Kubernetes** for multi-node deployments

## Docker vs Native Comparison

| Aspect | Docker | Native |
|--------|--------|--------|
| Setup | Easier, isolated | More control |
| Performance | ~2-5% overhead | Maximum speed |
| Cleanup | Simple (remove container) | Manual |
| Updates | Rebuild image | Update packages |
| Multiple models | Easy (different containers) | Port conflicts |
| Debugging | Extra layer | Direct access |
| **Recommendation** | Development, testing | Production, max performance |

## When to Use Docker

**Use Docker if:**
- You want easy cleanup and experimentation
- Running multiple models simultaneously
- Sharing setup with team
- Need reproducible environments
- Deploying to cloud/Kubernetes

**Use Native if:**
- Maximum performance is critical
- You're comfortable with Python environments
- Single model deployment
- Direct hardware access needed
