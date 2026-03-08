# Quick Start with Docker (Recommended for DGX Spark)

## Why Docker?
- ✅ No Python environment conflicts
- ✅ No dependency installation issues
- ✅ Clean, isolated environment
- ✅ Easy to start/stop/remove
- ✅ Already configured for remote access

## Prerequisites

Check if Docker is installed:
```bash
docker --version
docker-compose --version
```

If not installed, install Docker:
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Add your user to docker group (avoid sudo)
sudo usermod -aG docker $USER
newgrp docker
```

Install NVIDIA Container Toolkit:
```bash
# Add NVIDIA package repository
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# Install nvidia-docker2
sudo apt-get update
sudo apt-get install -y nvidia-docker2

# Restart Docker
sudo systemctl restart docker

# Test GPU access
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

## Launch Qwen3.5-35B (Recommended)

```bash
# Start the container
docker-compose up -d qwen35-35b

# View logs (wait for "Server started" message)
docker-compose logs -f qwen35-35b

# Test it's working
curl http://localhost:8001/v1/models
```

## Launch Qwen3.5-122B (Maximum Quality)

```bash
# Start the container
docker-compose up -d qwen35-122b

# View logs
docker-compose logs -f qwen35-122b
```

## Configure Firewall for Remote Access

```bash
# Allow port 8001 for remote connections
sudo ufw allow 8001/tcp

# Or if using firewalld
sudo firewall-cmd --permanent --add-port=8001/tcp
sudo firewall-cmd --reload
```

## Get Server IP Address

```bash
# Find your DGX Spark IP
hostname -I | awk '{print $1}'
```

## Test from Client Machine

From your development machine:
```bash
# Test connection (replace with your DGX IP)
curl http://192.168.1.100:8001/v1/models
```

## Configure Claude Code on Client

**PowerShell:**
```powershell
$env:ANTHROPIC_BASE_URL = "http://192.168.1.100:8001/v1"
$env:ANTHROPIC_AUTH_TOKEN = "dummy"
claude --model Qwen/Qwen3.5-35B-A3B
```

**Bash:**
```bash
export ANTHROPIC_BASE_URL=http://192.168.1.100:8001/v1
export ANTHROPIC_AUTH_TOKEN=dummy
claude --model Qwen/Qwen3.5-35B-A3B
```

## Common Commands

```bash
# View running containers
docker ps

# View logs
docker-compose logs -f qwen35-35b

# Stop container
docker-compose down

# Restart container
docker-compose restart qwen35-35b

# Remove container and start fresh
docker-compose down
docker-compose up -d qwen35-35b

# Check GPU usage
nvidia-smi

# Check container resource usage
docker stats qwen35-35b
```

## Troubleshooting

### Container won't start
```bash
# Check logs for errors
docker-compose logs qwen35-35b

# Check if GPU is accessible
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

### Out of memory
```bash
# Use smaller model
docker-compose down
docker-compose up -d qwen35-35b  # Instead of 122b
```

### Can't connect remotely
```bash
# Verify server is listening on all interfaces
sudo netstat -tlnp | grep 8001
# Should show: 0.0.0.0:8001 (not 127.0.0.1:8001)

# Check firewall
sudo ufw status
```

## Model Download

Models are automatically downloaded on first run. This may take time depending on your internet connection:

- **35B model**: ~22GB download
- **122B model**: ~76GB download

To pre-download models:
```bash
# Install huggingface-cli
pip install --user huggingface-hub

# Download model
huggingface-cli download Qwen/Qwen3.5-35B-A3B --local-dir ./models/Qwen3.5-35B-A3B
```

## That's It!

Docker handles all the complexity. No virtual environments, no dependency conflicts, just works.
