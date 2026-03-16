#!/usr/bin/env bash
# Start the voice home assistant stack:
#   - Nemotron-Nano-30B-A3B  (LLM,  port 8009)
#   - Parakeet-1.1B-CTC      (STT,  port 9000 / 50051)
#   - Wyoming Piper TTS      (TTS,  port 10200)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd "$PROJECT_DIR"

echo -e "${YELLOW}Stopping all running containers...${NC}"
docker compose down
echo ""

echo -e "${YELLOW}Starting voice assistant stack...${NC}"
docker compose \
  --profile nemotronnano \
  --profile parakeet \
  --profile piper \
  up -d

echo ""
echo -e "${GREEN}✓ Stack started${NC}"
echo ""
echo "Services:"
echo "  LLM (Nemotron-Nano)  →  http://localhost:8009/v1"
echo "  STT (Parakeet CTC)   →  http://localhost:9000  (gRPC: 50051)"
echo "  TTS (Wyoming Piper)  →  tcp://localhost:10200"
echo ""
echo "Nemotron-Nano takes ~5-15 min to load (CUDA graph compilation)."
echo "Watch startup:"
echo "  docker logs -f nemotron-nano"
echo "  docker logs -f parakeet-ctc"
echo ""
echo "Check readiness:"
echo "  ./utils/check_status.sh"
