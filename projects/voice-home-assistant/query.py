"""
HA Query — dry-run or live execution with optional vision model.

Uses a curated home-context markdown doc for entity knowledge, fetches live
states for known entities, then sends your prompt to the text LLM. Camera
queries are automatically routed to a separate vision model for image analysis.

Usage:
  python query.py "turn off all lights in the bedroom"
  python query.py -x "turn on the entry hall light"   # live execution
  python query.py "is there a car in the driveway?"   # triggers vision model
  python query.py --context                            # print model context
  python query.py -i                                   # interactive loop

Env vars (in .env):
  HA_URL, HA_TOKEN              — Home Assistant connection
  DGX_URL, DGX_MODEL            — Text LLM (Nemotron-Nano, port 8009)
  DGX_VISION_URL, DGX_VISION_MODEL — Vision LLM (Qwen2.5-VL, port 8011)
  HA_CONTEXT_FILE               — path to voice-context.md
"""

import argparse
import base64
import json
import os
import re
import sys
import tempfile
import time
from dotenv import load_dotenv
from openai import OpenAI

from ha_client import HAClient, HA_TOOLS

load_dotenv()

# ---------------------------------------------------------------------------
# Home context document
# ---------------------------------------------------------------------------

def load_context_doc(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"ERROR: HA_CONTEXT_FILE not found: {path}")
        print("Set HA_CONTEXT_FILE in .env to point to your voice-context.md")
        sys.exit(1)


def extract_entity_ids(doc: str) -> list[str]:
    return re.findall(r'`([a-z_]+\.[a-z0-9_]+)`', doc)


# ---------------------------------------------------------------------------
# Live state fetch (only for curated entities)
# ---------------------------------------------------------------------------

def fetch_live_states(ha: HAClient, entity_ids: list[str]) -> str:
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

def build_system_prompt(home_doc: str, live_states: str, has_vision: bool) -> str:
    vision_rule = (
        "- For questions about camera images (e.g. 'is there a car?', 'is anyone at the door?'), "
        "use the get_camera_snapshot tool — a vision model will analyze the image and return a description."
    ) if has_vision else (
        "- Camera image analysis is not available (no vision model configured)."
    )

    return f"""\
You are a voice controller for a smart home running Home Assistant.
You have complete knowledge of this home from the documentation below.

## Rules
- You MUST call tools to perform actions — never just describe what you would do.
- You CAN make multiple tool calls in a single response. For bulk actions (e.g. \
"turn off all lights"), call turn_off once per entity in the same response.
- For read-only queries ("what's on?", "what's the temperature?"), answer directly \
from Current States — no tools needed.
- For state-conditional actions ("turn off lights that are ON"), check Current States \
first and only act on entities whose state matches the condition.
- Use only the exact entity_id values listed below. Do not guess or invent IDs.
- Never control entities ending in `_indicator` — those are Inovelli switch LED status lights.
- Irrigation (yard_sprinkler_zone_*) is currently offline — tell the user if asked.
- Bond Bridge devices (gym fan, guest room fan, bedroom shades) may be unavailable \
if the Bridge is offline.
{vision_rule}
- Be concise in your final reply. One sentence confirming what was done or answering the question.

## Home Layout & Entity Reference
{home_doc}

## Current States
{live_states}
"""


# ---------------------------------------------------------------------------
# Vision model — camera image analysis
# ---------------------------------------------------------------------------

def analyze_camera_image(
    vision_llm: OpenAI,
    vision_model: str,
    image_bytes: bytes,
    question: str,
) -> str:
    """Send a camera JPEG to the vision model and return its analysis."""
    b64 = base64.b64encode(image_bytes).decode()
    try:
        response = vision_llm.chat.completions.create(
            model=vision_model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }],
            temperature=0.1,
            max_tokens=512,
        )
        return response.choices[0].message.content or "No analysis returned."
    except Exception as e:
        return f"Vision model error: {e}"


def handle_camera_tool(
    ha: HAClient | None,
    vision_llm: OpenAI | None,
    vision_model: str,
    args: dict,
    dry_run: bool,
    debug: bool = False,
) -> str:
    """
    Fetch camera snapshot and route to vision model.
    Camera fetch always runs (it's read-only) even in dry-run.
    Only HA write operations are skipped in dry-run.
    """
    entity_id = args.get("entity_id", "")
    question  = args.get("question", "Describe what you see.")

    if not vision_llm:
        return "[Vision model not configured — set DGX_VISION_URL and DGX_VISION_MODEL in .env]"
    if ha is None:
        return f"[No HA connection — cannot fetch {entity_id}]"

    try:
        print(f"  📷 Capturing {entity_id}...", end=" ", flush=True)
        image_bytes = ha.get_camera_snapshot(entity_id)
        size_kb = len(image_bytes) // 1024
        print(f"{size_kb} KB", end="", flush=True)

        if debug:
            # Save snapshot to temp file for manual inspection
            suffix = entity_id.replace(".", "_").replace("/", "_")
            ts = int(time.time())
            tmp_path = os.path.join(tempfile.gettempdir(), f"ha_snapshot_{suffix}_{ts}.jpg")
            with open(tmp_path, "wb") as f:
                f.write(image_bytes)
            print(f"\n  💾 Saved to: {tmp_path}", flush=True)

        print(f"  → analyzing with {vision_model}...", end=" ", flush=True)
        analysis = analyze_camera_image(vision_llm, vision_model, image_bytes, question)
        print("done.")

        if debug:
            print(f"\n  🔍 Vision response:\n    {analysis}\n")

        return analysis
    except Exception as e:
        print()
        return f"Camera error: {e}"


# ---------------------------------------------------------------------------
# XML tool call fallback parser (Nemotron-Nano native format)
# ---------------------------------------------------------------------------

def parse_xml_tool_calls(text: str) -> list[dict]:
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
# Main LLM loop
# ---------------------------------------------------------------------------

def run_query(
    llm: OpenAI,
    system_prompt: str,
    user_text: str,
    model: str,
    ha: HAClient | None = None,
    ha_readonly: HAClient | None = None,
    vision_llm: OpenAI | None = None,
    vision_model: str = "",
    debug: bool = False,
) -> tuple[list[dict], str]:
    """
    Send prompt to text LLM, handle tool calls.
    ha           — HA client for write operations (None = dry-run, skip writes)
    ha_readonly  — HA client for read-only ops like camera snapshots (always provided)
    Camera snapshot calls are routed to the vision model.
    """
    dry_run     = ha is None
    ha_for_cam  = ha_readonly or ha  # camera is always read-only, use whichever is available
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_text},
    ]
    actions = []

    for _ in range(10):
        response = llm.chat.completions.create(
            model=model,
            messages=messages,
            tools=HA_TOOLS,
            tool_choice="auto",
            temperature=0.1,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        msg     = response.choices[0].message
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

                if call.function.name == "get_camera_snapshot":
                    result = handle_camera_tool(ha_for_cam, vision_llm, vision_model, args, dry_run, debug)
                elif dry_run:
                    result = "[DRY RUN — not executed]"
                else:
                    result = ha.execute_tool(call.function.name, args)
                    print(f"  ✓ {call.function.name}({args}) → {result}")

                messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
            continue

        # --- Path 2: XML tool calls in response text (Nemotron fallback) ---
        xml_calls = parse_xml_tool_calls(content)
        if xml_calls:
            clean = re.sub(r'<tool_call>.*?</tool_call>', '', content, flags=re.DOTALL).strip()
            messages.append({"role": "assistant", "content": content})
            for i, c in enumerate(xml_calls):
                actions.append(c)
                if c["tool"] == "get_camera_snapshot":
                    result = handle_camera_tool(ha_for_cam, vision_llm, vision_model, c["args"], dry_run, debug)
                elif dry_run:
                    result = "[DRY RUN — not executed]"
                else:
                    result = ha.execute_tool(c["tool"], c["args"])
                    print(f"  ✓ {c['tool']}({c['args']}) → {result}")
                messages.append({"role": "tool", "tool_call_id": f"xml_{i}", "content": result})
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
    parser = argparse.ArgumentParser(description="HA Query — dry-run or live, with optional vision")
    parser.add_argument("prompt",       nargs="?", help="What you want to do")
    parser.add_argument("--execute", "-x", action="store_true", help="Execute commands in Home Assistant")
    parser.add_argument("--debug",   "-d", action="store_true", help="Save camera snapshots to temp files and print vision responses")
    parser.add_argument("--context",       action="store_true", help="Print full model context and exit")
    parser.add_argument("-i", "--interactive", action="store_true", help="Interactive loop")
    args = parser.parse_args()

    ha_url        = os.environ.get("HA_URL",           "http://homeassistant.local:8123")
    ha_token      = os.environ.get("HA_TOKEN",         "")
    dgx_url       = os.environ.get("DGX_URL",          "http://localhost:8009")
    dgx_model     = os.environ.get("DGX_MODEL",        "Nemotron-3-Nano-30B-A3B-NVFP4")
    vision_url    = os.environ.get("DGX_VISION_URL",   "")
    vision_model  = os.environ.get("DGX_VISION_MODEL", "Qwen2.5-VL-7B-Instruct-NVFP4")
    context_file  = os.environ.get("HA_CONTEXT_FILE",  "")

    if not ha_token:
        print("ERROR: HA_TOKEN not set.")
        sys.exit(1)
    if not context_file:
        print("ERROR: HA_CONTEXT_FILE not set.")
        sys.exit(1)

    home_doc    = load_context_doc(context_file)
    entity_ids  = extract_entity_ids(home_doc)
    ha          = HAClient(ha_url, ha_token)
    live_states = fetch_live_states(ha, entity_ids)

    has_vision   = bool(vision_url)
    vision_llm   = OpenAI(base_url=f"{vision_url}/v1", api_key="dummy") if has_vision else None

    if args.context:
        print(build_system_prompt(home_doc, live_states, has_vision))
        return

    system_prompt = build_system_prompt(home_doc, live_states, has_vision)
    llm = OpenAI(base_url=f"{dgx_url}/v1", api_key="dummy")

    print(f"Text  : {dgx_model}  ({dgx_url})")
    if has_vision:
        print(f"Vision: {vision_model}  ({vision_url})")
    else:
        print("Vision: not configured  (set DGX_VISION_URL to enable)")
    print("Mode  :", "LIVE" if args.execute else "DRY RUN")
    print()

    def run_once(prompt: str):
        print(f"Query : {prompt}")
        # Always pass ha so camera snapshots work in dry-run (read-only).
        # write_ha controls whether control commands are actually executed.
        ha_exec = ha if args.execute else None
        actions, final_text = run_query(
            llm, system_prompt, prompt, dgx_model,
            ha=ha_exec,
            ha_readonly=ha,
            vision_llm=vision_llm,
            vision_model=vision_model,
            debug=args.debug,
        )
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
