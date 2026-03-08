# Performance Monitoring for Qwen3.5 on DGX Spark

This guide covers how to monitor and measure the performance of Qwen3.5 models running on DGX Spark.

## Quick Start

### 1. Performance Test (One-shot)

Measure tokens/second with a test prompt:

```bash
# On DGX Spark (local)
python utils/test_performance.py http://localhost:8002

# From client machine (remote)
python utils/test_performance.py http://<DGX_SPARK_IP>:8002
```

Output example:
```
PERFORMANCE METRICS
======================================================================
Tokens/second:    42.15
Tokens/minute:    2529.00
Time/tok:         23.7ms

Rating: EXCELLENT (35B-A3B expected: 30-50 tok/s)
```

### 2. Real-time Monitoring

Live dashboard showing tokens/sec, GPU memory, and latency:

```bash
# On DGX Spark (local)
python utils/monitor_metrics.py http://localhost:8002

# From client machine (remote)
python utils/monitor_metrics.py http://<DGX_SPARK_IP>:8002
```

Press `Ctrl+C` to exit. Updates every 2 seconds by default.

### 3. Prometheus Metrics

vLLM exposes Prometheus metrics at `/metrics`. Access directly:

```bash
# View raw Prometheus metrics
curl http://localhost:8002/metrics

# Or use Grafana/Prometheus to scrape and visualize
```

## Key Metrics

### Tokens Throughput
- `vllm:prompt_tokens_total` - Total prompt tokens processed
- `vllm:generation_tokens_total` - Total generated tokens
- `vllm:time_to_first_token_seconds_sum` - Cumulative TTFT

### Latency
- `vllm:time_to_first_token_seconds` - Time to first token (TTFT)
- `vllm:time_per_output_token_seconds` - Time per output token (TPOT)

### GPU Memory
- `vllm:gpu_cache_usage_perc` - GPU KV cache usage percentage
- `vllm:gpu_cache_usage_perc` - Should stay below 80% for stability

### Request Stats
- `vllm:request_success_total` - Successful requests
- `vllm:request_failure_total` - Failed requests
- `vllm:num_requests_running` - Currently processing requests

## Docker Configuration

vLLM metrics are enabled by default with these flags:

```yaml
--enable-metrics
--metrics-port 8001
--metrics-interval 1
```

## Performance Benchmarks

### Qwen3.5-35B-A3B (Expected)
- **Tokens/sec**: 30-50 tok/s (varies with context length)
- **TTFT**: 50-200ms
- **TPOT**: 20-30ms per token
- **Context**: Up to 262K tokens

### Qwen3.5-122B-A10B (Experimental)
- **Tokens/sec**: 15-25 tok/s
- **TTFT**: 100-500ms
- **TPOT**: 40-60ms per token
- **Context**: Up to 128K tokens

## Troubleshooting

### Low Tokens/Second

1. **Check GPU memory**: `docker exec qwen35-35b nvidia-smi`
2. **Reduce context length**: Lower `--max-model-len` if using excessive memory
3. **Reduce GPU utilization**: Lower `--gpu-memory-utilization` to 0.70
4. **Check for concurrent loads**: Multiple requests slow down individual responses

### High TTFT

1. **First request penalty**: First request after idle time is slower
2. **KV cache fragmentation**: Restart container if cache usage is high
3. **Network latency**: Measure from client with `ping <DGX_IP>`

### OOM Errors

Reduce `--gpu-memory-utilization`:
```yaml
--gpu-memory-utilization 0.70
```

## Grafana Dashboard (Optional)

For advanced visualization, set up Grafana + Prometheus:

1. Install Prometheus on DGX Spark
2. Configure scrape job for `localhost:8001/metrics`
3. Import vLLM dashboard template (ID: 16003)

## Example Outputs

### test_performance.py

```
======================================================================
Qwen3.5 Performance Test
======================================================================
[1/4] Measuring Time to First Token (TTFT)...
✓ Total time: 5.23s
  Prompt tokens: 45
  Completion tokens: 256

======================================================================
PERFORMANCE METRICS
======================================================================
Tokens/second:    48.95
Tokens/minute:    2937.00
Time/tok:         20.4ms

Rating: EXCELLENT (35B-A3B expected: 30-50 tok/s)
```

### monitor_metrics.py

```
======================================================================
Qwen3.5 Performance Monitor - 14:32:15
======================================================================

Tokens Processed:
  Prompt tokens:     1,245
  Generation tokens: 8,567

Latency:
  Avg TTFT:          125.3ms

GPU Memory:
  KV Cache Usage:    45.2%

Real-time Speed:
  Tokens/sec:        42.15
  Tokens/minute:     2529

======================================================================
```
