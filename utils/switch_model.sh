#!/usr/bin/env bash
# Model switching utility for Qwen3.5 and other models
# Handles stopping current model and starting requested one

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Available models (using case statement instead of associative array for sh compatibility)
get_service_name() {
    case "$1" in
        35b) echo "qwen35-35b" ;;
        122b) echo "qwen35-122b" ;;
        deepseek) echo "deepseek-v32-speciale" ;;
        *) echo "" ;;
    esac
}

show_usage() {
    echo "Usage: $0 <model>"
    echo ""
    echo "Available models:"
    echo "  35b      - Qwen3.5-35B-A3B (30-50 tok/s, 262K context)"
    echo "  122b     - Qwen3.5-122B-A10B (15-25 tok/s, 65K context)"
    echo "  deepseek - DeepSeek-V3.2-Speciale (30-40 tok/s, 32K context, #1 coding)"
    echo ""
    echo "Examples:"
    echo "  $0 35b    # Switch to 35B model"
    echo "  $0 122b   # Switch to 122B model"
    echo ""
    echo "Current status:"
    docker compose -f "$PROJECT_DIR/docker-compose.yml" ps
}

stop_all_models() {
    echo -e "${YELLOW}Stopping all running models...${NC}"
    cd "$PROJECT_DIR"
    docker compose down
    echo -e "${GREEN}✓ All models stopped${NC}"
}

start_model() {
    local model_key=$1
    local service_name=$(get_service_name "$model_key")
    
    if [ -z "$service_name" ]; then
        echo -e "${RED}Error: Unknown model '$model_key'${NC}"
        show_usage
        exit 1
    fi
    
    echo -e "${YELLOW}Starting $service_name...${NC}"
    cd "$PROJECT_DIR"
    
    # Start the model (with profile if needed)
    if [ "$model_key" == "122b" ]; then
        docker compose --profile large up -d "$service_name"
    else
        docker compose up -d "$service_name"
    fi
    
    echo -e "${GREEN}✓ $service_name started${NC}"
    echo ""
    echo "Monitor startup with:"
    echo "  docker logs -f $service_name"
    echo ""
    echo "Or use the status checker:"
    echo "  ./utils/check_status.sh"
}

main() {
    if [ $# -eq 0 ]; then
        show_usage
        exit 1
    fi
    
    local model=$1
    
    # Special commands
    case $model in
        status|list)
            show_usage
            exit 0
            ;;
        stop)
            stop_all_models
            exit 0
            ;;
    esac
    
    # Validate model exists
    if [ -z "$(get_service_name "$model")" ]; then
        echo -e "${RED}Error: Unknown model '$model'${NC}"
        show_usage
        exit 1
    fi
    
    # Stop all models first
    stop_all_models
    echo ""
    
    # Start requested model
    start_model "$model"
    
    # Show next steps
    echo ""
    echo -e "${GREEN}Model switch complete!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Wait for model to load (~2-15 minutes depending on model)"
    echo "  2. Check status: ./utils/check_status.sh"
    echo "  3. Monitor metrics: python utils/monitor_metrics.py"
}

main "$@"
