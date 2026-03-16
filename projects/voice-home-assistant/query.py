"""
HA Query Tester — dry-run, no execution.

Fetches your Home Assistant entity list, builds context for the LLM,
sends your prompt to Nemotron-Nano, and prints what commands the model
would execute — without touching anything in HA.

Usage:
  python query.py "turn off all lights in the bedroom"
  python query.py --context        # print HA context and exit (useful to see what model sees)
  python query.py --interactive    # loop for multiple queries in one session

Requires .env with HA_URL, HA_TOKEN, and optionally DGX_URL / DGX_MODEL.
"""

import argparse
import json
import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

from ha_client import HAClient, HA_TOOLS

load_dotenv()


# Only include domains that can be controlled — skip sensors, trackers, weather, etc.
CONTROLLABLE_DOMAINS = {
    "light", "switch", "climate", "cover", "fan", "media_player",
    "script", "scene", "input_boolean", "input_select", "input_number",
    "button", "lock", "vacuum", "alarm_control_panel",
}


def fetch_ha_context(ha: HAClient) -> str:
    """
    Fetch controllable entities from HA and return a compact context string.
    Skips sensors, automations, device trackers, etc. to stay within token limits.
    """
    print("Fetching HA entities...", end=" ", flush=True)
    try:
        states = ha._get("states")
    except Exception as e:
        print(f"\nERROR: Could not reach Home Assistant: {e}")
        sys.exit(1)

    total_raw = len(states)

    # Group by domain, controllable only
    by_domain: dict[str, list[str]] = {}
    for s in states:
        eid = s["entity_id"]
        domain = eid.split(".")[0]
        if domain not in CONTROLLABLE_DOMAINS:
            continue
        name = s["attributes"].get("friendly_name", eid)
        state = s["state"]
        by_domain.setdefault(domain, []).append(f"  {eid} ({name}): {state}")

    # Priority order for the prompt
    priority = ["light", "switch", "climate", "cover", "fan", "media_player",
                "lock", "scene", "script", "input_boolean"]
    ordered = [(d, by_domain[d]) for d in priority if d in by_domain]
    ordered += [(d, by_domain[d]) for d in sorted(by_domain) if d not in priority]

    lines = []
    total = 0
    for domain, entities in ordered:
        lines.append(f"\n[{domain}]")
        for e in sorted(entities):
            lines.append(e)
        total += len(entities)

    print(f"got {total} controllable entities (filtered from {total_raw}) across {len(by_domain)} domains.")
    return "\n".join(lines)


def build_system_prompt(ha_context: str) -> str:
    return f"""You are a Home Assistant controller. The user will describe what they want to do.
Your job is to determine the exact sequence of Home Assistant API calls needed.

Use the available tools to fulfill the request. You may call multiple tools if needed.
Use the entity list below to find the correct entity_id values — use exact IDs, do not guess.

Available entities in this Home Assistant instance:
{ha_context}
"""


def run_dry_query(llm: OpenAI, system_prompt: str, user_text: str, model: str) -> list[dict]:
    """
    Send prompt to LLM, intercept all tool calls (dry-run), return list of planned actions.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]

    planned_actions = []

    for round_num in range(8):  # max 8 tool rounds
        response = llm.chat.completions.create(
            model=model,
            messages=messages,
            tools=HA_TOOLS,
            tool_choice="auto",
            temperature=0.1,
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            # Model is done — no more tool calls
            final_text = msg.content or ""
            return planned_actions, final_text

        # Collect tool calls for this round, feed back dry-run results
        messages.append(msg)
        for call in msg.tool_calls:
            try:
                args = json.loads(call.function.arguments)
            except json.JSONDecodeError:
                args = {"raw": call.function.arguments}

            action = {"tool": call.function.name, "args": args}
            planned_actions.append(action)

            # Return a fake success so the model can continue reasoning
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": "[DRY RUN — not executed]",
            })

    return planned_actions, ""


def print_plan(actions: list[dict], final_text: str):
    if not actions:
        print("\n[Model made no tool calls — it may have responded directly]")
        if final_text:
            print(f"\nModel response: {final_text}")
        return

    print(f"\n{'─'*55}")
    print(f"  PLANNED ACTIONS ({len(actions)} call{'s' if len(actions) != 1 else ''})")
    print(f"{'─'*55}")
    for i, a in enumerate(actions, 1):
        args_str = ", ".join(f"{k}={v!r}" for k, v in a["args"].items())
        print(f"  {i:2}. {a['tool']}({args_str})")
    print(f"{'─'*55}")

    if final_text:
        print(f"\nModel summary: {final_text}")


def main():
    parser = argparse.ArgumentParser(description="HA Query Tester (dry-run)")
    parser.add_argument("prompt", nargs="?", help="What you want to do")
    parser.add_argument("--context", action="store_true", help="Print HA context and exit")
    parser.add_argument("--interactive", "-i", action="store_true", help="Loop for multiple queries")
    args = parser.parse_args()

    ha_url   = os.environ.get("HA_URL",   "http://homeassistant.local:8123")
    ha_token = os.environ.get("HA_TOKEN", "")
    dgx_url  = os.environ.get("DGX_URL",  "http://localhost:8009")
    dgx_model = os.environ.get("DGX_MODEL", "Nemotron-3-Nano-30B-A3B-NVFP4")

    if not ha_token:
        print("ERROR: HA_TOKEN not set. Copy .env.example to .env and fill it in.")
        sys.exit(1)

    ha = HAClient(ha_url, ha_token)
    ha_context = fetch_ha_context(ha)

    if args.context:
        print(ha_context)
        return

    system_prompt = build_system_prompt(ha_context)
    llm = OpenAI(base_url=f"{dgx_url}/v1", api_key="dummy")

    print(f"\nModel: {dgx_model}  ({dgx_url})")
    print("DRY RUN — no changes will be made to Home Assistant.\n")

    def run_once(prompt: str):
        print(f"Query: {prompt}")
        actions, final_text = run_dry_query(llm, system_prompt, prompt, dgx_model)
        print_plan(actions, final_text)

    if args.interactive:
        print("Interactive mode. Enter your queries below (Ctrl+C to quit).\n")
        while True:
            try:
                prompt = input("Query> ").strip()
                if not prompt:
                    continue
                run_once(prompt)
                print()
            except KeyboardInterrupt:
                print("\nGoodbye.")
                break
    elif args.prompt:
        run_once(args.prompt)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
