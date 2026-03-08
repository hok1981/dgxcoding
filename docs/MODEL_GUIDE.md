# Qwen3.5 Model Guide for DGX Spark

## Model Overview

### Qwen3.5-35B-A3B ⭐ (Recommended)

**Architecture:**
- Total Parameters: 35B
- Active Parameters: 3B per token (MoE)
- Experts: 64 routed + 1 shared
- Hybrid Attention: Gated Delta Networks + Full Attention every 4th layer

**Memory Requirements:**
```
System/OS:      ~15 GB
Model (BF16):   ~63 GB
KV Cache:       ~35 GB (131K context)
CUDA Overhead:  ~5 GB
Free:           ~10 GB
─────────────────────────
Total:          ~118 GB / 128 GB
```

**Performance on DGX Spark:**
- Speed: ~30 tok/s (BF16)
- Context: 131K tokens (can extend to 256K)
- Memory bandwidth limited: ~273 GB/s LPDDR5X

**Best For:**
- Fast inference with strong capabilities
- Production deployments
- Multi-turn conversations
- Tool calling and agentic tasks

### Qwen3.5-122B-A10B

**Architecture:**
- Total Parameters: 122B
- Active Parameters: 10B per token (MoE)
- Experts: 64 routed + 1 shared
- Hybrid Attention: Same as 35B

**Memory Requirements (FP4 Quantized):**
```
System/OS:      ~15 GB
Model (FP4):    ~75 GB
KV Cache:       ~25 GB (65K context)
CUDA Overhead:  ~5 GB
Free:           ~8 GB
─────────────────────────
Total:          ~120 GB / 128 GB
```

**Performance on DGX Spark:**
- Speed: ~15 tok/s (FP4)
- Context: 65K tokens (reduced for memory)
- Requires `--quantization modelopt_fp4`

**Best For:**
- Maximum quality
- Complex reasoning tasks
- When speed is less critical

**Note:** FP4 quantization support is still maturing. For production, use 35B model.

### Qwen3.5-27B (Dense)

**Not recommended for DGX Spark** - Dense models are less efficient than MoE on this hardware. Use 35B-A3B instead.

## Architecture Details

### Hybrid Attention

Qwen3.5 uses a novel hybrid approach:
- **Gated Delta Networks (GDN)**: Linear attention (O(n) complexity) for 3 out of 4 layers
- **Full Attention**: Standard multi-head attention every 4th layer for associative recall
- Result: Near-linear scaling with context length while maintaining quality

### Mixture of Experts (MoE)

- **64 Routed Experts**: Top-8 activated per token
- **1 Shared Expert**: Always active for universal features
- **Efficiency**: Only ~3B or ~10B parameters active per forward pass

### Multimodal Support

- DeepStack Vision Transformer with Conv3d
- Native image and video understanding
- Supports vision-language tasks

## Configuration Flags

### Essential Flags

```bash
--attention-backend triton        # Required for DGX Spark (ARM64 + GB10)
--trust-remote-code              # Required for Qwen models
--reasoning-parser qwen3         # Enable thinking/reasoning mode
--tool-call-parser qwen3_coder   # Enable tool calling
```

### Memory Management

```bash
--mem-fraction-static 0.7        # Reserve 70% for model/KV cache
--context-length 131072          # 131K context (35B model)
--context-length 65536           # 65K context (122B model)
```

### Performance Tuning

```bash
--tp-size 1                      # Tensor parallelism (1 GPU)
--watchdog-timeout 1200          # Increase for large models
```

## Reasoning Modes

### Thinking Mode (Reasoning)

Enable with `--reasoning-parser qwen3`. The model generates `<think>` blocks:

```json
{
  "temperature": 1.0,
  "top_p": 0.95,
  "top_k": 20,
  "presence_penalty": 1.5
}
```

**Best for:** Complex reasoning, math, logic problems

### Non-Thinking Mode (Fast)

Default mode without thinking blocks:

```json
{
  "temperature": 0.7,
  "top_p": 0.8,
  "top_k": 20,
  "presence_penalty": 1.5
}
```

**Best for:** Chat, code generation, quick responses

## Tool Calling

Enable with `--tool-call-parser qwen3_coder`. Supports:
- Function definitions
- Parallel tool calls
- Tool execution results
- Multi-turn tool interactions

Example:
```python
response = requests.post('http://localhost:8001/v1/chat/completions', json={
    'model': 'Qwen/Qwen3.5-35B-A3B',
    'messages': [...],
    'tools': [
        {
            'type': 'function',
            'function': {
                'name': 'get_weather',
                'description': 'Get weather for a location',
                'parameters': {...}
            }
        }
    ]
})
```

## Performance Benchmarks

### DGX Spark (GB10, 128GB Unified Memory)

| Model | Precision | Speed | Memory | Context |
|-------|-----------|-------|--------|---------|
| 35B-A3B | BF16 | ~30 tok/s | 118GB | 131K |
| 35B-A3B | FP8 | ~50 tok/s | 80GB | 131K |
| 122B-A10B | FP4 | ~15 tok/s | 120GB | 65K |

**Note:** FP8 support requires additional setup. BF16 is recommended for stability.

## Memory Bandwidth Limitation

DGX Spark uses LPDDR5X with ~273 GB/s bandwidth. This is the bottleneck for inference speed, not compute. The ~30 tok/s for 35B-A3B BF16 is near the theoretical ceiling.

For higher throughput:
- Use quantized models (FP8/FP4)
- Reduce context length
- Use smaller batch sizes

## Model Selection Guide

**Choose Qwen3.5-35B-A3B if:**
- You want the best balance of speed and quality
- Running production workloads
- Need reliable, stable inference
- Memory efficiency matters

**Choose Qwen3.5-122B-A10B if:**
- You need maximum quality
- Speed is less critical
- Willing to use experimental FP4 quantization
- Complex reasoning tasks

**Avoid Qwen3.5-27B because:**
- Dense models are less efficient than MoE on this hardware
- 35B-A3B is faster and often better quality

## Supported Languages

- **Programming**: 358 languages (Python, JavaScript, Go, Rust, etc.)
- **Natural**: 201 languages and dialects

## Context Window

- **Native**: 256K tokens
- **Recommended**: 131K tokens (35B), 65K tokens (122B)
- **Extendable**: Up to 1M with YaRN (experimental)

## API Compatibility

Qwen3.5 with SGLang provides:
- **OpenAI-compatible API**: `/v1/chat/completions`, `/v1/completions`
- **Anthropic-compatible API**: Native support for Claude Code
- **Streaming**: Server-Sent Events (SSE)
- **Tool calling**: Function calling support

## Links

- [Qwen3.5 GitHub](https://github.com/QwenLM/Qwen3.5)
- [Qwen3.5 Blog](https://qwen.ai/blog?id=qwen3.5)
- [SGLang Documentation](https://docs.sglang.io/)
- [DGX Spark Playbooks](https://github.com/NVIDIA/dgx-spark-playbooks)
