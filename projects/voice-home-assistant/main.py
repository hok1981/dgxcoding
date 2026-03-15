"""
Voice Home Assistant
Usage: python main.py [--text "your command"]  # --text skips microphone for testing

Flow: microphone → STT → LLM (DGX) with HA tools → Home Assistant REST API
"""

import argparse
import json
import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

from stt import STT
from ha_client import HAClient, HA_TOOLS

load_dotenv()

SYSTEM_PROMPT = """You are a smart home assistant. The user will give you voice commands to control their home.

Use the available tools to fulfill their requests. Be concise — just act, then confirm briefly.
If you need to know what entities exist, use list_entities first.

Examples:
- "turn off the kitchen lights" → call turn_off with entity_id=light.kitchen
- "dim the living room to 30%" → call set_light with brightness_pct=30
- "what's the bedroom light set to?" → call get_state
"""


def run_llm(client: OpenAI, ha: HAClient, user_text: str, model: str) -> str:
    """
    Send user text to LLM with HA tools. Handle tool calls, return final reply.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]

    # Agentic loop: keep going until LLM stops calling tools
    for _ in range(5):  # max 5 tool rounds
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=HA_TOOLS,
            tool_choice="auto",
            temperature=0.1,
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content or "Done."

        # Execute each tool call
        messages.append(msg)
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments)
            print(f"[HA] {call.function.name}({args})")
            result = ha.execute_tool(call.function.name, args)
            print(f"[HA] → {result}")
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": result,
            })

    return "Done."


def main():
    parser = argparse.ArgumentParser(description="Voice Home Assistant")
    parser.add_argument("--text", help="Skip microphone, use this text directly")
    parser.add_argument("--once", action="store_true", help="Run once then exit")
    args = parser.parse_args()

    # Config from .env
    ha_url = os.environ.get("HA_URL", "http://homeassistant.local:8123")
    ha_token = os.environ.get("HA_TOKEN", "")
    dgx_url = os.environ.get("DGX_URL", "http://localhost:8002")
    dgx_model = os.environ.get("DGX_MODEL", "qwen3-30b-a3b")
    whisper_model = os.environ.get("WHISPER_MODEL", "base")
    whisper_device = os.environ.get("WHISPER_DEVICE", "cpu")
    silence_ms = int(os.environ.get("SILENCE_THRESHOLD", "500"))

    if not ha_token:
        print("ERROR: HA_TOKEN not set. Copy .env.example to .env and fill in your token.")
        sys.exit(1)

    # Initialize clients
    ha = HAClient(ha_url, ha_token)
    llm = OpenAI(base_url=f"{dgx_url}/v1", api_key="dummy")

    stt = None
    if not args.text:
        stt = STT(model_size=whisper_model, device=whisper_device)

    print(f"\nVoice Home Assistant ready.")
    print(f"  LLM: {dgx_url} ({dgx_model})")
    print(f"  HA:  {ha_url}")
    if args.text:
        print(f"  Mode: text input")
    else:
        print(f"  Mode: voice (Whisper {whisper_model})")
    print("\nPress Ctrl+C to quit.\n")

    while True:
        try:
            if args.text:
                user_text = args.text
            else:
                user_text = stt.listen(silence_threshold_ms=silence_ms)

            if not user_text.strip():
                continue

            reply = run_llm(llm, ha, user_text, model=dgx_model)
            print(f"[Assistant] {reply}\n")

            if args.once or args.text:
                break

        except KeyboardInterrupt:
            print("\nGoodbye.")
            break
        except Exception as e:
            print(f"[ERROR] {e}\n")


if __name__ == "__main__":
    main()
