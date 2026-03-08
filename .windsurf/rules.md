# Project Rules for Claude Code / Windsurf

## Project Overview

This project runs Qwen3.5 models on NVIDIA DGX Spark (Grace Blackwell ARM64) using SGLang in Docker, with remote access for Claude Code.

## Architecture

- **Hardware**: DGX Spark (ARM64, 128GB unified memory, Blackwell GB10 GPU)
- **Container**: `lmsysorg/sglang:spark` (official ARM64 image)
- **Models**: Qwen3.5-35B-A3B (primary), Qwen3.5-122B-A10B (optional)
- **API**: Anthropic-compatible (Claude Code integration)

## Critical Constraints

### 1. Architecture is ARM64
- DGX Spark uses Grace CPU (ARM Cortex-X925/A725)
- **Never** use x86_64 Docker images
- **Always** use `lmsysorg/sglang:spark` or ARM64-compatible images

### 2. Required SGLang Flags
```bash
--attention-backend triton        # Required for GB10 GPU
--trust-remote-code              # Required for Qwen models
--reasoning-parser qwen3         # Enable reasoning mode
--tool-call-parser qwen3_coder   # Enable tool calling
```

### 3. Memory Management
- Total: 128GB unified (CPU + GPU shared)
- 35B model: ~118GB used (safe)
- 122B model: Requires FP4 quantization, experimental

### 4. Performance Expectations
- 35B-A3B: ~30 tok/s (BF16) - this is the ceiling
- Memory bandwidth limited: ~273 GB/s LPDDR5X
- Don't expect faster speeds without quantization

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
- Use `lmsysorg/sglang:spark` image
- Include all required flags
- Set `shm_size: '32gb'` and `ipc: host`
- Bind to `0.0.0.0` for remote access

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

1. **Don't** create custom Dockerfiles - use official image
2. **Don't** include vLLM - SGLang only
3. **Don't** use x86 CUDA images
4. **Don't** create unnecessary abstraction layers
5. **Don't** add Python virtual environment setup - Docker handles it
6. **Don't** over-engineer - keep it simple

## What TO Do

1. **Do** use official `lmsysorg/sglang:spark` image
2. **Do** include all required SGLang flags
3. **Do** test on actual DGX Spark hardware
4. **Do** document performance characteristics
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
curl http://localhost:8001/v1/models
```

### Client-Side
```bash
python utils/test_connection.py YOUR_DGX_IP
```

## Common Issues

1. **Container crashes**: Check logs with `docker logs qwen35-35b`
2. **Slow startup**: Model download takes 2-3 minutes first time
3. **Out of memory**: Use 35B model, not 122B
4. **Wrong architecture**: Ensure using `lmsysorg/sglang:spark`

## Version Information

- **SGLang**: v0.5.9+ (use `:spark` tag)
- **Qwen3.5**: Latest (Feb/Mar 2026 releases)
- **CUDA**: 13.0 (in spark image)
- **PyTorch**: 2.10+ (in spark image)

## External Resources

- [DGX Spark Playbooks](https://github.com/NVIDIA/dgx-spark-playbooks)
- [SGLang Documentation](https://docs.sglang.io/)
- [Qwen3.5 GitHub](https://github.com/QwenLM/Qwen3.5)
- [SGLang Spark Support](https://github.com/sgl-project/sglang/issues/11658)

## When Making Changes

1. Test on actual DGX Spark hardware
2. Verify ARM64 compatibility
3. Check memory usage with `nvidia-smi`
4. Measure actual performance (tok/s)
5. Update documentation if behavior changes
6. Keep it simple - avoid over-engineering
