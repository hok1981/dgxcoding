"""
HA Query Tester — dry-run, no execution.

Uses a curated home-context markdown doc for entity knowledge, then fetches
live states only for those known entities. Sends your prompt to Nemotron-Nano
and prints what commands it would execute — without touching anything in HA.

Usage:
  python query.py "turn off all lights in the bedroom"
  python query.py --context        # print what the model sees and exit
  python query.py -i               # interactive loop

Env vars (in .env):
  HA_URL, HA_TOKEN          — Home Assistant connection
  DGX_URL, DGX_MODEL        — LLM endpoint
  HA_CONTEXT_FILE           — path to voice-context.md
"""

import argparse
import json
import os
import re
import sys
from dotenv import load_dotenv
from openai import OpenAI

from ha_client import HAClient, HA_TOOLS

load_dotenv()

# ---------------------------------------------------------------------------
# Home context document
# ---------------------------------------------------------------------------

def load_context_doc(path: str) -> str:
    """Load the curated voice-context.md file."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"ERROR: HA_CONTEXT_FILE not found: {path}")
        print("Set HA_CONTEXT_FILE in .env to point to your voice-context.md")
        sys.exit(1)


def extract_entity_ids(doc: str) -> list[str]:
    """Pull every `domain.entity_id` mentioned in the context doc."""
    return re.findall(r'`([a-z_]+\.[a-z0-9_]+)`', doc)


# ---------------------------------------------------------------------------
# Live state fetch (only for curated entities)
# ---------------------------------------------------------------------------

def fetch_live_states(ha: HAClient, entity_ids: list[str]) -> str:
    """
    Fetch current states for the entities listed in the context doc.
    Returns a compact multi-line string grouped by domain.
    """
    print("Fetching live states...", end=" ", flush=True)
    try:
        all_states = ha._get("states")
    except Exception as e:
        print(f"\nERROR: Could not reach Home Assistant: {e}")
        sys.exit(1)

    state_map = {s["entity_id"]: s["state"] for s in all_states}
    curated = set(entity_ids)

    by_domain: dict[str, list[str]] = {}
    for eid in sorted(curated):
        if eid not in state_map:
            continue
        domain = eid.split(".")[0]
        # Skip sensors/cameras/binary_sensors — read-only, not controllable
        if domain in ("sensor", "binary_sensor", "camera", "calendar"):
            continue
        by_domain.setdefault(domain, []).append(f"  {eid}: {state_map[eid]}")

    lines = []
    for domain in sorted(by_domain):
        lines.append(f"[{domain}]")
        lines.extend(by_domain[domain])

    found = sum(len(v) for v in by_domain.values())
    print(f"got {found} controllable entities.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """\
You are a voice controller for a smart home running Home Assistant.
You have complete knowledge of this home from the documentation below.

## Rules
- You MUST call tools to perform actions — never just describe what you would do.
- You CAN make multiple tool calls in a single response. For bulk actions (e.g. \
"turn off all lights"), call turn_off once per entity in the same response.
- For read-only queries ("what's on?", "what's the temperature?"), answer directly \
from Current States — no tools needed.
- For state-conditional actions ("turn off lights that are ON", "turn on fans that \
are off"), check Current States first and only act on entities whose state matches \
the condition. Do NOT call turn_off on an entity that is already off.
- Use only the exact entity_id values listed below. Do not guess or invent IDs.
- Never control entities ending in `_indicator` — those are Inovelli switch LED \
status lights, not room devices.
- Irrigation (yard_sprinkler_zone_*) is currently offline — tell the user if asked.
- Bond Bridge devices (gym fan, guest room fan, bedroom shades) may be unavailable \
if the Bridge is offline.
- Be concise in your final reply. One sentence confirming what was done.

## Home Layout & Entity Reference
{home_doc}

## Current States
{live_states}
"""

def build_system_prompt(home_doc: str, live_states: str) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(home_doc=home_doc, live_states=live_states)


# ---------------------------------------------------------------------------
# XML tool call fallback parser
# ---------------------------------------------------------------------------
# Nemotron-Nano sometimes outputs <tool_call> XML in response text instead of
# using the OpenAI API tool_calls field. This parser extracts those calls.

def parse_xml_tool_calls(text: str) -> list[dict]:
    """Parse <tool_call><function=name><parameter=x>val</parameter></function></tool_call> blocks."""
    calls = []
    for block in re.finditer(r'<tool_call>(.*?)</tool_call>', text, re.DOTALL):
        content = block.group(1)
        fn_match = re.search(r'<function=(\w+)', content)
        if not fn_match:
            continue
        fn_name = fn_match.group(1)
        params = {}
        for p in re.finditer(r'<parameter=(\w+)>\s*(.*?)\s*</parameter>', content, re.DOTALL):
            params[p.group(1)] = p.group(2).strip()
        calls.append({"tool": fn_name, "args": params})
    return calls


# ---------------------------------------------------------------------------
# LLM dry-run loop
# ---------------------------------------------------------------------------

def run_query(
    llm: OpenAI,
    system_prompt: str,
    user_text: str,
    model: str,
    ha: HAClient | None = None,
) -> tuple[list[dict], str]:
    """
    Send prompt to LLM and handle tool calls.
    If ha is provided, tool calls are executed against Home Assistant.
    If ha is None, dry-run mode — calls are recorded but not executed.
    Returns (actions, final_text).
    """
    dry_run = ha is None
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]

    actions = []

    for _ in range(10):  # max rounds
        response = llm.chat.completions.create(
            model=model,
            messages=messages,
            tools=HA_TOOLS,
            tool_choice="auto",
            temperature=0.1,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        msg = response.choices[0].message
        content = msg.content or ""

        # --- Path 1: proper OpenAI tool_calls ---
        if msg.tool_calls:
            messages.append(msg)
            for call in msg.tool_calls:
                try:
                    args = json.loads(call.function.arguments)
                except json.JSONDecodeError:
                    args = {"raw": call.function.arguments}
                actions.append({"tool": call.function.name, "args": args})
                if dry_run:
                    result = "[DRY RUN — not executed]"
                else:
                    result = ha.execute_tool(call.function.name, args)
                    print(f"  ✓ {call.function.name}({args}) → {result}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result,
                })
            continue

        # --- Path 2: XML tool calls in response text (Nemotron fallback) ---
        xml_calls = parse_xml_tool_calls(content)
        if xml_calls:
            clean = re.sub(r'<tool_call>.*?</tool_call>', '', content, flags=re.DOTALL).strip()
            messages.append({"role": "assistant", "content": content})
            for i, c in enumerate(xml_calls):
                actions.append(c)
                if dry_run:
                    result = "[DRY RUN — not executed]"
                else:
                    result = ha.execute_tool(c["tool"], c["args"])
                    print(f"  ✓ {c['tool']}({c['args']}) → {result}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": f"xml_{i}",
                    "content": result,
                })
            if clean:
                return actions, clean
            continue

        # --- No tool calls: model is done ---
        display = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        return actions, display

    return actions, ""


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_plan(actions: list[dict], final_text: str, executed: bool = False):
    label = "EXECUTED" if executed else "PLANNED ACTIONS"
    if actions:
        print(f"\n{'─'*55}")
        print(f"  {label} ({len(actions)} call{'s' if len(actions) != 1 else ''})")
        print(f"{'─'*55}")
        if not executed:
            for i, a in enumerate(actions, 1):
                args_str = ", ".join(f"{k}={v!r}" for k, v in a["args"].items())
                print(f"  {i:2}. {a['tool']}({args_str})")
            print(f"{'─'*55}")
    else:
        print("\n[No actions — model answered directly]")

    if final_text:
        print(f"\n{final_text}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="HA Query — dry-run or live execution")
    parser.add_argument("prompt", nargs="?", help="What you want to do")
    parser.add_argument("--execute", "-x", action="store_true", help="Actually execute commands in Home Assistant")
    parser.add_argument("--context", action="store_true", help="Print full model context and exit")
    parser.add_argument("-i", "--interactive", action="store_true", help="Interactive loop")
    args = parser.parse_args()

    ha_url        = os.environ.get("HA_URL",          "http://homeassistant.local:8123")
    ha_token      = os.environ.get("HA_TOKEN",        "")
    dgx_url       = os.environ.get("DGX_URL",         "http://localhost:8009")
    dgx_model     = os.environ.get("DGX_MODEL",       "Nemotron-3-Nano-30B-A3B-NVFP4")
    context_file  = os.environ.get("HA_CONTEXT_FILE", "")

    if not ha_token:
        print("ERROR: HA_TOKEN not set. Copy .env.example to .env and fill it in.")
        sys.exit(1)
    if not context_file:
        print("ERROR: HA_CONTEXT_FILE not set. Point it to your voice-context.md")
        sys.exit(1)

    home_doc    = load_context_doc(context_file)
    entity_ids  = extract_entity_ids(home_doc)

    ha          = HAClient(ha_url, ha_token)
    live_states = fetch_live_states(ha, entity_ids)

    if args.context:
        print(build_system_prompt(home_doc, live_states))
        return

    system_prompt = build_system_prompt(home_doc, live_states)
    llm = OpenAI(base_url=f"{dgx_url}/v1", api_key="dummy")

    print(f"Model : {dgx_model}  ({dgx_url})")
    if args.execute:
        print("Mode  : LIVE — commands will be sent to Home Assistant\n")
    else:
        print("Mode  : DRY RUN — nothing will be sent to Home Assistant\n")

    def run_once(prompt: str):
        print(f"Query : {prompt}")
        ha_exec = ha if args.execute else None
        actions, final_text = run_query(llm, system_prompt, prompt, dgx_model, ha=ha_exec)
        print_plan(actions, final_text, executed=args.execute)

    if args.interactive:
        print("Interactive mode — Ctrl+C to quit\n")
        while True:
            try:
                prompt = input("Query> ").strip()
                if prompt:
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
