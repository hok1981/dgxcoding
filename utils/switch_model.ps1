# Model switching utility for Qwen3.5 and other models (PowerShell version)
# Handles stopping current model and starting requested one

param(
    [Parameter(Position=0)]
    [string]$Model
)

$ProjectDir = Split-Path -Parent $PSScriptRoot

# Available models
$Models = @{
    "35b" = "qwen35-35b"
    "122b" = "qwen35-122b"
    "deepseek" = "deepseek-v32-speciale"
}

function Show-Usage {
    Write-Host "Usage: .\switch_model.ps1 <model>" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Available models:"
    Write-Host "  35b      - Qwen3.5-35B-A3B (30-50 tok/s, 262K context)"
    Write-Host "  122b     - Qwen3.5-122B-A10B (15-25 tok/s, 65K context)"
    Write-Host "  deepseek - DeepSeek-V3.2-Speciale (30-40 tok/s, 32K context, #1 coding)"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\switch_model.ps1 35b    # Switch to 35B model"
    Write-Host "  .\switch_model.ps1 122b   # Switch to 122B model"
    Write-Host ""
    Write-Host "Current status:" -ForegroundColor Cyan
    Push-Location $ProjectDir
    docker compose ps
    Pop-Location
}

function Stop-AllModels {
    Write-Host "Stopping all running models..." -ForegroundColor Yellow
    Push-Location $ProjectDir
    docker compose down
    Pop-Location
    Write-Host "✓ All models stopped" -ForegroundColor Green
}

function Start-Model {
    param([string]$ModelKey)
    
    $ServiceName = $Models[$ModelKey]
    
    if (-not $ServiceName) {
        Write-Host "Error: Unknown model '$ModelKey'" -ForegroundColor Red
        Show-Usage
        exit 1
    }
    
    Write-Host "Starting $ServiceName..." -ForegroundColor Yellow
    Push-Location $ProjectDir
    
    # Start the model (with profile if needed)
    if ($ModelKey -eq "122b") {
        docker compose --profile large up -d $ServiceName
    } else {
        docker compose up -d $ServiceName
    }
    
    Pop-Location
    Write-Host "✓ $ServiceName started" -ForegroundColor Green
    Write-Host ""
    Write-Host "Monitor startup with:"
    Write-Host "  docker logs -f $ServiceName"
    Write-Host ""
    Write-Host "Or use the status checker:"
    Write-Host "  bash ./utils/check_status.sh"
}

# Main logic
if (-not $Model) {
    Show-Usage
    exit 1
}

# Special commands
switch ($Model.ToLower()) {
    "status" {
        Show-Usage
        exit 0
    }
    "list" {
        Show-Usage
        exit 0
    }
    "stop" {
        Stop-AllModels
        exit 0
    }
}

# Validate model exists
if (-not $Models.ContainsKey($Model)) {
    Write-Host "Error: Unknown model '$Model'" -ForegroundColor Red
    Show-Usage
    exit 1
}

# Stop all models first
Stop-AllModels
Write-Host ""

# Start requested model
Start-Model $Model

# Show next steps
Write-Host ""
Write-Host "Model switch complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Wait for model to load (~2-15 minutes depending on model)"
Write-Host "  2. Check status: bash ./utils/check_status.sh"
Write-Host "  3. Monitor metrics: python utils/monitor_metrics.py"
