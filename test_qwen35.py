#!/usr/bin/env python3
"""
Test script for Qwen3.5 local deployment
Tests server connectivity, model inference, and Claude Code compatibility
"""

import requests
import json
import time
import sys

SERVER_URL = "http://localhost:8001"

def test_server_health():
    """Test if server is running and responsive"""
    print("Testing server health...")
    try:
        response = requests.get(f"{SERVER_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✓ Server is healthy")
            return True
        else:
            print(f"✗ Server returned status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Server is not responding: {e}")
        return False

def test_models_endpoint():
    """Test /v1/models endpoint (OpenAI compatible)"""
    print("\nTesting /v1/models endpoint...")
    try:
        response = requests.get(f"{SERVER_URL}/v1/models", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✓ Models endpoint working")
            print(f"Available models: {json.dumps(data, indent=2)}")
            return True
        else:
            print(f"✗ Models endpoint returned status: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Models endpoint failed: {e}")
        return False

def test_simple_completion():
    """Test basic completion"""
    print("\nTesting simple completion...")
    
    payload = {
        "model": "Qwen/Qwen3.5-122B-A10B",  # Will use whatever model is loaded
        "messages": [
            {"role": "user", "content": "Say 'Hello, I am Qwen3.5!' and nothing else."}
        ],
        "temperature": 0.7,
        "max_tokens": 50
    }
    
    try:
        response = requests.post(
            f"{SERVER_URL}/v1/chat/completions",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            content = data['choices'][0]['message']['content']
            print("✓ Simple completion successful")
            print(f"Response: {content}")
            return True
        else:
            print(f"✗ Completion failed with status: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Completion request failed: {e}")
        return False

def test_coding_task():
    """Test coding capability"""
    print("\nTesting coding capability...")
    
    payload = {
        "model": "Qwen/Qwen3.5-122B-A10B",
        "messages": [
            {
                "role": "user", 
                "content": "Write a Python function to calculate the factorial of a number. Include docstring."
            }
        ],
        "temperature": 0.7,
        "max_tokens": 500
    }
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{SERVER_URL}/v1/chat/completions",
            json=payload,
            timeout=60
        )
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            content = data['choices'][0]['message']['content']
            tokens = data.get('usage', {}).get('completion_tokens', 0)
            
            print("✓ Coding task successful")
            print(f"Time: {elapsed:.2f}s")
            if tokens > 0:
                print(f"Tokens: {tokens} ({tokens/elapsed:.1f} tok/s)")
            print(f"\nGenerated code:\n{'-'*60}\n{content}\n{'-'*60}")
            return True
        else:
            print(f"✗ Coding task failed with status: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Coding task request failed: {e}")
        return False

def test_reasoning_mode():
    """Test reasoning/thinking mode"""
    print("\nTesting reasoning mode...")
    
    payload = {
        "model": "Qwen/Qwen3.5-122B-A10B",
        "messages": [
            {
                "role": "user",
                "content": "Solve this step by step: If a train travels 120 km in 2 hours, what is its average speed in m/s?"
            }
        ],
        "temperature": 1.0,
        "max_tokens": 1000
    }
    
    try:
        response = requests.post(
            f"{SERVER_URL}/v1/chat/completions",
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            content = data['choices'][0]['message']['content']
            print("✓ Reasoning task successful")
            print(f"\nReasoning output:\n{'-'*60}\n{content}\n{'-'*60}")
            
            # Check if thinking blocks are present
            if "<think>" in content or "step by step" in content.lower():
                print("✓ Model is showing reasoning process")
            return True
        else:
            print(f"✗ Reasoning task failed with status: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Reasoning task request failed: {e}")
        return False

def test_streaming():
    """Test streaming responses"""
    print("\nTesting streaming capability...")
    
    payload = {
        "model": "Qwen/Qwen3.5-122B-A10B",
        "messages": [
            {"role": "user", "content": "Count from 1 to 10."}
        ],
        "temperature": 0.7,
        "max_tokens": 100,
        "stream": True
    }
    
    try:
        response = requests.post(
            f"{SERVER_URL}/v1/chat/completions",
            json=payload,
            stream=True,
            timeout=30
        )
        
        if response.status_code == 200:
            print("✓ Streaming started")
            print("Stream output: ", end="", flush=True)
            
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data_str = line[6:]
                        if data_str.strip() == '[DONE]':
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data['choices'][0]['delta']
                            if 'content' in delta:
                                print(delta['content'], end="", flush=True)
                        except json.JSONDecodeError:
                            pass
            
            print("\n✓ Streaming completed successfully")
            return True
        else:
            print(f"✗ Streaming failed with status: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Streaming request failed: {e}")
        return False

def main():
    print("=" * 70)
    print("Qwen3.5 Local Deployment Test Suite")
    print("=" * 70)
    
    tests = [
        ("Server Health", test_server_health),
        ("Models Endpoint", test_models_endpoint),
        ("Simple Completion", test_simple_completion),
        ("Coding Task", test_coding_task),
        ("Reasoning Mode", test_reasoning_mode),
        ("Streaming", test_streaming)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"✗ {test_name} crashed: {e}")
            results[test_name] = False
        
        time.sleep(1)  # Brief pause between tests
    
    print("\n" + "=" * 70)
    print("Test Results Summary")
    print("=" * 70)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    total = len(results)
    passed = sum(results.values())
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Your Qwen3.5 setup is working correctly.")
        print("\nYou can now use Claude Code with your local model:")
        print("  claude --model Qwen/Qwen3.5-122B-A10B")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
