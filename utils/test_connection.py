#!/usr/bin/env python3
"""
Test remote connection to Qwen3.5 server on DGX Spark
Run this from your client/development machine
"""

import requests
import sys
import time

def test_remote_connection(server_ip, port=8001):
    """Test connection to remote Qwen3.5 server"""
    
    base_url = f"http://{server_ip}:{port}"
    
    print("=" * 70)
    print(f"Testing Remote Connection to Qwen3.5 Server")
    print(f"Server: {base_url}")
    print("=" * 70)
    
    # Test 1: Basic connectivity
    print("\n[1/5] Testing basic connectivity...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        print(f"✓ Server is reachable (status: {response.status_code})")
    except requests.exceptions.ConnectionError:
        print(f"✗ Cannot connect to {base_url}")
        print("\nTroubleshooting steps:")
        print("1. Verify server IP address is correct")
        print("2. Check if server is running on DGX Spark")
        print("3. Verify firewall allows port 8001")
        print("4. Test with: Test-NetConnection -ComputerName {server_ip} -Port {port}")
        return False
    except requests.exceptions.Timeout:
        print(f"✗ Connection timeout - server may be slow or unreachable")
        return False
    
    # Test 2: Models endpoint
    print("\n[2/5] Testing /v1/models endpoint...")
    try:
        response = requests.get(f"{base_url}/v1/models", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Models endpoint working")
            if 'data' in data:
                for model in data['data']:
                    print(f"  Available model: {model.get('id', 'unknown')}")
        else:
            print(f"✗ Models endpoint returned status: {response.status_code}")
    except Exception as e:
        print(f"✗ Models endpoint failed: {e}")
        return False
    
    # Test 3: Simple completion
    print("\n[3/5] Testing simple completion...")
    try:
        start = time.time()
        response = requests.post(
            f"{base_url}/v1/chat/completions",
            json={
                "model": "Qwen/Qwen3.5-122B-A10B",
                "messages": [{"role": "user", "content": "Say 'Connection successful!'"}],
                "max_tokens": 20
            },
            timeout=30
        )
        elapsed = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            content = data['choices'][0]['message']['content']
            print(f"✓ Completion successful ({elapsed:.2f}s)")
            print(f"  Response: {content}")
        else:
            print(f"✗ Completion failed: {response.status_code}")
            print(f"  Response: {response.text}")
    except Exception as e:
        print(f"✗ Completion failed: {e}")
        return False
    
    # Test 4: Network latency
    print("\n[4/5] Testing network latency...")
    latencies = []
    for i in range(5):
        try:
            start = time.time()
            requests.get(f"{base_url}/health", timeout=5)
            latency = (time.time() - start) * 1000
            latencies.append(latency)
        except:
            pass
    
    if latencies:
        avg_latency = sum(latencies) / len(latencies)
        print(f"✓ Average latency: {avg_latency:.1f}ms")
        
        if avg_latency < 10:
            print("  Network quality: Excellent (same machine or very fast LAN)")
        elif avg_latency < 50:
            print("  Network quality: Good (LAN)")
        elif avg_latency < 100:
            print("  Network quality: Fair (WiFi or slow LAN)")
        else:
            print("  Network quality: Poor (may impact performance)")
    
    # Test 5: Claude Code compatibility
    print("\n[5/5] Testing Claude Code compatibility...")
    print(f"\nTo use with Claude Code, set these environment variables:")
    print(f"\nPowerShell:")
    print(f'  $env:ANTHROPIC_BASE_URL = "{base_url}/v1"')
    print(f'  $env:ANTHROPIC_AUTH_TOKEN = "dummy"')
    print(f"\nBash/WSL:")
    print(f'  export ANTHROPIC_BASE_URL={base_url}/v1')
    print(f'  export ANTHROPIC_AUTH_TOKEN=dummy')
    print(f"\nThen run:")
    print(f'  claude --model Qwen/Qwen3.5-122B-A10B')
    
    print("\n" + "=" * 70)
    print("✓ All tests passed! Remote connection is working.")
    print("=" * 70)
    
    return True

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_remote_connection.py <DGX_SPARK_IP> [port]")
        print("\nExample:")
        print("  python test_remote_connection.py 192.168.1.100")
        print("  python test_remote_connection.py 192.168.1.100 8001")
        sys.exit(1)
    
    server_ip = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8001
    
    success = test_remote_connection(server_ip, port)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
