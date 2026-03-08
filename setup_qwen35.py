#!/usr/bin/env python3
"""
Qwen3.5 Model Setup Script for NVIDIA DGX Spark
Supports: 122B-A10B, 35B-A3B, 27B models
"""

import subprocess
import sys
import os
from pathlib import Path

MODELS = {
    "122b": {
        "name": "Qwen/Qwen3.5-122B-A10B",
        "memory": "~76GB (FP16)",
        "description": "Largest model - best performance, competes with commercial APIs",
        "recommended": True
    },
    "35b": {
        "name": "Qwen/Qwen3.5-35B-A3B",
        "memory": "~22GB (FP16)",
        "description": "MoE model - excellent balance of speed and quality",
        "recommended": True
    },
    "27b": {
        "name": "Qwen/Qwen3.5-27B",
        "memory": "~17GB (FP16)",
        "description": "Dense model - most accurate for single-GPU",
        "recommended": False
    }
}

def check_dependencies():
    """Check if required packages are installed"""
    print("Checking dependencies...")
    
    required = ["torch", "transformers", "huggingface_hub"]
    missing = []
    
    for package in required:
        try:
            __import__(package)
            print(f"✓ {package} installed")
        except ImportError:
            missing.append(package)
            print(f"✗ {package} missing")
    
    if missing:
        print(f"\nInstalling missing packages: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
    
    return True

def install_serving_framework(framework="sglang"):
    """Install SGLang or vLLM for model serving"""
    print(f"\nInstalling {framework}...")
    
    if framework == "sglang":
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "sglang[all]", "--upgrade"
        ])
    elif framework == "vllm":
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "vllm", "--upgrade"
        ])
    
    print(f"✓ {framework} installed successfully")

def download_model(model_id):
    """Download model from Hugging Face"""
    print(f"\nDownloading {model_id}...")
    print("This may take a while depending on your internet connection...")
    
    from huggingface_hub import snapshot_download
    
    try:
        local_dir = snapshot_download(
            repo_id=model_id,
            local_dir=f"./models/{model_id.split('/')[-1]}",
            local_dir_use_symlinks=False
        )
        print(f"✓ Model downloaded to: {local_dir}")
        return local_dir
    except Exception as e:
        print(f"✗ Error downloading model: {e}")
        return None

def create_launch_scripts(model_key):
    """Create launch scripts for SGLang and vLLM"""
    model_info = MODELS[model_key]
    model_name = model_info["name"]
    
    # SGLang launch script
    sglang_script = f"""#!/usr/bin/env python3
# Launch Qwen3.5-{model_key.upper()} with SGLang

import subprocess
import sys

cmd = [
    sys.executable, "-m", "sglang.launch_server",
    "--model-path", "{model_name}",
    "--port", "8001",
    "--host", "0.0.0.0",
    "--tp-size", "1",
    "--context-length", "262144",
    "--reasoning-parser", "qwen3",
    "--trust-remote-code"
]

print("Starting SGLang server...")
print(" ".join(cmd))
subprocess.run(cmd)
"""
    
    # vLLM launch script
    vllm_script = f"""#!/usr/bin/env python3
# Launch Qwen3.5-{model_key.upper()} with vLLM

import subprocess
import sys

cmd = [
    "vllm", "serve", "{model_name}",
    "--port", "8001",
    "--host", "0.0.0.0",
    "--tensor-parallel-size", "1",
    "--max-model-len", "262144",
    "--reasoning-parser", "qwen3",
    "--trust-remote-code"
]

print("Starting vLLM server...")
print(" ".join(cmd))
subprocess.run(cmd)
"""
    
    # Save scripts
    Path("launch_scripts").mkdir(exist_ok=True)
    
    sglang_path = Path(f"launch_scripts/launch_qwen35_{model_key}_sglang.py")
    vllm_path = Path(f"launch_scripts/launch_qwen35_{model_key}_vllm.py")
    
    sglang_path.write_text(sglang_script)
    vllm_path.write_text(vllm_script)
    
    print(f"\n✓ Launch scripts created:")
    print(f"  - {sglang_path}")
    print(f"  - {vllm_path}")
    
    return sglang_path, vllm_path

def create_claude_code_config():
    """Create configuration for Claude Code integration"""
    config = """# Claude Code Configuration for Qwen3.5

## Environment Variables (PowerShell)
$env:ANTHROPIC_BASE_URL = "http://localhost:8001/v1"
$env:ANTHROPIC_AUTH_TOKEN = "dummy"

## Environment Variables (Bash/WSL)
export ANTHROPIC_BASE_URL=http://localhost:8001/v1
export ANTHROPIC_AUTH_TOKEN=dummy

## Usage
# After setting environment variables, run:
claude --model Qwen/Qwen3.5-122B-A10B

## VS Code Settings
# Add to your VS Code settings.json:
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

## Testing the Connection
# Test with curl:
curl http://localhost:8001/v1/models

# Or with Python:
python -c "import requests; print(requests.get('http://localhost:8001/v1/models').json())"
"""
    
    config_path = Path("claude_code_config.md")
    config_path.write_text(config)
    print(f"\n✓ Claude Code configuration saved to: {config_path}")
    return config_path

def main():
    print("=" * 60)
    print("Qwen3.5 Setup for NVIDIA DGX Spark (128GB Unified Memory)")
    print("=" * 60)
    
    print("\nAvailable models:")
    for key, info in MODELS.items():
        star = " ⭐" if info["recommended"] else ""
        print(f"\n{key.upper()}{star}")
        print(f"  Model: {info['name']}")
        print(f"  Memory: {info['memory']}")
        print(f"  Description: {info['description']}")
    
    print("\n" + "=" * 60)
    choice = input("\nWhich model would you like to set up? (122b/35b/27b): ").lower()
    
    if choice not in MODELS:
        print(f"Invalid choice. Please choose from: {', '.join(MODELS.keys())}")
        return
    
    print(f"\nSetting up Qwen3.5-{choice.upper()}...")
    
    # Check dependencies
    check_dependencies()
    
    # Choose serving framework
    print("\nAvailable serving frameworks:")
    print("1. SGLang (recommended - faster, better tool calling)")
    print("2. vLLM (alternative - more mature)")
    framework_choice = input("Choose framework (1/2): ").strip()
    
    framework = "sglang" if framework_choice == "1" else "vllm"
    install_serving_framework(framework)
    
    # Ask about model download
    download = input("\nDownload model now? (y/n): ").lower()
    if download == 'y':
        download_model(MODELS[choice]["name"])
    
    # Create launch scripts
    create_launch_scripts(choice)
    
    # Create Claude Code config
    create_claude_code_config()
    
    print("\n" + "=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print("\nNext steps:")
    print(f"1. Launch the model server:")
    print(f"   python launch_scripts/launch_qwen35_{choice}_{framework}.py")
    print("\n2. In a new terminal, set environment variables (see claude_code_config.md)")
    print("\n3. Test the connection:")
    print("   curl http://localhost:8001/v1/models")
    print("\n4. Use with Claude Code:")
    print(f"   claude --model {MODELS[choice]['name']}")
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
