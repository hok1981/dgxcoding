# Troubleshooting Guide

## Container Won't Start

### Error: "unknown or invalid runtime name: nvidia"

**Cause:** NVIDIA Container Toolkit not installed or not configured.

**Solution:**
```bash
# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configure Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Test
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

### Error: "permission denied while trying to connect to Docker daemon"

**Cause:** User not in docker group.

**Solution:**
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Container Exits Immediately

**Check logs:**
```bash
docker logs qwen35-35b
```

**Common causes:**
1. **Missing HF_TOKEN**: Set in `.env` file
2. **Out of memory**: Use smaller model or reduce context length
3. **Model download failed**: Check internet connection and HF token

## Model Loading Issues

### Model Download is Slow

**Solution:**
```bash
# Pre-download model
export HF_TOKEN="your_token_here"
huggingface-cli download Qwen/Qwen3.5-35B-A3B --local-dir ~/.cache/huggingface/hub/models--Qwen--Qwen3.5-35B-A3B
```

### Out of Memory During Model Load

**For 35B model:**
```bash
# Reduce context length
--context-length 65536  # Instead of 131072
```

**For 122B model:**
```bash
# Ensure FP4 quantization is enabled
--quantization modelopt_fp4
--context-length 32768  # Reduce context
--mem-fraction-static 0.6  # Reduce memory allocation
```

## Performance Issues

### Slow Inference (<20 tok/s on 35B)

**Check GPU usage:**
```bash
nvidia-smi
# GPU should be at ~90-100% utilization
```

**Check memory bandwidth:**
```bash
# DGX Spark is limited by memory bandwidth (~273 GB/s)
# ~30 tok/s is expected for BF16
```

**Solutions:**
- Use FP8 quantization (requires additional setup)
- Reduce batch size
- Reduce context length

### High Latency from Client

**Check network:**
```bash
# From client machine
ping YOUR_DGX_IP
# Should be <5ms on LAN
```

**Use wired connection:**
- WiFi adds 10-50ms latency
- Use gigabit ethernet

## API Errors

### 400 Bad Request

**Check request format:**
```bash
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3.5-35B-A3B",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100
  }'
```

**Common mistakes:**
- Missing `Content-Type: application/json` header
- Invalid JSON format
- Wrong model name

### 500 Internal Server Error

**Check server logs:**
```bash
docker logs qwen35-35b --tail 50
```

**Common causes:**
- Out of memory
- Model crashed
- Invalid parameters

**Solution:**
```bash
# Restart container
docker compose restart qwen35-35b
```

### Connection Refused

**Verify server is listening:**
```bash
# On DGX Spark
sudo netstat -tlnp | grep 8001
# Should show: 0.0.0.0:8001
```

**Check firewall:**
```bash
sudo ufw status
# Should show: 8001/tcp ALLOW
```

## Claude Code Issues

### "Unable to connect to Anthropic services"

**Verify environment variables:**
```bash
# PowerShell
echo $env:ANTHROPIC_BASE_URL
echo $env:ANTHROPIC_AUTH_TOKEN

# Bash
echo $ANTHROPIC_BASE_URL
echo $ANTHROPIC_AUTH_TOKEN
```

**Should output:**
```
http://YOUR_DGX_IP:8001/v1
dummy
```

### Claude Code Uses Wrong Model

**Specify model explicitly:**
```bash
claude --model Qwen/Qwen3.5-35B-A3B
```

### Responses are Truncated

**Increase max_tokens:**
```bash
# In your request
"max_tokens": 2048  # Or higher
```

## Docker Issues

### Container Keeps Restarting

**Check logs:**
```bash
docker logs qwen35-35b --tail 100
```

**Disable auto-restart temporarily:**
```bash
docker update --restart=no qwen35-35b
```

### Disk Space Full

**Check disk usage:**
```bash
df -h
```

**Clean up Docker:**
```bash
# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Remove stopped containers
docker container prune
```

### Can't Pull Image

**Check internet connection:**
```bash
ping hub.docker.com
```

**Use proxy if needed:**
```bash
# Configure Docker proxy in /etc/docker/daemon.json
{
  "proxies": {
    "http-proxy": "http://proxy.example.com:8080",
    "https-proxy": "http://proxy.example.com:8080"
  }
}

sudo systemctl restart docker
```

## Model-Specific Issues

### Gibberish Output

**Causes:**
1. Context length too low
2. Wrong attention backend
3. Model not fully loaded

**Solutions:**
```bash
# Increase context length
--context-length 131072

# Ensure correct backend
--attention-backend triton

# Wait for model to fully load (check logs)
docker logs -f qwen35-35b
```

### Tool Calling Not Working

**Verify parser is enabled:**
```bash
# In docker compose.yml
--tool-call-parser qwen3_coder
```

**Check request format:**
```json
{
  "model": "Qwen/Qwen3.5-35B-A3B",
  "messages": [...],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "function_name",
        "description": "Function description",
        "parameters": {...}
      }
    }
  ]
}
```

### Reasoning Mode Not Working

**Verify parser is enabled:**
```bash
# In docker compose.yml
--reasoning-parser qwen3
```

**Use appropriate temperature:**
```json
{
  "temperature": 1.0,
  "top_p": 0.95
}
```

## Hardware Issues

### GPU Not Detected

**Check NVIDIA drivers:**
```bash
nvidia-smi
# Should show GB10 GPU
```

**Verify Docker GPU access:**
```bash
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

### Memory Errors

**Check available memory:**
```bash
free -h
# Should show ~128GB total
```

**Reduce memory usage:**
```bash
# Lower memory fraction
--mem-fraction-static 0.6

# Reduce context length
--context-length 65536
```

## Getting Help

### Collect Diagnostic Info

```bash
# System info
uname -a
nvidia-smi

# Docker info
docker --version
docker info | grep -i runtime

# Container status
docker ps -a
docker logs qwen35-35b --tail 100

# Network
ip addr
sudo netstat -tlnp | grep 8001
```

### Useful Resources

- [SGLang Documentation](https://docs.sglang.io/)
- [DGX Spark Playbooks](https://github.com/NVIDIA/dgx-spark-playbooks)
- [Qwen3.5 GitHub](https://github.com/QwenLM/Qwen3.5)
- [SGLang GitHub Issues](https://github.com/sgl-project/sglang/issues)

### Report Issues

When reporting issues, include:
1. DGX Spark system info (`uname -a`, `nvidia-smi`)
2. Docker version and runtime config
3. Full error message and logs
4. Steps to reproduce
5. Model and configuration used
