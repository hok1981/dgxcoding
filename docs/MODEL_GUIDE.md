# Model Guide — DGX Spark

All models run via TRT-LLM (`nvcr.io/nvidia/tensorrt-llm/release:1.2.0rc6`) in NVFP4
quantization on the GB10 Blackwell GPU. NVFP4 gives ~3.5x memory reduction vs BF16
and ~65% higher tok/s by activating Blackwell-native tensor cores.

---

## Quick Comparison

| Model | Type | Active Params | Port | Profile | Best For |
|---|---|---|---|---|---|
| Qwen3-30B-A3B-NVFP4 | MoE | 3B | 8002 | `qwen3a3b` | Fast general purpose, coding |
| Qwen3-32B-NVFP4 | Dense | 32B | 8003 | `qwen332b` | Deep reasoning, complex tasks |
| Phi-4-reasoning-plus-NVFP4 | Dense | ~14B | 8004 | `phi4` | Math, logic, low latency |
| Llama-3.3-70B-Instruct-NVFP4 | Dense | 70B | 8005 | `llama3370b` | General purpose, widest compat |
| DeepSeek-V3.2-NVFP4 | MoE | ~37B | 8006 | `deepseek` | Coding, technical, math |
| Nemotron-3-Super-120B-A12B-NVFP4 | MoE | 12B | 8007 | `nemotron120b` | Highest quality ceiling |
| Kimi-K2.5 | MoE | — | 8008 | `kimi` | Long context ⚠️ pending TRT-LLM 1.3.x |

---

## Model Details

### Qwen3-30B-A3B-NVFP4
**Publisher:** Alibaba (NVIDIA NVFP4 quant)
**Architecture:** Mixture of Experts — 30B total, **3B active per token**

**Strengths:**
- Fastest model in the lineup — low active parameter count means high tok/s
- Best multilingual capability (Alibaba-trained, strong non-English)
- Good coding and instruction following
- Very memory-efficient — fits easily even at long contexts

**Weaknesses:**
- MoE routing adds overhead at very low batch sizes
- Shallower reasoning than dense models of similar "size"

**Recommended for:** High-throughput workloads, interactive coding assistant,
multilingual tasks, default everyday model.

---

### Qwen3-32B-NVFP4
**Publisher:** Alibaba (NVIDIA NVFP4 quant)
**Architecture:** Dense — **32B active per token**

**Strengths:**
- All 32B parameters contribute to every token — deeper reasoning than A3B
- More consistent output quality (no MoE routing variability)
- Strong at multi-step logic, structured output, and complex code

**Weaknesses:**
- Slower than A3B (higher compute per token)
- Higher memory bandwidth usage

**Recommended for:** Complex reasoning chains, tasks where output quality
matters more than throughput, A/B comparison against the A3B variant.

---

### Phi-4-reasoning-plus-NVFP4
**Publisher:** Microsoft (NVIDIA NVFP4 quant)
**Architecture:** Dense — ~**14B active parameters**

**Strengths:**
- Smallest and fastest model — very low first-token latency
- Specifically fine-tuned for chain-of-thought reasoning
- Exceptional at math, logic puzzles, and structured problem solving
- Punches well above its weight class on reasoning benchmarks

**Weaknesses:**
- Smaller knowledge base than 30B+ models
- Can struggle with open-ended creative or knowledge-heavy tasks
- Less capable at very long context tasks

**Recommended for:** Math problems, logic tasks, structured output generation,
fast prototyping, latency-sensitive applications.

---

### Llama-3.3-70B-Instruct-NVFP4
**Publisher:** Meta (NVIDIA NVFP4 quant)
**Architecture:** Dense — **70B active parameters**

**Strengths:**
- Most widely benchmarked model — well-understood behaviour
- Largest ecosystem: most evals, tools, and fine-tunes target Llama
- Excellent general-purpose instruction following
- Strong at writing, summarization, and analysis

**Weaknesses:**
- Highest compute and memory cost of the dense models
- Lower tok/s than MoE models in the same quality tier
- No specialisation — DeepSeek beats it at coding, Phi-4 at math

**Recommended for:** General assistant tasks, writing, summarization,
production baseline, when you need well-known benchmark characteristics.

---

### DeepSeek-V3.2-NVFP4
**Publisher:** DeepSeek (NVIDIA NVFP4 quant)
**Architecture:** Mixture of Experts — ~671B total, **~37B active per token**

**Strengths:**
- State-of-the-art coding — consistently tops coding benchmarks
- Excellent at algorithms, math, and technical problem solving
- MoE efficiency gives solid tok/s despite large total parameter count
- Strong at multi-file reasoning, refactoring, and debugging

**Weaknesses:**
- Largest download in the lineup
- Can be verbose and over-engineer simple solutions
- Less strong at open-ended creative writing

**Recommended for:** Code generation, code review, debugging, algorithm
design, any task where correctness and technical depth matter most.

---

### Nemotron-3-Super-120B-A12B-NVFP4
**Publisher:** NVIDIA
**Architecture:** Mixture of Experts — 120B total, **12B active per token**

**Strengths:**
- NVIDIA's own flagship — optimised and tested on DGX Spark hardware
- Used internally as a teacher model for distillation (highest quality ceiling)
- Strong instruction following and enterprise-grade reliability
- MoE efficiency keeps tok/s reasonable despite 120B total params
- Officially supported and benchmarked on this exact hardware

**Weaknesses:**
- Less community benchmarking than Llama or DeepSeek
- Fewer fine-tunes and third-party tools built around it
- Large total parameter download

**Recommended for:** Tasks requiring maximum quality, enterprise workloads,
NVIDIA's own recommended model for this hardware.

---

### Kimi-K2.5 ⚠️ Pending
**Publisher:** Moonshot AI
**Architecture:** MoE
**Status:** Requires TRT-LLM v1.3.0rc7+ — check nvcr.io for availability

**Strengths:**
- Extremely long context window (128K+ tokens natively)
- Strong at document analysis and long-form reasoning
- Good multilingual capability

**Weaknesses:**
- Least battle-tested of the lineup on DGX Spark
- TRT-LLM support only just added in v1.3.0rc7

**Recommended for:** Long document summarisation, multi-document Q&A,
tasks that exceed the 32K context of other models.

---

## Choosing a Model

```
Need fast responses?           → Phi-4-reasoning-plus or Qwen3-30B-A3B
Writing code?                  → DeepSeek-V3.2 > Qwen3-32B > Llama-3.3-70B
Math / logic?                  → Phi-4-reasoning-plus > DeepSeek-V3.2
General assistant?             → Llama-3.3-70B or Qwen3-30B-A3B
Highest quality ceiling?       → Nemotron-120B or DeepSeek-V3.2
Long documents (>32K tokens)?  → Kimi-K2.5 (when available)
Multilingual?                  → Qwen3-30B-A3B or Qwen3-32B
```

---

## Starting a Model

```bash
# Start one model
docker compose --profile <profile> up -d

# Stop it
docker compose --profile <profile> down

# Check status
bash utils/check_status.sh

# Run inference test on all models sequentially
bash utils/test_models.sh

# Test specific models
bash utils/test_models.sh qwen3a3b deepseek phi4
```

---

## Performance Notes

All figures are approximate on DGX Spark (GB10, 128GB unified memory, 273 GB/s bandwidth).

| Model | Expected tok/s (NVFP4) |
|---|---|
| Phi-4-reasoning-plus | ~100–120 |
| Qwen3-30B-A3B | ~70–80 |
| Qwen3-32B | ~50–60 |
| Llama-3.3-70B | ~35–45 |
| DeepSeek-V3.2 | ~30–40 |
| Nemotron-120B | ~40–50 |

Memory bandwidth is the primary bottleneck on DGX Spark. NVFP4 reduces
weight size by ~3.5x, which directly multiplies throughput vs BF16.

---

## Why NVFP4 + TRT-LLM

- **NVFP4** is a Blackwell-native 4-bit floating point format — activates
  dedicated tensor cores unavailable to older quantisation formats
- **TRT-LLM** is NVIDIA's officially supported inference runtime for DGX Spark,
  compiled natively for SM121 (no PTX JIT fallback)
- Together they give the best performance achievable on this hardware
