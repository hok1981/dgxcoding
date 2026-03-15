# Voice Home Assistant — Design Document

## Goal

Replace Google Home with a fully local voice assistant that:
- Understands natural language commands in English
- Controls Home Assistant entities (lights, switches, scripts, climate, etc.)
- Runs entirely on local hardware — no cloud, no subscriptions
- Uses DGX Spark as the AI backend (STT + LLM)

---

## Phases

| Phase | Trigger | STT | LLM | Interface |
|-------|---------|-----|-----|-----------|
| **1 — Phone** | HA Companion App button | Whisper on DGX | Qwen3-A3B on DGX | Phone widget |
| **2 — Hardware** | Wake word (always-on) | Parakeet on DGX | Qwen3-A3B on DGX | RPi satellite |

This document covers Phase 1 in full and Phase 2 at design level.

---

## Phase 1 Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Phone (HA Companion App)                               │
│  - Tap widget or shortcut                               │
│  - Mic audio captured by app                            │
└───────────────────────┬─────────────────────────────────┘
                        │ audio stream (local WiFi)
                        ▼
┌─────────────────────────────────────────────────────────┐
│  Home Assistant Server                                  │
│  - Assist Pipeline orchestrates STT → LLM → response   │
│  - Executes entity commands natively                    │
└────────────┬──────────────────────┬─────────────────────┘
             │ Wyoming protocol      │ OpenAI-compatible API
             │ (TCP :10300)          │ (HTTP :8002)
             ▼                       ▼
┌────────────────────┐   ┌──────────────────────────────┐
│  DGX Spark         │   │  DGX Spark                   │
│  wyoming-whisper   │   │  TRT-LLM: Qwen3-A3B          │
│  faster-whisper    │   │  (port 8002)                 │
│  model: base/small │   │                              │
│  device: cuda      │   │  System prompt + HA tools    │
└────────────────────┘   └──────────────────────────────┘
```

### Request flow (Phase 1)

1. User taps voice button in HA Companion App
2. App records microphone audio
3. HA Assist pipeline receives audio
4. HA sends audio to **Wyoming Whisper** on DGX (:10300) → returns transcript
5. HA sends transcript to **OpenAI Conversation** integration → DGX Qwen3-A3B (:8002)
6. LLM returns tool calls (e.g. `turn_off(light.kitchen)`) or plain text response
7. HA executes entity commands directly
8. HA TTS speaks reply back through Companion App

---

## Phase 2 Architecture

```
┌──────────────────────┐
│  Wyoming Satellite   │  RPi Zero 2W + ReSpeaker 2-Mic HAT
│  - openWakeWord      │  Always-on, low-power
│  - "Hey Jarvis"      │
└──────────┬───────────┘
           │ Wyoming protocol (audio on wake word only)
           ▼
┌──────────────────────────────────────────────────────────┐
│  Home Assistant (same pipeline as Phase 1)               │
└────────────┬─────────────────────────┬───────────────────┘
             │ Wyoming STT             │ OpenAI Conversation
             ▼                         ▼
┌────────────────────┐     ┌──────────────────────────────┐
│  DGX Spark         │     │  DGX Spark                   │
│  wyoming-parakeet  │     │  TRT-LLM: Qwen3-A3B          │
│  Parakeet-TDT-1.1B │     │  (port 8002)                 │
│  (experiment)      │     └──────────────────────────────┘
└────────────────────┘
```

Phase 2 changes from Phase 1:
- Wyoming Satellite replaces phone as the input device
- Parakeet replaces Whisper for STT (experiment — keep Whisper as fallback)
- Everything else is identical — HA pipeline, DGX LLM, entity control

---

## Tech Stack

### DGX Spark Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `qwen3-a3b` | `nvcr.io/nvidia/tensorrt-llm/release:1.2.0rc6` | 8002 | LLM — intent parsing + tool calls |
| `wyoming-whisper` | `rhasspy/wyoming-faster-whisper` | 10300 | STT — audio → transcript |

### Home Assistant Integrations

| Integration | Purpose |
|-------------|---------|
| **Wyoming** (STT) | Points to DGX :10300 for speech recognition |
| **OpenAI Conversation** | Points to DGX :8002 for LLM intent + control |
| **Assist Pipeline** | Chains STT → Conversation → TTS |
| **HA Companion App** | Phone interface — voice button, widgets |

### LLM Configuration

- **Model**: Qwen3-A3B (port 8002) — chosen for speed (70-80 tok/s), adequate for voice latency
- **System prompt**: instructs LLM to control HA entities, be concise, use tools
- **Tool calling**: HA's OpenAI Conversation integration sends entity list as context
- **Fallback**: Qwen3-32B (port 8003) if better reasoning needed for complex commands

### STT Configuration

- **Phase 1 model**: `faster-whisper base` — fast, accurate enough for clear voice commands
- **Upgrade path**: `faster-whisper small` or `medium` if accuracy issues arise
- **Device**: CUDA (DGX Blackwell GPU — significantly faster than CPU)
- **Language**: English only (`--language en`)

---

## HA Assist Pipeline Configuration

```yaml
# configuration.yaml (or via UI)
conversation:
  intents: {}  # disabled — let LLM handle everything

# Voice pipeline configured in UI:
# Settings → Voice Assistants → Add Pipeline
#   STT: Wyoming (host: DGX_IP, port: 10300)
#   Conversation agent: OpenAI Conversation (DGX)
#   TTS: Piper (local, fast)
```

### OpenAI Conversation integration settings

```
API endpoint: http://DGX_IP:8002/v1
API key: dummy
Model: qwen3-30b-a3b
```

---

## DGX Docker Compose Addition

```yaml
wyoming-whisper:
  image: rhasspy/wyoming-faster-whisper
  platform: linux/arm64
  ports:
    - "10300:10300"
  volumes:
    - whisper-models:/data
  command: >
    --uri tcp://0.0.0.0:10300
    --model base
    --language en
    --device cuda
  runtime: nvidia
  environment:
    - NVIDIA_VISIBLE_DEVICES=all
  restart: unless-stopped
  profiles:
    - whisper

volumes:
  whisper-models:
```

Note: `wyoming-whisper` runs independently from the LLM services — it can stay up permanently alongside whichever LLM is active. It uses minimal GPU memory (~200MB for `base` model).

---

## LLM System Prompt Design

The OpenAI Conversation integration in HA automatically injects the list of exposed entities into the context. The system prompt needs to:

1. Instruct the LLM to act as a home controller, not a chatbot
2. Keep responses short (spoken via TTS — brevity matters)
3. Prefer acting over asking for clarification
4. Handle ambiguous room/entity names gracefully

```
You are a smart home controller. Control Home Assistant entities based on voice commands.

Rules:
- Act immediately on clear commands. Don't ask for confirmation.
- Keep responses to one short sentence (they will be spoken aloud).
- If a command is ambiguous (e.g. "the lights" could mean multiple rooms),
  turn on/off all matching entities.
- For unknown entities, say so briefly: "I don't see a [name] entity."
- Prefer entity friendly names over IDs in your spoken responses.
```

---

## Open Questions (to resolve during Phase 1)

1. **Wyoming ARM64 image**: Confirm `rhasspy/wyoming-faster-whisper` has a working ARM64 build for DGX
2. **GPU memory overlap**: Verify Whisper CUDA + Qwen3-A3B can coexist within 128GB (should be fine — Whisper base is ~200MB)
3. **HA Companion App latency**: Measure end-to-end from tap to response — target < 3 seconds
4. **Entity exposure**: Decide which HA entities to expose to the LLM (all vs curated list — too many can confuse the model)
5. **TTS voice**: Choose Piper voice model — affects how natural the spoken replies sound

---

## Phase 2 Decision Criteria

Move to Phase 2 hardware when:
- Phase 1 is stable and used daily
- Phone-tap friction becomes annoying (hands full, etc.)
- Parakeet Wyoming adapter has a stable community implementation

Hardware to buy for Phase 2:
- Raspberry Pi Zero 2W (~$15)
- ReSpeaker 2-Mic Pi HAT (~$20)
- Small USB power supply + case
