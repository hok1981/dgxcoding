# Remote Access Setup

Connect Claude Code running on your client machine to Qwen3.5 running on DGX Spark.

## Architecture

```
┌─────────────────────┐         Network          ┌─────────────────────┐
│  Client Machine     │◄──────────────────────►│  DGX Spark Server   │
│                     │                          │                     │
│  - Claude Code      │    HTTP API (8000)      │  - Qwen3.5 Model    │
│  - Your IDE         │                          │  - vLLM Server      │
│  - Development      │                          │  - 128GB Memory     │
└─────────────────────┘                          └─────────────────────┘
```

## Server Setup (DGX Spark)

### 1. Start the Model

```bash
# Start Qwen3.5-35B
docker-compose up -d qwen35-35b

# Verify it's running
docker ps
docker logs -f qwen35-35b
```

### 2. Get Server IP Address

```bash
hostname -I | awk '{print $1}'
# Example output: 192.168.1.100
```

### 3. Configure Firewall

```bash
# Allow port 8000 for remote connections
sudo ufw allow 8000/tcp

# Or if using firewalld
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

### 4. Verify Server is Listening

```bash
# Check port is bound to all interfaces (0.0.0.0)
sudo netstat -tlnp | grep 8000
# Should show: 0.0.0.0:8000 (not 127.0.0.1:8000)

# Test locally
curl http://localhost:8000/v1/models
```

## Client Setup (Your Development Machine)

### 1. Test Connectivity

```bash
# Test network connection
curl http://192.168.1.100:8001/v1/models

# Or use the test script
python utils/test_connection.py 192.168.1.100
```

### 2. Configure Claude Code

**PowerShell:**
```powershell
$env:ANTHROPIC_BASE_URL = "http://192.168.1.100:8000/v1"
$env:ANTHROPIC_AUTH_TOKEN = "dummy"
```

**Bash/WSL:**
```bash
export ANTHROPIC_BASE_URL=http://192.168.1.100:8000/v1
export ANTHROPIC_AUTH_TOKEN=dummy
```

**VS Code Settings (settings.json):**
```json
{
  "claudeCode.environmentVariables": [
    {
      "name": "ANTHROPIC_BASE_URL",
      "value": "http://192.168.1.100:8000/v1"
    },
    {
      "name": "ANTHROPIC_AUTH_TOKEN",
      "value": "dummy"
    }
  ]
}
```

### 3. Use Claude Code

```bash
claude --model qwen3.5-35b
```

## Network Configuration

### Static IP (Recommended)

Set a static IP on your DGX Spark to avoid IP changes:

```bash
# Edit netplan configuration
sudo nano /etc/netplan/01-netcfg.yaml
```

Example configuration:
```yaml
network:
  version: 2
  ethernets:
    eth0:
      addresses:
        - 192.168.1.100/24
      gateway4: 192.168.1.1
      nameservers:
        addresses: [8.8.8.8, 8.8.4.4]
```

Apply:
```bash
sudo netplan apply
```

### Using Hostname

Add hostname to `/etc/hosts` on client machine:
```
192.168.1.100  dgx-spark
```

Then use:
```bash
export ANTHROPIC_BASE_URL=http://dgx-spark:8001/v1
```

## Security Options

### Option 1: Trusted Network (Simplest)

If both machines are on the same trusted network:
- Use HTTP (no encryption)
- Simple firewall rule
- **Recommended for**: Home lab, internal corporate network

### Option 2: SSH Tunnel (Secure)

For untrusted networks or internet access:

**On client machine:**
```bash
# Create SSH tunnel
ssh -L 8000:localhost:8000 user@dgx-spark-ip

# In another terminal, use localhost
export ANTHROPIC_BASE_URL=http://localhost:8000/v1
```

**Benefits:**
- Encrypted connection
- No firewall changes needed
- Works over internet

### Option 3: Reverse Proxy with HTTPS

For production deployments, use nginx with SSL:

```nginx
server {
    listen 443 ssl;
    server_name dgx-spark.local;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Performance Expectations

| Network | Latency Impact | Throughput Impact |
|---------|---------------|-------------------|
| Same machine | 0ms | None |
| Gigabit LAN | +1-5ms | Minimal |
| WiFi 6 | +5-20ms | Slight |
| VPN | +10-50ms | Moderate |
| Internet | +50-200ms | Significant |

**Recommendation**: Use wired gigabit connection for best experience.

## Troubleshooting

### Can't Connect from Client

**1. Verify server is running:**
```bash
# On DGX Spark
docker ps | grep qwen
docker logs qwen35-35b
```

**2. Test from DGX Spark itself:**
```bash
curl http://localhost:8001/v1/models
```

**3. Check firewall:**
```bash
sudo ufw status
# Should show: 8000/tcp ALLOW
```

**4. Test network connectivity:**
```bash
# From client
ping 192.168.1.100
telnet 192.168.1.100 8000
```

**5. Verify server bound to correct interface:**
```bash
# On DGX Spark
sudo netstat -tlnp | grep 8000
# Should show: 0.0.0.0:8000 (not 127.0.0.1:8000)
```

### Slow Performance

**1. Check network bandwidth:**
```bash
# Install iperf3
sudo apt install iperf3

# On server
iperf3 -s

# On client
iperf3 -c 192.168.1.100
```

**2. Use wired connection:**
- Avoid WiFi if possible
- 1Gbps+ recommended

**3. Check server load:**
```bash
# On DGX Spark
nvidia-smi
docker stats qwen35-35b
```

### Connection Refused

**Check if port is exposed:**
```bash
# In docker-compose.yml, verify:
ports:
  - "0.0.0.0:8001:8001"  # Correct
  # NOT "127.0.0.1:8001:8001"
```

## Multiple Clients

The server can handle multiple concurrent clients:
- SGLang supports continuous batching
- Efficient request scheduling
- Monitor with: `docker stats qwen35-35b`

## Quick Reference

### Server Side (DGX Spark)
```bash
# Start
docker-compose up -d qwen35-35b

# Get IP
hostname -I | awk '{print $1}'

# Open firewall
sudo ufw allow 8000/tcp

# Check status
docker logs -f qwen35-35b
```

### Client Side
```bash
# Set environment (replace IP)
export ANTHROPIC_BASE_URL=http://192.168.1.100:8000/v1
export ANTHROPIC_AUTH_TOKEN=dummy

# Test
curl http://192.168.1.100:8000/v1/models

# Use
claude --model qwen3.5-35b
```
