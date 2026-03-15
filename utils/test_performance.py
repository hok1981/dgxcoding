#!/usr/bin/env python3
"""
test_performance.py — proper tok/s benchmark for any model running on DGX Spark

Measures:
  - TTFT  (time to first token, via streaming)
  - Decode tok/s  (completion_tokens / (total_time - TTFT))
  - End-to-end tok/s  (completion_tokens / total_time)

Runs N iterations and reports mean ± stddev.

Usage:
  python utils/test_performance.py <port>
  python utils/test_performance.py <port> --runs 5 --tokens 2048
  python utils/test_performance.py <port> --prompt "Your custom prompt"
"""

import argparse
import json
import statistics
import sys
import time
import requests

DEFAULT_PROMPT = (
    "Write a detailed technical explanation of how the transformer architecture works. "
    "Cover self-attention, multi-head attention, positional encoding, feed-forward layers, "
    "layer normalization, and how encoder-decoder models differ from decoder-only models. "
    "Include concrete examples where helpful. /no_think"
)

def get_model_id(base_url: str) -> str:
    resp = requests.get(f"{base_url}/v1/models", timeout=10)
    resp.raise_for_status()
    return resp.json()["data"][0]["id"]

def run_once(base_url: str, model_id: str, prompt: str, max_tokens: int) -> dict:
    """Single streaming inference run. Returns ttft_s, decode_tps, e2e_tps, completion_tokens."""
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    t_start = time.perf_counter()
    t_first = None
    completion_tokens = 0

    with requests.post(
        f"{base_url}/v1/chat/completions",
        json=payload,
        stream=True,
        timeout=300,
    ) as resp:
        resp.raise_for_status()
        for raw in resp.iter_lines():
            if not raw:
                continue
            line = raw.decode("utf-8")
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue

            # Record time of first content token
            choices = chunk.get("choices", [])
            if t_first is None and choices:
                delta = choices[0].get("delta", {})
                if delta.get("content"):
                    t_first = time.perf_counter()

            # Pick up final usage from the last chunk
            usage = chunk.get("usage")
            if usage:
                completion_tokens = usage.get("completion_tokens", completion_tokens)

    t_end = time.perf_counter()

    total_s = t_end - t_start
    ttft_s = (t_first - t_start) if t_first else 0.0
    decode_s = total_s - ttft_s

    e2e_tps = completion_tokens / total_s if total_s > 0 else 0
    decode_tps = completion_tokens / decode_s if decode_s > 0 else 0

    return {
        "ttft_s": ttft_s,
        "decode_tps": decode_tps,
        "e2e_tps": e2e_tps,
        "completion_tokens": completion_tokens,
        "total_s": total_s,
    }

def fmt(values: list, unit: str = "") -> str:
    if len(values) == 1:
        return f"{values[0]:.2f}{unit}"
    mean = statistics.mean(values)
    stdev = statistics.stdev(values)
    return f"{mean:.2f}{unit}  ±{stdev:.2f}  (min {min(values):.2f}, max {max(values):.2f})"

def main():
    parser = argparse.ArgumentParser(description="DGX Spark model benchmark")
    parser.add_argument("port", type=int, help="Model port (e.g. 8002)")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--runs", type=int, default=3, help="Number of iterations (default: 3)")
    parser.add_argument("--tokens", type=int, default=2048, help="Max completion tokens (default: 2048)")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--json", action="store_true", help="Output results as single JSON line (suppresses human output)")
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}"

    if not args.json:
        print(f"Connecting to {base_url} ...")
    try:
        model_id = get_model_id(base_url)
    except Exception as e:
        print(f"ERROR: Could not reach model API — {e}", file=sys.stderr)
        sys.exit(1)

    if not args.json:
        print(f"Model   : {model_id}")
        print(f"Tokens  : up to {args.tokens}")
        print(f"Runs    : {args.runs}")
        print()

    results = []
    for i in range(args.runs):
        if not args.json:
            print(f"  Run {i+1}/{args.runs} ... ", end="", flush=True)
        else:
            print(f"  run {i+1}/{args.runs}...", end="", flush=True, file=sys.stderr)
        r = run_once(base_url, model_id, args.prompt, args.tokens)
        results.append(r)
        if not args.json:
            print(f"{r['completion_tokens']} tokens  |  TTFT {r['ttft_s']:.2f}s  |  decode {r['decode_tps']:.1f} tok/s")
        else:
            print(f" {r['decode_tps']:.1f} tok/s", file=sys.stderr)

    if args.json:
        import json as _json
        def _mean(key): return statistics.mean(r[key] for r in results)
        def _stdev(key): return statistics.stdev(r[key] for r in results) if len(results) > 1 else 0.0
        print(_json.dumps({
            "model": model_id,
            "runs": args.runs,
            "tokens": args.tokens,
            "ttft_s": round(_mean("ttft_s"), 3),
            "ttft_stdev": round(_stdev("ttft_s"), 3),
            "decode_tps": round(_mean("decode_tps"), 1),
            "decode_stdev": round(_stdev("decode_tps"), 1),
            "e2e_tps": round(_mean("e2e_tps"), 1),
            "completion_tokens": round(_mean("completion_tokens")),
        }))
        return

    print()
    print("=" * 60)
    print(f"  Model        : {model_id}")
    print(f"  TTFT         : {fmt([r['ttft_s'] for r in results], 's')}")
    print(f"  Decode tok/s : {fmt([r['decode_tps'] for r in results])}")
    print(f"  E2E tok/s    : {fmt([r['e2e_tps'] for r in results])}")
    print(f"  Tokens gen   : {fmt([r['completion_tokens'] for r in results])}")
    print("=" * 60)

if __name__ == "__main__":
    main()
