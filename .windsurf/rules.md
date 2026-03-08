# Project Rules for Claude Code / Windsurf

## Project Overview

This project runs Qwen3.5 models on NVIDIA DGX Spark (Grace Blackwell ARM64) using vLLM in Docker, with remote access for Claude Code.

## Architecture

- **Hardware**: DGX Spark (ARM64, 128GB unified memory, Blackwell GB10 GPU)
- **Container**: `vllm/vllm-openai:cu130-nightly` (ARM64 with Qwen3.5 support)
- **Models**: Qwen3.5-35B-A3B (primary), Qwen3.5-122B-A10B (optional)
- **API**: OpenAI-compatible (Claude Code integration)

## Critical Constraints

### 0. Docker Compose Command Format
**CRITICAL**: Always use `docker compose` (with space) instead of `docker-compose` (with hyphen). The hyphenated version is deprecated and not available on this system.

```bash
# CORRECT
docker compose up -d
docker compose down
docker compose ps

# WRONG - DO NOT USE
docker-compose up -d
docker-compose down
docker-compose ps
```

### 1. Architecture is ARM64
- DGX Spark uses Grace CPU (ARM Cortex-X925/A725)
- **Never** use x86_64 Docker images
- **Always** use `vllm/vllm-openai:cu130-nightly` or ARM64-compatible images

### 2. Required vLLM Flags
```bash
--reasoning-parser qwen3         # Enable reasoning mode
--tool-call-parser qwen3_coder   # Enable tool calling
--enable-auto-tool-choice        # Auto tool selection
--enable-prefix-caching          # Performance optimization
```

### 3. Memory Management
- Total: 128GB unified (CPU + GPU shared)
- 35B model: ~90GB used with vLLM (efficient)
- 122B model: ~120GB (experimental)
- Use `--gpu-memory-utilization 0.80` for stability

### 4. Performance Expectations
- 35B-A3B: 30-50 tok/s (depends on context length)
- First run: ~15 minutes (model download + CUDA graph compilation)
- Subsequent runs: 1-2 minutes
- Memory bandwidth limited: ~273 GB/s LPDDR5X

## File Structure

```
CodingDGX/
├── README.md                    # Quickstart guide
├── docker-compose.yml           # Service definitions
├── .env.example                 # HF token template
├── .gitignore
├── docs/                        # Documentation
│   ├── MODEL_GUIDE.md
│   ├── REMOTE_ACCESS.md
│   └── TROUBLESHOOTING.md
└── utils/                       # Utility scripts
    ├── check_status.sh
    └── test_connection.py
```

## Code Style

### Docker Compose
- Use `vllm/vllm-openai:cu130-nightly` image
- Model name as first argument in command
- Set `shm_size: '64gb'` and `ipc: host`
- Bind to `0.0.0.0` for remote access
- Port 8000 (vLLM default)

### Documentation
- Keep docs concise and practical
- Include code examples
- Reference actual performance numbers
- Link to official resources

### Scripts
- Bash for server-side utilities
- Python for client-side tools
- Include error handling
- Provide clear output

## What NOT to Do

1. **Don't** create custom Dockerfiles - use official vLLM image
2. **Don't** use SGLang - vLLM has better Qwen3.5 support
3. **Don't** use x86 CUDA images
4. **Don't** create unnecessary abstraction layers
5. **Don't** add Python virtual environment setup - Docker handles it
6. **Don't** over-engineer - keep it simple

## What TO Do

1. **Do** use `vllm/vllm-openai:cu130-nightly` image
2. **Do** include all required vLLM flags
3. **Do** test on actual DGX Spark hardware
4. **Do** document first-run time (~15 minutes)
5. **Do** keep configuration simple and clear
6. **Do** provide troubleshooting guidance

## Dependencies

### Required
- Docker with NVIDIA Container Toolkit
- HuggingFace token (for model downloads)
- Network access to HuggingFace

### Not Required
- Python virtual environments (Docker handles it)
- Manual package installation
- Custom CUDA setup

## Testing

### Server-Side
```bash
./utils/check_status.sh
curl http://localhost:8000/v1/models
```

### Client-Side
```bash
python utils/test_connection.py YOUR_DGX_IP
```

## Common Issues

1. **Container crashes**: Check logs with `docker logs qwen35-35b`
2. **Slow startup**: First run takes ~15 minutes (model download + CUDA compilation)
3. **Out of memory**: Reduce `--gpu-memory-utilization` to 0.75 or 0.70
4. **Model type not recognized**: Ensure using `vllm/vllm-openai:cu130-nightly` (has vLLM v0.16.0+)

## Version Information

- **vLLM**: v0.16.0+ (in `:cu130-nightly` tag)
- **Qwen3.5**: Latest (Feb/Mar 2026 releases)
- **CUDA**: 13.1 (in vLLM nightly image)
- **PyTorch**: 2.9+ (in vLLM nightly image)

## External Resources

- [vLLM Documentation](https://docs.vllm.ai/)
- [Qwen3.5 GitHub](https://github.com/QwenLM/Qwen3.5)
- [Community Guide](https://github.com/adadrag/qwen3.5-dgx-spark)
- [vLLM Docker Hub](https://hub.docker.com/r/vllm/vllm-openai)

## When Making Changes

1. Test on actual DGX Spark hardware
2. Verify ARM64 compatibility
3. Check memory usage with `nvidia-smi`
4. Measure actual performance (tok/s)
5. Update documentation if behavior changes
6. Keep it simple - avoid over-engineering
