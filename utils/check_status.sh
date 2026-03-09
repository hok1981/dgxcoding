#!/bin/bash
# Check if any LLM model is running and ready

echo "Checking LLM Model Status"
echo "=========================="

# Check if container is running
echo ""
echo "[1/5] Checking if container is running..."

# Look for any of our model containers
CONTAINER=$(docker ps --filter "name=qwen35-35b" --filter "name=qwen35-122b" --filter "name=deepseek-v32-speciale" --filter "name=kimi-k25" --filter "name=mimo-v2-flash" --format "{{.Names}}" | head -1)

if [ -n "$CONTAINER" ]; then
    echo "✓ Container '$CONTAINER' is running"
else
    echo "✗ No model container is running"
    echo ""
    echo "Start a container with:"
    echo "  ./utils/switch_model.sh 35b       # Qwen3.5-35B"
    echo "  ./utils/switch_model.sh deepseek  # DeepSeek-V3.2-Speciale"
    echo "  ./utils/switch_model.sh kimi      # Kimi-K2.5"
    echo "  ./utils/switch_model.sh mimo      # MiMo-V2-Flash"
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

# Get the external port for this container
PORT=$(docker port $CONTAINER 8000 2>/dev/null | cut -d: -f2)

if [ -n "$PORT" ]; then
    if netstat -tlnp 2>/dev/null | grep -q :$PORT || ss -tlnp 2>/dev/null | grep -q :$PORT; then
        echo "✓ Port $PORT is listening"
    else
        echo "✗ Port $PORT is not listening yet"
        echo "Server may still be loading the model..."
    fi
else
    echo "⚠ Could not determine port mapping"
fi

# Test health endpoint
echo ""
echo "[4/5] Testing health endpoint..."
if [ -n "$PORT" ]; then
    if curl -s -f http://localhost:$PORT/health > /dev/null 2>&1; then
        echo "✓ Health endpoint responding"
    else
        echo "⚠ Health endpoint not responding yet"
    fi
else
    echo "⚠ Skipping health check (port unknown)"
fi

# Test models endpoint
echo ""
echo "[5/5] Testing models API endpoint..."
if [ -n "$PORT" ]; then
    MODELS_RESPONSE=$(curl -s http://localhost:$PORT/v1/models 2>/dev/null)
else
    MODELS_RESPONSE=""
fi
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
echo "Container: $CONTAINER"
if [ -n "$PORT" ]; then
    echo "Port: $PORT"
    echo "Server IP: $SERVER_IP"
    echo ""
    echo "Test from this machine:"
    echo "  curl http://localhost:$PORT/v1/models"
    echo ""
    echo "Test from client machine:"
    echo "  curl http://$SERVER_IP:$PORT/v1/models"
    echo ""
    echo "Configure Claude Code on client:"
    echo "  export ANTHROPIC_BASE_URL=http://$SERVER_IP:$PORT"
    echo "  export ANTHROPIC_AUTH_TOKEN=dummy"
    echo "  claude --model <model-name>"
else
    echo "Server IP: $SERVER_IP"
    echo ""
    echo "⚠ Port information unavailable"
fi
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
