#!/usr/bin/env python3
"""
Test Qwen3.5 model performance and measure tokens/sec
Run this from client machine or directly on DGX Spark
"""

import requests
import time
import json
import sys

def measure_performance(server_url, model, max_tokens=256, prompt=None):
    """Measure model performance in tokens/second"""

    # Default prompt if not provided
    if prompt is None:
        prompt = """Write a detailed explanation of how neural networks learn patterns from data.
Include information about forward propagation, backpropagation, gradient descent,
and how weights are updated during training."""

    print("=" * 70)
    print("Qwen3.5 Performance Test")
    print("=" * 70)
    print(f"Server: {server_url}")
    print(f"Model: {model}")
    print(f"Max tokens: {max_tokens}")
    print()

    # Test 1: Time to first token (TTFT)
    print("[1/4] Measuring Time to First Token (TTFT)...")
    start = time.time()
    response = requests.post(
        f"{server_url}/v1/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 256,
            "stream": False
        },
        timeout=300
    )
    total_time = time.time() - start

    if response.status_code != 200:
        print(f"✗ Request failed: {response.status_code}")
        print(response.text)
        return

    data = response.json()
    content = data['choices'][0]['message']['content']
    prompt_tokens = data['usage']['prompt_tokens']
    completion_tokens = data['usage']['completion_tokens']

    # TTFT (first token arrival) - approximated by time to first response
    # For accurate TTFT, use streaming mode
    print(f"✓ Total time: {total_time:.2f}s")
    print(f"  Prompt tokens: {prompt_tokens}")
    print(f"  Completion tokens: {completion_tokens}")

    # Performance metrics
    if completion_tokens > 0:
        tokens_per_second = completion_tokens / total_time
        tokens_per_minute = tokens_per_second * 60
        print()
        print("=" * 70)
        print("PERFORMANCE METRICS")
        print("=" * 70)
        print(f"Tokens/second:    {tokens_per_second:.2f}")
        print(f"Tokens/minute:    {tokens_per_minute:.2f}")
        print(f"Time/tok:         {1000/tokens_per_second:.1f}ms")
        print()

        # Performance rating
        if tokens_per_second >= 40:
            print("Rating: EXCELLENT (35B-A3B expected: 30-50 tok/s)")
        elif tokens_per_second >= 25:
            print("Rating: GOOD (35B-A3B expected: 30-50 tok/s)")
        elif tokens_per_second >= 15:
            print("Rating: FAIR")
        else:
            print("Rating: SLOW (check GPU memory and context length)")
        print()

    # Test 2: Streaming tokens/sec
    print("[2/4] Measuring streaming tokens/sec...")
    stream_start = time.time()
    tokens_received = 0
    first_token_time = None

    response = requests.post(
        f"{server_url}/v1/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 256,
            "stream": True,
            "stream_options": {"include_usage": True}
        },
        timeout=300,
        stream=True
    )

    if response.status_code == 200:
        for chunk in response.iter_lines():
            if chunk:
                chunk_str = chunk.decode('utf-8')
                if chunk_str.startswith('data: '):
                    try:
                        line_data = json.loads(chunk_str[6:])
                        if 'choices' in line_data and len(line_data['choices']) > 0:
                            if not line_data['choices'][0]['finish_reason']:
                                tokens_received += 1
                                if first_token_time is None:
                                    first_token_time = time.time() - stream_start
                    except:
                        pass

        stream_time = time.time() - stream_start
        if stream_time > 0:
            stream_tps = tokens_received / stream_time
            print(f"✓ Streaming tokens/sec: {stream_tps:.2f}")
            print(f"  Tokens received: {tokens_received}")
            print(f"  Time to first token: {first_token_time:.3f}s" if first_token_time else "  No tokens received")
    else:
        print(f"✗ Streaming failed: {response.status_code}")

    # Test 3: Model info
    print()
    print("[3/4] Fetching model info...")
    response = requests.get(f"{server_url}/v1/models", timeout=10)
    if response.status_code == 200:
        models = response.json()['data']
        for model_info in models:
            print(f"  Model ID: {model_info['id']}")
            print(f"  Created: {model_info['created']}")

    # Test 4: System info
    print()
    print("[4/4] System information...")
    response = requests.get(f"{server_url}/v1/model_cards", timeout=10)
    if response.status_code == 200:
        print("✓ System endpoints available")

    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total completion tokens: {completion_tokens}")
    if completion_tokens > 0:
        print(f"Avg tokens/second: {tokens_per_second:.2f}")
        print(f"Total time: {total_time:.2f}s")
        print()
        print("Note: Performance varies based on:")
        print("  - Context length (longer context = slower)")
        print("  - GPU memory availability")
        print("  - Model size (35B vs 122B)")
        print("  - Concurrent requests")

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_performance.py <server_url> [model] [max_tokens]")
        print()
        print("Examples:")
        print("  python test_performance.py http://localhost:8002")
        print("  python test_performance.py http://192.168.1.100:8002 qwen3.5-35b 512")
        print()
        print("Default model: qwen3.5-35b")
        sys.exit(1)

    server_url = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "qwen3.5-35b"
    max_tokens = int(sys.argv[3]) if len(sys.argv) > 3 else 256

    measure_performance(server_url, model, max_tokens)

if __name__ == "__main__":
    main()
