#!/usr/bin/env python3
"""
Real-time monitoring of Qwen3.5 vLLM metrics
Displays active throughput, load visualizations (30s, 5min), and only shows metrics when active
"""

import requests
import time
import sys
from datetime import datetime
from collections import deque

# Store history for load visualization
# Each entry: (timestamp, prompt_tokens, generation_tokens)
history = deque(maxlen=300)  # 300 samples @ 2s interval = 10 minutes

# Track last active period for immediate display
last_active_period = None  # (start_time, start_prompt, start_gen, end_time, end_prompt, end_gen)

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
            if '{' in line:
                # Format: metric_name{label="value"} value
                # Split on first { to get metric name, last space to get value
                brace_pos = line.index('{')
                space_pos = line.rfind(' ')
                if space_pos > brace_pos:
                    key = line[:brace_pos]
                    try:
                        value = float(line[space_pos + 1:])
                        metrics[key] = value
                    except ValueError:
                        pass
                continue

            if '(' in line:
                # Format: metric_name(key="value") value
                paren_pos = line.index('(')
                space_pos = line.rfind(' ')
                if space_pos > paren_pos:
                    key = line[:paren_pos]
                    try:
                        value = float(line[space_pos + 1:])
                        metrics[key] = value
                    except ValueError:
                        pass
                continue

            # Simple format: metric_name value
            parts = line.rsplit(' ', 1)
            if len(parts) >= 2:
                try:
                    value = float(parts[1])
                    metrics[parts[0]] = value
                except ValueError:
                    pass
    return metrics

def detect_active_periods():
    """Detect all active periods in history and return stats + samples"""
    global last_active_period

    active_throughputs = []
    samples = []
    current_period = None
    last_active_info = None

    prev_time = None
    prev_prompt = None
    prev_gen = None

    for i, (ts, prompt, gen) in enumerate(history):
        if prev_time is not None:
            time_diff = ts - prev_time
            if time_diff > 0:
                prompt_diff = prompt - prev_prompt
                gen_diff = gen - prev_gen
                is_active = prompt_diff > 0 or gen_diff > 0

                if is_active:
                    total_diff = prompt_diff + gen_diff
                    tok_per_sec = total_diff / time_diff

                    # Track current activity period
                    if current_period is None:
                        current_period = {
                            'start_time': prev_time,
                            'start_prompt': prev_prompt,
                            'start_gen': prev_gen,
                            'tok_per_sec': tok_per_sec
                        }
                    else:
                        current_period['tok_per_sec'] = tok_per_sec

                    active_throughputs.append(tok_per_sec)
                    samples.append((tok_per_sec, ts))

                    # Track most recent active period
                    if last_active_info is None or ts > last_active_info['end_time']:
                        last_active_info = {
                            'tok_per_sec': tok_per_sec,
                            'start_time': current_period['start_time'],
                            'start_prompt': current_period['start_prompt'],
                            'start_gen': current_period['start_gen'],
                            'end_time': ts,
                            'end_prompt': prompt,
                            'end_gen': gen
                        }

                    # Update current period stats
                    current_period['end_time'] = ts
                    current_period['end_prompt'] = prompt
                    current_period['end_gen'] = gen
                    current_period['samples'] = current_period.get('samples', []) + [(tok_per_sec, ts)]

                prev_time = ts
                prev_prompt = prompt
                prev_gen = gen

    # Compute statistics
    if active_throughputs:
        avg_active = sum(active_throughputs) / len(active_throughputs)
        max_active = max(active_throughputs)
        min_active = min(active_throughputs)

        # Return the most recent complete active period info
        if last_active_info:
            last_active_info['avg_throughput'] = avg_active
            last_active_info['max_throughput'] = max_active
    else:
        avg_active = max_active = min_active = 0

    return avg_active, max_active, min_active, samples, last_active_info, current_period

def draw_bar(value, max_value, width=30, char='#'):
    """Draw a simple ASCII bar chart"""
    if max_value == 0:
        return '.' * width
    filled = int((value / max_value) * width)
    return char * filled + '.' * (width - filled)

def display_load_visualization(samples):
    """Display ASCII load visualization for last 30s and 5min"""
    if not samples:
        return

    now = time.time()

    # Extract active periods with timestamps
    active_periods = [(tok, ts) for tok, ts, _, _ in samples]

    # Last 30s activity
    recent = [t for t, ts in active_periods if (now - ts) <= 30]
    if recent:
        max_tok = max(recent) if recent else 1
        print(f"\n  Last 30s:  [{draw_bar(recent[-1], max(max_tok, 1), 30)}] {recent[-1]:.1f} t/s")

    # 5-minute trend (10 segments)
    last_5min = [t for t, ts in active_periods if (now - ts) <= 300]
    if len(last_5min) > 10:
        segment_size = len(last_5min) // 10
        segments = []
        for i in range(10):
            start = i * segment_size
            end = start + segment_size if i < 9 else len(last_5min)
            if start < len(last_5min):
                avg = sum(last_5min[start:end]) / max(end - start, 1)
                segments.append(avg)

        max_seg = max(segments) if segments else 1
        print(f"  Last 5min: ", end="")
        for seg in segments:
            bar_len = int((seg / max(max_seg, 1)) * 4)
            print("█" if bar_len > 0 else "░", end="")
        print()

def display_metrics(metrics, last_poll=None):
    """Display parsed metrics in a nice format - only active periods highlighted"""
    global last_active_period

    print("\033[2J\033[H")
    print("=" * 70)
    print(f"Qwen3.5 Performance Monitor - {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 70)

    # Store this sample
    curr_prompt = metrics.get('vllm:prompt_tokens_total', 0)
    curr_gen = metrics.get('vllm:generation_tokens_total', 0)
    history.append((time.time(), curr_prompt, curr_gen))

    # Overall totals
    print(f"\n  Tokens Processed (lifetime):")
    print(f"    Prompt tokens:     {int(curr_prompt):>12,}")
    print(f"    Generation tokens: {int(curr_gen):>12,}")
    print(f"    Total:             {int(curr_prompt + curr_gen):>12,}")

    # Detect active periods
    avg_active, max_active, min_active, samples, last_active, current_period = detect_active_periods()

    # Calculate instant rate since last poll
    instant_tps = 0
    instant_status = "IDLE"
    if last_poll is not None and hasattr(display_metrics, 'last_prompt') and hasattr(display_metrics, 'last_gen') and hasattr(display_metrics, 'last_time'):
        time_diff = time.time() - display_metrics.last_time
        prompt_diff = curr_prompt - display_metrics.last_prompt
        gen_diff = curr_gen - display_metrics.last_gen
        total_diff = prompt_diff + gen_diff
        if time_diff > 0 and total_diff > 0:
            instant_tps = total_diff / time_diff
            instant_status = "GENERATING" if instant_tps > 10 else "PROCESSING PROMPT"

    # Store state for next iteration
    display_metrics.last_prompt = curr_prompt
    display_metrics.last_gen = curr_gen
    display_metrics.last_time = time.time()

    # Show throughput for active periods
    print(f"\n  Throughput (during activity):")
    if avg_active > 0:
        print(f"    Avg:               {avg_active:>12.2f} t/s")
        print(f"    Max:               {max_active:>12.2f} t/s")
        print(f"    Min (during busy): {min_active:>12.2f} t/s")
    else:
        print(f"    (no activity detected in history)")

    # Show most recent active period or current activity
    if last_active:
        elapsed = time.time() - last_active['end_time']
        print(f"\n  Recent session:")
        duration = last_active['end_time'] - last_active['start_time']
        total_tokens = (last_active['end_prompt'] - last_active['start_prompt']) + \
                       (last_active['end_gen'] - last_active['start_gen'])
        print(f"    Duration:          {duration:.1f}s")
        print(f"    Tokens:            {total_tokens:,}")
        print(f"    Avg rate:          {last_active['avg_throughput']:.1f} t/s")
        print(f"    Ended:             {elapsed:.0f}s ago")

    # If currently active, show that
    if current_period and (time.time() - current_period.get('end_time', 0)) < 5:
        elapsed = time.time() - current_period['end_time']
        print(f"\n  Current session:")
        total_tokens = (curr_prompt - current_period.get('start_prompt', curr_prompt)) + \
                       (curr_gen - current_period.get('start_gen', curr_gen))
        print(f"    Active for:        {elapsed:.1f}s")
        print(f"    Tokens so far:     {total_tokens:,}")
        print(f"    Current rate:      {current_period['tok_per_sec']:.1f} t/s")

    # Draw load visualization
    display_load_visualization(samples)

    # Current instant status
    print(f"\n  Current:             {instant_status}")
    if instant_tps > 0:
        print(f"                    ({instant_tps:.1f} t/s right now)")

    # GPU Memory
    if 'vllm:gpu_cache_usage_perc' in metrics:
        gpu_cache = metrics['vllm:gpu_cache_usage_perc']
        print(f"\n  GPU Memory:")
        print(f"    KV Cache Usage:    {gpu_cache:.1f}% [{draw_bar(gpu_cache, 100, 20)}]")

    # Request latency
    if 'vllm:request_success_total' in metrics:
        req_count = metrics['vllm:request_success_total']
        print(f"\n  Requests completed:  {int(req_count):,}")

    if 'vllm:time_to_first_token_seconds_sum' in metrics:
        ttft_sum = metrics['vllm:time_to_first_token_seconds_sum']
        ttft_count = metrics.get('vllm:time_to_first_token_seconds_count', 1)
        avg_ttft = ttft_sum / max(ttft_count, 1) * 1000
        print(f"    Avg TTFT:          {avg_ttft:.1f}ms")

    print("\n" + "-" * 70)
    print("Press Ctrl+C to stop | Metrics shown during ACTIVE periods only")
    print("-" * 70)

def monitor_server(server_url, interval=2):
    """Main monitoring loop"""
    print(f"Monitoring {server_url}/metrics")
    print("Press Ctrl+C to exit\n")

    last_poll = None
    try:
        while True:
            metrics_text = fetch_metrics(server_url)
            if metrics_text:
                metrics = parse_metrics(metrics_text)
                display_metrics(metrics, last_poll)
                last_poll = metrics.get('vllm:prompt_tokens_total', 0)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")

def main():
    default_url = "http://192.168.68.40:8002"

    if len(sys.argv) < 2:
        server_url = default_url
        interval = 2.0
        print(f"Using default server: {server_url}")
        print("Usage: python monitor_metrics.py [server_url] [interval]")
        print()
    else:
        server_url = sys.argv[1]
        interval = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0

    if not server_url.startswith('http://') and not server_url.startswith('https://'):
        server_url = 'http://' + server_url

    server_url = server_url.rstrip('/')

    # Test connection first
    try:
        response = requests.get(f"{server_url}/health", timeout=5)
        if response.status_code != 200:
            print(f"Warning: Health check returned {response.status_code}")
    except Exception as e:
        print(f"Error: Cannot connect to {server_url}: {e}")
        sys.exit(1)

    monitor_server(server_url, interval)

if __name__ == "__main__":
    main()
