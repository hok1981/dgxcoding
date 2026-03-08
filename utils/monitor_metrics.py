#!/usr/bin/env python3
"""
Real-time monitoring of Qwen3.5 vLLM metrics
Displays tokens/sec, GPU memory, queue status, and more
"""

import requests
import time
import sys
from datetime import datetime

def fetch_metrics(url):
    """Fetch Prometheus metrics from vLLM"""
    try:
        response = requests.get(f"{url}/metrics", timeout=5)
        if response.status_code == 200:
            return response.text
    except Exception as e:
        print(f"Error fetching metrics: {e}")
    return None

def parse_metrics(metrics_text):
    """Parse Prometheus metrics into a dictionary"""
    metrics = {}
    for line in metrics_text.split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            parts = line.split(' ')
            if len(parts) >= 2:
                key = parts[0]
                value = float(parts[1])
                metrics[key] = value
    return metrics

def get_gpu_metrics(url):
    """Try to get NVIDIA DCGM or nvidia-smi GPU metrics"""
    # vLLM exposes GPU metrics via v1/extensions/gpu
    try:
        response = requests.get(f"{url}/v1/model_cards", timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def display_metrics(metrics):
    """Display parsed metrics in a nice format"""
    print("\033[2J\033[H")  # Clear screen
    print("=" * 70)
    print(f"Qwen3.5 Performance Monitor - {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 70)

    # Throughput metrics
    if 'vllm:prompt_tokens_total' in metrics:
        prompt_tokens = metrics['vllm:prompt_tokens_total']
        print(f"\nTokens Processed:")
        print(f"  Prompt tokens:     {int(prompt_tokens):,}")

    if 'vllm:generation_tokens_total' in metrics:
        gen_tokens = metrics['vllm:generation_tokens_total']
        print(f"  Generation tokens: {int(gen_tokens):,}")

    # Request latency
    if 'vllm:request_success_total' in metrics and 'vllm:time_to_first_token_seconds_sum' in metrics:
        req_count = metrics['vllm:request_success_total']
        ttft_sum = metrics['vllm:time_to_first_token_seconds_sum']
        ttft_count = metrics.get('vllm:time_to_first_token_seconds_count', 1)
        avg_ttft = ttft_sum / max(ttft_count, 1) * 1000
        print(f"\nLatency:")
        print(f"  Avg TTFT:          {avg_ttft:.1f}ms")

    # GPU Memory
    if 'vllm:gpu_cache_usage_perc' in metrics:
        gpu_cache = metrics['vllm:gpu_cache_usage_perc']
        print(f"\nGPU Memory:")
        print(f"  KV Cache Usage:    {gpu_cache:.1f}%")

    # Context length metrics
    if 'vllm:ep_total_num_tokens' in metrics:
        print(f"\nExecution:")
        print(f"  EP tokens:         {int(metrics['vllm:ep_total_num_tokens']):,}")

    # Calculate tokens/sec over time
    if hasattr(display_metrics, 'last_tokens'):
        current_tokens = display_metrics.last_tokens
        time_diff = time.time() - display_metrics.last_time
        if time_diff > 0:
            tokens_diff = current_tokens - display_metrics.last_tokens
            tokens_per_sec = tokens_diff / time_diff
            print(f"\nReal-time Speed:")
            print(f"  Tokens/sec:        {tokens_per_sec:.2f}")
            print(f"  Tokens/minute:     {tokens_per_sec * 60:.0f}")
    display_metrics.last_tokens = metrics.get('vllm:generation_tokens_total', 0)
    display_metrics.last_time = time.time()

    print("\n" + "=" * 70)
    print("Press Ctrl+C to stop")
    print("=" * 70)

def monitor_server(server_url, interval=2):
    """Main monitoring loop"""
    metrics_url = f"{server_url}/metrics"
    print(f"Monitoring {metrics_url}")
    print("Press Ctrl+C to exit\n")

    try:
        while True:
            metrics_text = fetch_metrics(metrics_url)
            if metrics_text:
                metrics = parse_metrics(metrics_text)
                display_metrics(metrics)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")

def main():
    if len(sys.argv) < 2:
        print("Usage: python monitor_metrics.py <server_url> [interval]")
        print()
        print("Examples:")
        print("  python monitor_metrics.py http://localhost:8002")
        print("  python monitor_metrics.py http://192.168.1.100:8002 1")
        sys.exit(1)

    server_url = sys.argv[1]
    interval = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0

    # Ensure URL has proper format
    if not server_url.endswith('/'):
        server_url += '/'

    # Test connection first
    try:
        response = requests.get(f"{server_url}health", timeout=5)
        if response.status_code != 200:
            print(f"Warning: Health check returned {response.status_code}")
    except Exception as e:
        print(f"Error: Cannot connect to {server_url}: {e}")
        sys.exit(1)

    monitor_server(server_url, interval)

if __name__ == "__main__":
    main()
