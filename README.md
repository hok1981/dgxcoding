# Qwen3.5 on NVIDIA DGX Spark - Setup Guide

This repository contains setup scripts and configurations for running Qwen3.5 models on NVIDIA DGX Spark (128GB unified memory) and connecting them to Claude Code for AI-assisted coding.

**📡 Remote Access**: If running Claude Code on a different machine than the DGX Spark, see **[REMOTE_ACCESS.md](REMOTE_ACCESS.md)** for network configuration.

## Hardware Specifications

- **System**: NVIDIA DGX Spark
- **Memory**: 128GB unified (CPU + GPU shared)
- **Architecture**: Grace Blackwell (GB10 Superchip)
- **Capability**: Run models up to 200B parameters locally

## Qwen3.5 Models Overview

### Qwen3.5-122B-A10B ⭐ (Recommended)
- **Total Parameters**: 122B (10B active per token - MoE)
- **Memory Required**: ~76GB FP16 / ~106GB with full context
- **Performance**: Competes with commercial APIs (GPT-4 class)
- **Best For**: Maximum quality, complex reasoning, tool calling
- **Speed**: 8-15 tok/s on DGX Spark

### Qwen3.5-35B-A3B ⭐ (Recommended)
- **Total Parameters**: 35B (3B active per token - MoE)
- **Memory Required**: ~22GB FP16 / ~30GB with full context
- **Performance**: Excellent balance of speed and quality
- **Best For**: Fast inference with strong capabilities
- **Speed**: 100+ tok/s on high-end GPUs

### Qwen3.5-27B
- **Total Parameters**: 27B (dense model)
- **Memory Required**: ~17GB FP16 / ~24GB with full context
- **Performance**: Most accurate dense model
- **Best For**: When you need every parameter active
- **Speed**: 30-40 tok/s typical

## Features

All Qwen3.5 models support:
- **256K context window** (extendable to 1M with YaRN)
- **Hybrid reasoning** (thinking and non-thinking modes)
- **Tool calling** and function execution
- **358 programming languages**
- **Multimodal capabilities** (vision + language)
- **201 natural languages**

## Quick Start

### 1. Run Setup Script

```powershell
python setup_qwen35.py
```

This interactive script will:
- Check and install dependencies
- Install SGLang or vLLM serving framework
- Optionally download the model
- Create launch scripts
- Generate Claude Code configuration

### 2. Launch Model Server

Choose your preferred serving framework:

**SGLang (Recommended):**
```powershell
python launch_scripts/launch_qwen35_122b_sglang.py
```

**vLLM (Alternative):**
```powershell
python launch_scripts/launch_qwen35_122b_vllm.py
```

The server will start on `http://localhost:8001` with OpenAI-compatible API endpoints.

### 3. Configure Claude Code

**PowerShell:**
```powershell
$env:ANTHROPIC_BASE_URL = "http://localhost:8001/v1"
$env:ANTHROPIC_AUTH_TOKEN = "dummy"
```

**Bash/WSL:**
```bash
export ANTHROPIC_BASE_URL=http://localhost:8001/v1
export ANTHROPIC_AUTH_TOKEN=dummy
```

**VS Code Settings (settings.json):**
```json
{
  "claudeCode.environmentVariables": [
    {
      "name": "ANTHROPIC_BASE_URL",
      "value": "http://localhost:8001/v1"
    },
    {
      "name": "ANTHROPIC_AUTH_TOKEN",
      "value": "dummy"
    }
  ]
}
```

### 4. Use Claude Code with Local Model

```powershell
claude --model Qwen/Qwen3.5-122B-A10B
```

Or use the Claude Code interface in your IDE - it will automatically use the local model.

## Model Configuration

### Thinking Mode (for complex reasoning)

**General tasks:**
- temperature: 1.0
- top_p: 0.95
- top_k: 20
- presence_penalty: 1.5

**Precise coding:**
- temperature: 0.6
- top_p: 0.95
- top_k: 20
- presence_penalty: 0.0

### Non-Thinking Mode (for faster responses)

**General tasks:**
- temperature: 0.7
- top_p: 0.8
- top_k: 20
- presence_penalty: 1.5

**Reasoning tasks:**
- temperature: 1.0
- top_p: 0.95
- top_k: 20
- presence_penalty: 1.5

### Disable/Enable Thinking

**Disable thinking (PowerShell):**
```powershell
--chat-template-kwargs "{\"enable_thinking\":false}"
```

**Enable thinking (PowerShell):**
```powershell
--chat-template-kwargs "{\"enable_thinking\":true}"
```

## Testing the Setup

### Test Server Connection
```powershell
curl http://localhost:8001/v1/models
```

### Test with Python
```python
import requests

response = requests.get('http://localhost:8001/v1/models')
print(response.json())
```

### Test Completion
```python
import requests

response = requests.post(
    'http://localhost:8001/v1/chat/completions',
    json={
        'model': 'Qwen/Qwen3.5-122B-A10B',
        'messages': [
            {'role': 'user', 'content': 'Write a Python function to calculate fibonacci numbers'}
        ],
        'temperature': 0.7
    }
)
print(response.json()['choices'][0]['message']['content'])
```

## Advanced Configuration

### Multi-GPU Setup (if needed)

For the 397B model or faster inference, use tensor parallelism:

**SGLang:**
```bash
python -m sglang.launch_server \
  --model-path Qwen/Qwen3.5-397B-A17B \
  --port 8001 \
  --tp-size 2 \
  --context-length 262144 \
  --reasoning-parser qwen3
```

**vLLM:**
```bash
vllm serve Qwen/Qwen3.5-397B-A17B \
  --port 8001 \
  --tensor-parallel-size 2 \
  --max-model-len 262144 \
  --reasoning-parser qwen3
```

### Memory Optimization

If you encounter memory issues:

1. **Reduce context length:**
   ```bash
   --context-length 131072  # Use 128K instead of 256K
   ```

2. **Use KV cache quantization:**
   ```bash
   --cache-type-k q8_0 --cache-type-v q8_0
   ```

3. **Use FP8 quantized models:**
   - Download FP8 versions from Hugging Face (saves ~50% memory)

## Troubleshooting

### Server won't start
- Check if port 8001 is already in use
- Verify CUDA is available: `python -c "import torch; print(torch.cuda.is_available())"`
- Check memory usage: `nvidia-smi`

### Claude Code can't connect
- Verify server is running: `curl http://localhost:8001/v1/models`
- Check environment variables are set correctly
- Ensure no firewall blocking localhost:8001

### Slow inference
- Reduce context length if not needed
- Use smaller model (35B instead of 122B)
- Enable KV cache quantization
- Check if other processes are using GPU memory

### Gibberish output
- Context length might be too low - increase it
- Try: `--cache-type-k bf16 --cache-type-v bf16`
- Adjust temperature settings

## Model Comparison

| Model | Total Params | Active Params | Memory (FP16) | Speed | Best Use Case |
|-------|-------------|---------------|---------------|-------|---------------|
| 122B-A10B | 122B | 10B | ~76GB | 8-15 tok/s | Maximum quality, complex tasks |
| 35B-A3B | 35B | 3B | ~22GB | 100+ tok/s | Fast, high-quality coding |
| 27B | 27B | 27B | ~17GB | 30-40 tok/s | Dense, consistent quality |

## Resources

- [Qwen3.5 GitHub](https://github.com/QwenLM/Qwen3.5)
- [Qwen3.5 Blog](https://qwen.ai/blog?id=qwen3.5)
- [SGLang Documentation](https://github.com/sgl-project/sglang)
- [vLLM Documentation](https://github.com/vllm-project/vllm)
- [Claude Code Documentation](https://docs.anthropic.com/claude/docs)

## License

Qwen3.5 models are released under Apache 2.0 license.
