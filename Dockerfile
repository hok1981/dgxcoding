FROM nvidia/cuda:12.1.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

ENV ANTHROPIC_BASE_URL=http://localhost:8001/v1
ENV ANTHROPIC_AUTH_TOKEN=dummy

CMD ["python3", "-m", "sglang.launch_server", \
     "--model-path", "Qwen/Qwen3.5-122B-A10B", \
     "--port", "8001", \
     "--host", "0.0.0.0", \
     "--tp-size", "1", \
     "--context-length", "262144", \
     "--reasoning-parser", "qwen3", \
     "--trust-remote-code"]
