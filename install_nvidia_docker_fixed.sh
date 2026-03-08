#!/bin/bash
# Install NVIDIA Container Toolkit for Docker GPU support
# Updated for DGX systems

set -e

echo "Detecting system information..."
. /etc/os-release
echo "OS: $NAME $VERSION"
echo "ID: $ID"
echo "VERSION_ID: $VERSION_ID"

echo ""
echo "Installing NVIDIA Container Toolkit..."

# Use the official installation method
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Update package list
sudo apt-get update

# Install nvidia-container-toolkit
sudo apt-get install -y nvidia-container-toolkit

# Configure Docker to use NVIDIA runtime
sudo nvidia-ctk runtime configure --runtime=docker

# Restart Docker
sudo systemctl restart docker

echo ""
echo "✓ NVIDIA Container Toolkit installed successfully!"
echo ""
echo "Testing GPU access in Docker..."
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

echo ""
echo "✓ GPU access confirmed!"
echo ""
echo "You can now run: docker-compose up -d qwen35-35b"
