# Project Rules for Claude Code

## Project Overview

This project runs multiple LLMs on NVIDIA DGX Spark (Grace Blackwell ARM64) using **TensorRT-LLM** in Docker, with OpenAI-compatible API for Claude Code integration. It also hosts a growing **projects/** directory for AI applications built on top of these models.

## Architecture

- **Hardware**: DGX Spark (ARM64, 128GB unified memory, Blackwell GB10 GPU)
- **Runtime**: TensorRT-LLM 1.2.0rc6 (`nvcr.io/nvidia/tensorrt-llm/release:1.2.0rc6`)
- **Quantization**: NVFP4 (Blackwell-native 4-bit float, very fast)
- **API**: OpenAI-compatible at each model's port
- **Model cache**: `~/.cache/huggingface` shared across containers

## Available Models

| Service | Model | Port | Profile | Active Params | Best For |
|---------|-------|------|---------|--------------|----------|
| qwen3-a3b | nvidia/Qwen3-30B-A3B-NVFP4 | 8002 | qwen3a3b | 3B | Speed, daily use |
| qwen3-32b | nvidia/Qwen3-32B-NVFP4 | 8003 | qwen332b | 32B | Reasoning, quality |
| phi4-reasoning | nvidia/Phi-4-reasoning-plus-NVFP4 | 8004 | phi4 | ~14B | Math, logic |
| llama33-70b | nvidia/Llama-3.3-70B-Instruct-NVFP4 | 8005 | llama3370b | 70B | General purpose |
| gpt-oss-120b | openai/gpt-oss-120b | 8006 | gptoss120b | ~120B MoE | Quality, fits ~80GB |
| nemotron-120b | nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4 | 8007 | nemotron120b | 12B | Highest quality (experimental) |
| kimi-k25 | moonshotai/Kimi-K2.5 | 8008 | kimi | MoE | (pending TRT-LLM 1.3.x) |
| nemotron-nano | nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4 | 8009 | nemotronnano | 3B | Fast MoE, agentic |
| qwen35-35b | Qwen/Qwen3.5-35B-A3B-FP8 | 8010 | qwen3535b | 3B | Coding, fast MoE |

## File Structure

```
CodingDGX/
├── README.md
├── docker-compose.yml           # 7 model services via Docker Compose profiles
├── .env.example                 # HF_TOKEN template
├── config/
│   ├── trtllm-config.yml        # KV cache, GPU memory fraction, CUDA graphs
│   └── start_trtllm.sh          # Container startup: HF download + trtllm-serve
├── docs/
│   ├── MODEL_GUIDE.md           # Model comparison, benchmarks, selection guide
│   ├── REMOTE_ACCESS.md         # Networking, firewall, SSH tunnel, static IP
│   ├── TROUBLESHOOTING.md       # Comprehensive issue resolution
│   ├── ADDING_MODELS.md         # How to add new models to docker-compose
│   ├── MODEL_SWITCHING.md       # Switch between models
│   └── PERFORMANCE_MONITORING.md
├── utils/
│   ├── check_status.sh          # Health check: container → port → API
│   ├── test_connection.py       # Remote connectivity + Claude Code setup test
│   ├── switch_model.sh          # Stop all, start one model by name
│   ├── test_models.sh           # Test all models sequentially with memory watchdog
│   ├── monitor_metrics.py       # Real-time Prometheus metrics dashboard
│   └── test_performance.py      # One-shot TTFT + tok/s measurement
└── projects/                    # AI applications built on DGX models
    └── voice-home-assistant/    # (planned) Voice → Home Assistant control
```

## Critical Constraints

### 1. Architecture is ARM64
- DGX Spark uses Grace CPU (ARM Cortex-X925/A725)
- **Never** use x86_64 Docker images
- **Always** use `nvcr.io/nvidia/tensorrt-llm/release:1.2.0rc6` or ARM64-compatible images

### 2. Runtime is TensorRT-LLM (NOT vLLM)
- Image: `nvcr.io/nvidia/tensorrt-llm/release:1.2.0rc6`
- Startup: `bash /start_trtllm.sh` inside container
- Config: `/tmp/extra-llm-api-config.yml` (mapped from `config/trtllm-config.yml`)
- Models must be NVFP4 variants from NVIDIA NGC/HuggingFace

### 3. Memory Management
- Total: 128GB unified (CPU + GPU shared), ~119GB usable
- `free_gpu_memory_fraction: 0.70` in trtllm-config.yml
- Safety watchdog in test_models.sh: warn at 15GB free, kill at 8GB free
- Only run one model at a time in production (profiles enforce this)

### 4. Performance Expectations (NVFP4 on Blackwell)
- Phi-4: ~100-120 tok/s
- Qwen3-A3B: ~70-80 tok/s (default choice for speed)
- Qwen3-32B: ~50-60 tok/s
- Llama-3.3-70B: ~35-45 tok/s
- DeepSeek-V3.2: ~30-40 tok/s
- First run: ~15 minutes (model download + CUDA graph compilation)

## Docker Compose Usage

```bash
# Start a model
docker compose --profile qwen3a3b up -d

# Switch models
./utils/switch_model.sh 35b       # Qwen3-A3B (fastest)
./utils/switch_model.sh deepseek  # DeepSeek (best coding)
./utils/switch_model.sh 32b       # Qwen3-32B (best reasoning)

# Check health
./utils/check_status.sh
```

## Claude Code Integration

```bash
# On client machine
export ANTHROPIC_BASE_URL=http://DGX_IP:8002   # Port matches model
export ANTHROPIC_AUTH_TOKEN=dummy
claude --model qwen3-30b-a3b
```

## Code Style

### Docker Compose Services
- Use `nvcr.io/nvidia/tensorrt-llm/release:1.2.0rc6` image
- Each model gets its own Docker Compose profile
- Set `shm_size: '64gb'` and `ipc: host`
- Bind to `0.0.0.0` for remote access
- Unique port per model (8002–8008 range)
- Volume mount: `config/start_trtllm.sh:/start_trtllm.sh` and `config/trtllm-config.yml:/tmp/extra-llm-api-config.yml`

### Documentation
- Keep concise and practical
- Include actual performance numbers
- Reference specific ports and profiles

### Scripts
- Bash for server-side utilities (ARM64 compatible)
- Python for client-side tools (no venv needed on client if simple deps)
- Include error handling and clear output

## What NOT to Do

1. **Don't** use vLLM — project has migrated to TensorRT-LLM
2. **Don't** use SGLang
3. **Don't** use x86 CUDA images
4. **Don't** create custom Dockerfiles — use official TRT-LLM image
5. **Don't** run multiple large models simultaneously (OOM risk)
6. **Don't** over-engineer — keep configurations simple

## What TO Do

1. **Do** use `nvcr.io/nvidia/tensorrt-llm/release:1.2.0rc6`
2. **Do** use NVFP4 model variants for best Blackwell performance
3. **Do** use Docker Compose profiles for model isolation
4. **Do** test on actual DGX Spark hardware
5. **Do** update performance numbers from real measurements
6. **Do** provide troubleshooting guidance in docs/

## Projects Directory

The `projects/` folder contains self-contained AI applications built on top of the DGX model infrastructure.

### Project Conventions
- Each project is its own subdirectory: `projects/<project-name>/`
- Include a README.md with setup, architecture, and usage
- Projects may run on the DGX or on a client machine calling DGX APIs
- Keep project dependencies isolated (Docker or venv per project)
- Document which DGX model(s) the project uses and why

### Planned: voice-home-assistant
Goal: Say a voice command → LLM interprets it → controls Home Assistant via MCP.

Architecture:
```
Microphone → STT (Whisper) → LLM (Qwen3-A3B on DGX) + HA MCP → Home Assistant API
```

Components:
- **STT**: faster-whisper (runs locally or on DGX) for low-latency transcription
- **LLM**: Qwen3-A3B (port 8002) — fast enough for real-time voice response
- **MCP**: Home Assistant MCP server (`npx @modelcontextprotocol/server-home-assistant`)
- **Orchestrator**: Python script that ties STT → LLM → HA together

Key considerations:
- HA_TOKEN and HA_URL needed for Home Assistant MCP
- Qwen3-A3B preferred for speed (70-80 tok/s) over quality models
- Whisper `base` or `small` model for fast STT; `medium` for accuracy
- MCP tool calling requires `--tool-call-parser` support (verify TRT-LLM support)

## Common Issues

1. **Container won't start**: Check `docker logs <service>` and verify HF_TOKEN in `.env`
2. **Slow first startup**: ~15 min for model download + CUDA graph compilation (normal)
3. **Out of memory**: Only one model at a time; reduce `free_gpu_memory_fraction` to 0.65
4. **Model not found**: Ensure NVFP4 variant exists on HuggingFace for that model
5. **Kimi not working**: Requires TRT-LLM 1.3.x (not yet released as of 2026-03-14)

## Version Information

- **TensorRT-LLM**: 1.2.0rc6
- **CUDA**: 12.x (in TRT-LLM image)
- **Models**: Qwen3, Phi-4, Llama-3.3, DeepSeek-V3.2, Nemotron (all Feb/Mar 2026 NVFP4)

## External Resources

- [TensorRT-LLM Docs](https://nvidia.github.io/TensorRT-LLM/)
- [NVIDIA NGC - TRT-LLM Image](https://catalog.ngc.nvidia.com/orgs/nvidia/teams/tensorrt-llm/containers/release)
- [Qwen3 GitHub](https://github.com/QwenLM/Qwen3)
- [Home Assistant MCP](https://github.com/modelcontextprotocol/servers/tree/main/src/home-assistant)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)

## When Making Changes

1. Test on actual DGX Spark hardware
2. Verify ARM64 compatibility before adding any image or binary
3. Check memory usage with `nvidia-smi` after startup
4. Measure actual tok/s and update docs if changed
5. Keep project structure simple — one directory per concern
