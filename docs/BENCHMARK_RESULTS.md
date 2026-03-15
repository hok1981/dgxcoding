# Benchmark Results

Hardware: DGX Spark — Grace Blackwell GB10, 128 GiB unified memory
Runtime: TensorRT-LLM 1.2.0rc6, NVFP4 quantization
Test prompt: one-sentence Pythagorean theorem summary (`/no_think`)

---

## 2026-03-14

| Model                              | Status             | RAM +GiB | Peak GiB | min free GiB | tok/s |
|------------------------------------|--------------------|----------|----------|--------------|-------|
| Qwen3-30B-A3B-NVFP4                | OK                 | 32.2     | 36.0     | —            | 39.5  |
| Qwen3-32B-NVFP4                    | OK                 | 29.6     | 34.0     | —            | 8.2   |
| Phi-4-reasoning-plus-NVFP4         | OK                 | 21.4     | 25.1     | —            | 20.1  |
| Llama-3.3-70B-Instruct-NVFP4       | OK                 | 63.5     | 67.2     | —            | 3.2   |
| DeepSeek-V3.2-NVFP4                | KILLED_BY_WATCHDOG | —        | —        | < 8.0        | —     |
| Nemotron-3-Super-120B-A12B-NVFP4   | KILLED_BY_WATCHDOG | —        | —        | < 8.0        | —     |
| Kimi-K2.5                          | TIMEOUT            | —        | —        | —            | —     |

### Notes

- **Qwen3-A3B**: Much lower tok/s than expected (39.5 vs 70–80). Likely still running in
  thinking mode despite `/no_think` — worth retesting with explicit `enable_thinking: false`
  if TRT-LLM supports it.
- **Qwen3-32B**: 8.2 tok/s is very low for a 32B model (expected 50–60). Same suspicion as above.
- **Phi-4**: 20.1 tok/s below expected 100–120. Reasoning model, likely same issue.
- **Llama-3.3-70B**: 3.2 tok/s is unexpectedly low for 70B (expected 35–45). May indicate
  memory pressure or suboptimal KV cache config.
- **DeepSeek-V3.2**: Killed by OOM watchdog. Model is a ~671B MoE — at NVFP4 (0.5 bytes/param)
  weights alone require ~335 GiB, far exceeding the 128 GiB system. Unlikely to run without
  expert offloading support in TRT-LLM.
- **Nemotron-120B**: Killed by OOM watchdog. 120B params × 0.5 bytes ≈ 60 GiB weights.
  Should theoretically fit, but KV cache + activation buffers push it over. Try
  `free_gpu_memory_fraction: 0.50` and a model-specific config if needed.
- **Kimi-K2.5**: Timeout — requires TRT-LLM 1.3.x (not yet released).

### Actionable next steps

1. Re-run speed tests once thinking-mode suppression is confirmed working
2. Try Nemotron with reduced `free_gpu_memory_fraction: 0.50` in a dedicated config
3. DeepSeek-V3.2 is almost certainly too large for 128 GiB — wait for TRT-LLM expert
   offloading support or a distilled variant
4. Investigate Llama tok/s — 3.2 is a 10× regression from spec
