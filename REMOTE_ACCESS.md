# Remote Access Configuration for Qwen3.5

## Architecture

```
┌─────────────────────┐         Network          ┌─────────────────────┐
│  Client Machine     │◄──────────────────────►│  DGX Spark Server   │
│                     │                          │                     │
│  - Claude Code      │    HTTP/HTTPS API       │  - Qwen3.5 Model    │
│  - Your IDE         │    (Port 8001)          │  - SGLang/vLLM      │
│  - Development      │                          │  - 128GB Memory     │
└─────────────────────┘                          └─────────────────────┘
```

## Server Configuration (DGX Spark)

### 1. Update Server Launch to Accept Remote Connections

The server must bind to `0.0.0.0` (all interfaces) instead of `localhost`:

**SGLang (already configured):**
```bash
python -m sglang.launch_server \
  --model-path Qwen/Qwen3.5-122B-A10B \
  --port 8001 \
  --host 0.0.0.0 \
  --tp-size 1 \
  --context-length 262144 \
  --reasoning-parser qwen3 \
  --trust-remote-code
```

**vLLM:**
```bash
vllm serve Qwen/Qwen3.5-122B-A10B \
  --port 8001 \
  --host 0.0.0.0 \
  --tensor-parallel-size 1 \
  --max-model-len 262144 \
  --reasoning-parser qwen3 \
  --trust-remote-code
```

### 2. Firewall Configuration (DGX Spark)

**Windows Firewall:**
```powershell
# Allow inbound connections on port 8001
New-NetFirewallRule -DisplayName "Qwen3.5 API Server" `
  -Direction Inbound `
  -LocalPort 8001 `
  -Protocol TCP `
  -Action Allow
```

**Check if port is listening:**
```powershell
netstat -an | findstr :8001
```

### 3. Docker Configuration for Remote Access

Update `docker-compose.yml` to bind to all interfaces (already configured):

```yaml
services:
  qwen35-122b:
    ports:
      - "0.0.0.0:8001:8001"  # Bind to all interfaces
```

Or use Docker run:
```powershell
docker run -d `
  --name qwen35-122b `
  --gpus all `
  -p 0.0.0.0:8001:8001 `
  -v ${PWD}/models:/app/models `
  --shm-size 32g `
  qwen35:latest
```

## Client Configuration (Your Development Machine)

### 1. Find DGX Spark IP Address

On DGX Spark, run:
```powershell
# Get IP address
ipconfig

# Or for specific adapter
(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike "*Loopback*"}).IPAddress
```

Example output: `192.168.1.100`

### 2. Test Connection from Client

```powershell
# Test connectivity
curl http://192.168.1.100:8001/v1/models

# Or with PowerShell
Invoke-RestMethod -Uri "http://192.168.1.100:8001/v1/models"
```

### 3. Configure Claude Code on Client Machine

**PowerShell:**
```powershell
$env:ANTHROPIC_BASE_URL = "http://192.168.1.100:8001/v1"
$env:ANTHROPIC_AUTH_TOKEN = "dummy"
```

**Bash/WSL:**
```bash
export ANTHROPIC_BASE_URL=http://192.168.1.100:8001/v1
export ANTHROPIC_AUTH_TOKEN=dummy
```

**VS Code Settings (settings.json):**
```json
{
  "claudeCode.environmentVariables": [
    {
      "name": "ANTHROPIC_BASE_URL",
      "value": "http://192.168.1.100:8001/v1"
    },
    {
      "name": "ANTHROPIC_AUTH_TOKEN",
      "value": "dummy"
    }
  ]
}
```

### 4. Use Claude Code

```powershell
claude --model Qwen/Qwen3.5-122B-A10B
```

## Security Considerations

### Option 1: Trusted Network (Simplest)
If both machines are on the same trusted network:
- Use HTTP (no encryption needed)
- Simple firewall rule
- **Recommended for**: Home lab, internal corporate network

### Option 2: SSH Tunnel (Secure)
For untrusted networks or internet access:

**On client machine:**
```powershell
# Create SSH tunnel
ssh -L 8001:localhost:8001 user@dgx-spark-ip

# Then use localhost in Claude Code
$env:ANTHROPIC_BASE_URL = "http://localhost:8001/v1"
```

**Benefits:**
- Encrypted connection
- No firewall changes needed
- Works over internet

### Option 3: Reverse Proxy with HTTPS (Production)

**Install nginx on DGX Spark:**
```nginx
server {
    listen 443 ssl;
    server_name dgx-spark.local;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Client configuration:**
```powershell
$env:ANTHROPIC_BASE_URL = "https://dgx-spark.local/v1"
```

### Option 4: API Key Authentication

Add authentication middleware (custom script):

```python
# auth_proxy.py on DGX Spark
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)
VALID_API_KEY = "your-secret-key-here"

@app.route('/<path:path>', methods=['GET', 'POST'])
def proxy(path):
    api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
    
    if api_key != VALID_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    # Forward to actual server
    url = f"http://localhost:8001/{path}"
    resp = requests.request(
        method=request.method,
        url=url,
        headers={k:v for k,v in request.headers if k != 'Host'},
        data=request.get_data(),
        cookies=request.cookies,
        allow_redirects=False
    )
    
    return resp.content, resp.status_code

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8002)
```

**Client uses port 8002 with API key:**
```powershell
$env:ANTHROPIC_BASE_URL = "http://192.168.1.100:8002/v1"
$env:ANTHROPIC_AUTH_TOKEN = "your-secret-key-here"
```

## Network Troubleshooting

### Can't connect from client

**1. Verify server is running:**
```powershell
# On DGX Spark
netstat -an | findstr :8001
```

**2. Test from DGX Spark itself:**
```powershell
# On DGX Spark
curl http://localhost:8001/v1/models
```

**3. Check firewall:**
```powershell
# On DGX Spark - list firewall rules
Get-NetFirewallRule | Where-Object {$_.LocalPort -eq 8001}
```

**4. Test network connectivity:**
```powershell
# From client
Test-NetConnection -ComputerName 192.168.1.100 -Port 8001
```

**5. Check if server bound to correct interface:**
```powershell
# On DGX Spark
netstat -an | findstr :8001
# Should show: 0.0.0.0:8001 (not 127.0.0.1:8001)
```

### Slow performance over network

**1. Check network bandwidth:**
```powershell
# Use iperf3 or similar
iperf3 -s  # On server
iperf3 -c 192.168.1.100  # On client
```

**2. Enable compression (if supported):**
```python
# In client requests
headers = {'Accept-Encoding': 'gzip, deflate'}
```

**3. Use local network (avoid WiFi if possible)**
- Wired connection recommended
- 1Gbps+ network for best experience

## Performance Expectations

| Network | Latency Impact | Throughput Impact |
|---------|---------------|-------------------|
| Same machine | 0ms | None |
| Gigabit LAN | +1-5ms | Minimal |
| WiFi 6 | +5-20ms | Slight |
| VPN | +10-50ms | Moderate |
| Internet | +50-200ms | Significant |

**Recommendation**: Use wired gigabit connection between client and DGX Spark for best experience.

## Static IP Configuration (Recommended)

To avoid IP address changes:

**On DGX Spark:**
```powershell
# Set static IP
New-NetIPAddress -InterfaceAlias "Ethernet" `
  -IPAddress 192.168.1.100 `
  -PrefixLength 24 `
  -DefaultGateway 192.168.1.1

# Set DNS
Set-DnsClientServerAddress -InterfaceAlias "Ethernet" `
  -ServerAddresses ("8.8.8.8","8.8.4.4")
```

Or use hostname:
```powershell
# Client can use hostname instead of IP
$env:ANTHROPIC_BASE_URL = "http://dgx-spark:8001/v1"
```

## Multiple Client Support

The server can handle multiple concurrent clients:

- **SGLang**: Excellent concurrent request handling
- **vLLM**: Good concurrent request handling
- Both support continuous batching

**Monitoring concurrent usage:**
```powershell
# Check active connections
netstat -an | findstr :8001 | findstr ESTABLISHED
```

## Quick Reference

### Server Side (DGX Spark)
```powershell
# 1. Start server (bind to all interfaces)
docker-compose up -d qwen35-122b

# 2. Open firewall
New-NetFirewallRule -DisplayName "Qwen3.5 API" -Direction Inbound -LocalPort 8001 -Protocol TCP -Action Allow

# 3. Get IP address
ipconfig
```

### Client Side (Your Machine)
```powershell
# 1. Set environment variable (replace IP)
$env:ANTHROPIC_BASE_URL = "http://192.168.1.100:8001/v1"
$env:ANTHROPIC_AUTH_TOKEN = "dummy"

# 2. Test connection
curl http://192.168.1.100:8001/v1/models

# 3. Use Claude Code
claude --model Qwen/Qwen3.5-122B-A10B
```

## Recommended Setup

For your use case (separate machines, likely same network):

1. **Use Docker on DGX Spark** (already configured for remote access)
2. **Static IP or hostname** for DGX Spark
3. **Firewall rule** to allow port 8001
4. **HTTP is fine** if on trusted network
5. **SSH tunnel** if accessing over internet

This gives you clean separation, easy management, and good performance.
