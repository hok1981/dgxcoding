# Voice Home Assistant

Control Home Assistant with your voice using Whisper (STT) + a DGX Spark LLM.

```
Microphone → Whisper STT → Qwen3-A3B (DGX) → Home Assistant REST API
```

## Prerequisites

- Python 3.10+
- DGX Spark running `qwen3-a3b` (port 8002) — see root `docker-compose.yml`
- Home Assistant with a Long-Lived Access Token

## Setup

```bash
cd projects/voice-home-assistant

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env: set HA_URL, HA_TOKEN, DGX_URL
```

### Get a Home Assistant token
1. Go to your HA profile: `http://homeassistant.local:8123/profile`
2. Scroll to "Long-Lived Access Tokens" → Create token
3. Paste into `.env` as `HA_TOKEN`

## Usage

```bash
# Voice mode (default)
python main.py

# Test without microphone
python main.py --text "turn off the kitchen lights"
python main.py --text "dim living room to 40%"
python main.py --text "what lights are on?"
```

## How It Works

1. **STT**: `faster-whisper` records from microphone until 500ms of silence, then transcribes
2. **LLM**: Qwen3-A3B on DGX receives transcribed text + HA tool definitions
3. **Tool calls**: LLM decides which HA action to call (turn_on, turn_off, set_light, etc.)
4. **HA REST API**: Python executes the tool call against Home Assistant
5. **Reply**: LLM gives a brief confirmation

## Available Commands (examples)

| You say | What happens |
|---------|-------------|
| "Turn off the kitchen lights" | `turn_off(light.kitchen)` |
| "Dim the bedroom to 30%" | `set_light(light.bedroom, brightness_pct=30)` |
| "Set living room lights to warm white" | `set_light(light.living_room, color_name=warm white)` |
| "Toggle the fan" | `toggle(switch.fan)` |
| "What's the thermostat set to?" | `get_state(climate.thermostat)` |
| "What lights are available?" | `list_entities(domain=light)` |
| "Run the movie mode script" | `run_script(movie_mode)` |

## Configuration (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `HA_URL` | `http://homeassistant.local:8123` | Home Assistant base URL |
| `HA_TOKEN` | — | Long-lived access token (required) |
| `DGX_URL` | `http://localhost:8002` | DGX model endpoint |
| `DGX_MODEL` | `qwen3-30b-a3b` | Model name |
| `WHISPER_MODEL` | `base` | STT model: tiny/base/small/medium |
| `WHISPER_DEVICE` | `cpu` | Where Whisper runs: cpu or cuda |
| `SILENCE_THRESHOLD` | `500` | ms of silence to stop recording |

## Entity IDs

The LLM needs to know your entity IDs (e.g. `light.kitchen` vs `light.kitchen_ceiling`).
Run this to see what you have:

```bash
python main.py --text "list all lights" --once
python main.py --text "list all switches" --once
```

Or check in HA: **Settings → Devices & Services → Entities**

## Whisper Model Tradeoffs

| Model | Speed | Accuracy | Size |
|-------|-------|----------|------|
| `tiny` | ~32x realtime | Low | 75MB |
| `base` | ~16x realtime | Good | 145MB |
| `small` | ~6x realtime | Better | 466MB |
| `medium` | ~2x realtime | Best | 1.5GB |

`base` is the default — fast enough for voice commands, accurate for clear speech.

## Running STT on DGX

If you want Whisper to run on the DGX GPU instead of locally:
1. Set `WHISPER_DEVICE=cuda` in `.env`
2. Ensure the DGX has CUDA drivers accessible (it does if TRT-LLM is running)
3. Note: this requires network audio streaming, not currently implemented — local CPU is simpler

## Troubleshooting

**"No module named sounddevice"**
```bash
pip install sounddevice
# On Linux also: apt-get install libportaudio2
```

**Microphone not detected**
```bash
python -c "import sounddevice; print(sounddevice.query_devices())"
```

**LLM not calling tools / wrong entity IDs**
- Run `python main.py --text "list all lights"` to see actual entity IDs
- Entity IDs are exact: `light.kitchen` not `light.Kitchen`

**Home Assistant 401 Unauthorized**
- Regenerate your Long-Lived Access Token in HA profile settings

**DGX connection refused**
- Verify: `curl http://DGX_IP:8002/v1/models`
- Check model is running: `./utils/check_status.sh` on DGX
