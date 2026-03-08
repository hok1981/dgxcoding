# Qwen3.5 on NVIDIA DGX Spark

Run Qwen3.5 models locally on DGX Spark (Grace Blackwell) with vLLM and connect to Claude Code for AI-assisted development.

## Quick Start

### 1. Set HuggingFace Token

```bash
cp .env.example .env
# Edit .env and add your HuggingFace token
```

### 2. Start Qwen3.5-35B

```bash
docker-compose up -d qwen35-35b
```

### 3. Monitor Startup

```bash
# Watch logs (first run: ~15 minutes for model download + CUDA compilation)
docker logs -f qwen35-35b

# Check status
./utils/check_status.sh
```

**Note:** First run takes ~15 minutes (model download ~70GB + CUDA graph compilation). Subsequent starts are 1-2 minutes.

### 4. Connect Claude Code (from client machine)

Get your DGX Spark IP:
```bash
hostname -I | awk '{print $1}'
```

On your client machine:
```bash
# PowerShell
$env:ANTHROPIC_BASE_URL = "http://YOUR_DGX_IP:8002/v1"
$env:ANTHROPIC_AUTH_TOKEN = "dummy"

# Bash
export ANTHROPIC_BASE_URL=http://YOUR_DGX_IP:8002/v1
export ANTHROPIC_AUTH_TOKEN=dummy

# Use with Claude Code
claude --model qwen3.5-35b
```

## Available Models

| Model | Command | Memory | Performance | Port |
|-------|---------|--------|-------------|------|
| **Qwen3.5-35B-A3B** | `docker-compose up -d qwen35-35b` | ~90GB | 30-50 tok/s | 8002 |
| **Qwen3.5-122B-A10B** | `docker-compose --profile large up -d qwen35-122b` | ~120GB | ~15 tok/s | 8003 |

## Architecture

```
┌─────────────────────┐         Network          ┌─────────────────────┐
│  Client Machine     │◄──────────────────────►│  DGX Spark Server   │
│                     │                          │                     │
│  - Claude Code      │    HTTP API (8002)      │  - Qwen3.5 Model    │
│  - Your IDE         │                          │  - vLLM Server      │
│  - Development      │                          │  - 128GB Memory     │
└─────────────────────┘                          └─────────────────────┘
```

## Documentation

- **[Model Guide](docs/MODEL_GUIDE.md)** - Model specs, memory requirements, performance
- **[Remote Access](docs/REMOTE_ACCESS.md)** - Client-server networking setup
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

## Utilities

- **`utils/check_status.sh`** - Health check and status
- **`utils/test_connection.py`** - Test remote connectivity from client

## Hardware

- **System**: NVIDIA DGX Spark
- **CPU**: Grace (20 ARM cores - 10x Cortex-X925 + 10x Cortex-A725)
- **GPU**: Blackwell GB10 (6144 CUDA cores, SM 12.1)
- **Memory**: 128GB unified (CPU + GPU shared)
- **Architecture**: ARM64

## Features

All Qwen3.5 models support:
- **256K context window** (131K default for memory efficiency)
- **Hybrid reasoning** (thinking and non-thinking modes)
- **Tool calling** via `qwen3_coder` parser
- **Anthropic-compatible API** (works with Claude Code)
- **358 programming languages**

## License

Apache 2.0 (same as Qwen3.5 models)
