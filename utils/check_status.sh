#!/bin/bash
# Check if Qwen3.5 model is running and ready

echo "Checking Qwen3.5 Model Status"
echo "=============================="

# Check if container is running
echo ""
echo "[1/5] Checking if container is running..."
if docker ps | grep -q qwen35; then
    CONTAINER=$(docker ps | grep qwen35 | awk '{print $NF}')
    echo "✓ Container '$CONTAINER' is running"
else
    echo "✗ No Qwen3.5 container is running"
    echo ""
    echo "Start a container with:"
    echo "  docker-compose up -d qwen35-35b"
    echo "  or"
    echo "  docker-compose up -d qwen35-122b"
    exit 1
fi

# Check container logs for startup status
echo ""
echo "[2/5] Checking container logs..."
if docker logs $CONTAINER 2>&1 | tail -20 | grep -q "Server started"; then
    echo "✓ Server has started successfully"
elif docker logs $CONTAINER 2>&1 | tail -20 | grep -q "error\|Error\|ERROR"; then
    echo "✗ Server encountered errors:"
    docker logs $CONTAINER 2>&1 | tail -10
    exit 1
else
    echo "⚠ Server is still starting up..."
    echo "Recent logs:"
    docker logs $CONTAINER 2>&1 | tail -5
    echo ""
    echo "Wait a moment and check logs with:"
    echo "  docker logs -f $CONTAINER"
fi

# Check if port is listening
echo ""
echo "[3/5] Checking if API port is listening..."
if netstat -tlnp 2>/dev/null | grep -q :8002 || ss -tlnp 2>/dev/null | grep -q :8002; then
    echo "✓ Port 8002 is listening"
else
    echo "✗ Port 8002 is not listening yet"
    echo "Server may still be loading the model..."
fi

# Test health endpoint
echo ""
echo "[4/5] Testing health endpoint..."
if curl -s -f http://localhost:8002/health > /dev/null 2>&1; then
    echo "✓ Health endpoint responding"
else
    echo "⚠ Health endpoint not responding yet"
fi

# Test models endpoint
echo ""
echo "[5/5] Testing models API endpoint..."
MODELS_RESPONSE=$(curl -s http://localhost:8002/v1/models 2>/dev/null)
if [ ! -z "$MODELS_RESPONSE" ]; then
    echo "✓ Models API is responding"
    echo ""
    echo "Available models:"
    echo "$MODELS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$MODELS_RESPONSE"
else
    echo "⚠ Models API not responding yet"
    echo ""
    echo "The model may still be loading. This can take several minutes."
    echo "Monitor progress with:"
    echo "  docker logs -f $CONTAINER"
    exit 0
fi

# Get server IP
echo ""
echo "=============================="
echo "✓ Model is UP and READY!"
echo "=============================="
echo ""
SERVER_IP=$(hostname -I | awk '{print $1}')
echo "Server IP: $SERVER_IP"
echo ""
echo "Test from this machine:"
echo "  curl http://localhost:8002/v1/models"
echo ""
echo "Test from client machine:"
echo "  curl http://$SERVER_IP:8002/v1/models"
echo ""
echo "Configure Claude Code on client:"
echo "  export ANTHROPIC_BASE_URL=http://$SERVER_IP:8002"
echo "  export ANTHROPIC_AUTH_TOKEN=dummy"
echo "  claude --model qwen3.5-35b"
echo ""
echo "Monitor logs:"
echo "  docker logs -f $CONTAINER"
echo ""
echo "Check GPU usage:"
echo "  nvidia-smi"
echo ""
echo "Real-time monitoring:"
echo "  python utils/monitor_metrics.py http://$SERVER_IP:8002"
echo ""
echo "Performance test:"
echo "  python utils/test_performance.py http://$SERVER_IP:8002"
