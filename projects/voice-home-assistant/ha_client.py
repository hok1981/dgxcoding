"""
Home Assistant REST API client.
Exposes HA actions as Python functions and as OpenAI tool definitions.
"""

import requests
from typing import Any


class HAClient:
    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _post(self, path: str, data: dict = None) -> dict:
        r = requests.post(f"{self.url}/api/{path}", json=data or {}, headers=self.headers)
        r.raise_for_status()
        return r.json() if r.text else {}

    def _get(self, path: str) -> Any:
        r = requests.get(f"{self.url}/api/{path}", headers=self.headers)
        r.raise_for_status()
        return r.json()

    # --- Actions ---

    def turn_on(self, entity_id: str, **kwargs) -> dict:
        """Turn on a light, switch, or other entity."""
        return self._post("services/homeassistant/turn_on", {"entity_id": entity_id, **kwargs})

    def turn_off(self, entity_id: str) -> dict:
        """Turn off a light, switch, or other entity."""
        return self._post("services/homeassistant/turn_off", {"entity_id": entity_id})

    def toggle(self, entity_id: str) -> dict:
        """Toggle an entity on/off."""
        return self._post("services/homeassistant/toggle", {"entity_id": entity_id})

    def set_light(self, entity_id: str, brightness_pct: int = None, color_name: str = None) -> dict:
        """Control a light's brightness and/or color."""
        data = {"entity_id": entity_id}
        if brightness_pct is not None:
            data["brightness_pct"] = max(0, min(100, brightness_pct))
        if color_name is not None:
            data["color_name"] = color_name
        return self._post("services/light/turn_on", data)

    def run_script(self, script_id: str) -> dict:
        """Run a Home Assistant script."""
        return self._post(f"services/script/{script_id}", {})

    def get_state(self, entity_id: str) -> dict:
        """Get the current state of an entity."""
        return self._get(f"states/{entity_id}")

    def list_entities(self, domain: str = None) -> list[dict]:
        """List all entities, optionally filtered by domain (e.g. 'light', 'switch')."""
        states = self._get("states")
        if domain:
            states = [s for s in states if s["entity_id"].startswith(f"{domain}.")]
        return [{"entity_id": s["entity_id"], "state": s["state"], "name": s["attributes"].get("friendly_name", "")} for s in states]

    # --- Tool executor ---

    def execute_tool(self, name: str, args: dict) -> str:
        """Execute a tool call from the LLM and return a result string."""
        try:
            if name == "turn_on":
                self.turn_on(args["entity_id"])
                return f"Turned on {args['entity_id']}"
            elif name == "turn_off":
                self.turn_off(args["entity_id"])
                return f"Turned off {args['entity_id']}"
            elif name == "toggle":
                self.toggle(args["entity_id"])
                return f"Toggled {args['entity_id']}"
            elif name == "set_light":
                self.set_light(
                    args["entity_id"],
                    brightness_pct=args.get("brightness_pct"),
                    color_name=args.get("color_name"),
                )
                return f"Updated light {args['entity_id']}"
            elif name == "run_script":
                self.run_script(args["script_id"])
                return f"Ran script {args['script_id']}"
            elif name == "get_state":
                state = self.get_state(args["entity_id"])
                return f"{args['entity_id']} is {state['state']}"
            elif name == "list_entities":
                entities = self.list_entities(args.get("domain"))
                return "\n".join(f"{e['entity_id']} ({e['name']}): {e['state']}" for e in entities[:20])
            else:
                return f"Unknown tool: {name}"
        except Exception as e:
            return f"Error executing {name}: {e}"


# OpenAI-format tool definitions passed to the LLM
HA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "turn_on",
            "description": "Turn on a light, switch, fan, or any Home Assistant entity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "e.g. light.kitchen, switch.living_room_lamp"}
                },
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turn_off",
            "description": "Turn off a light, switch, or any Home Assistant entity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "e.g. light.kitchen, switch.living_room_lamp"}
                },
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "toggle",
            "description": "Toggle a Home Assistant entity on or off.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "e.g. light.bedroom"}
                },
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_light",
            "description": "Set a light's brightness and/or color.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "e.g. light.living_room"},
                    "brightness_pct": {"type": "integer", "description": "Brightness 0-100"},
                    "color_name": {"type": "string", "description": "Color name e.g. red, blue, warm white"},
                },
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_script",
            "description": "Run a Home Assistant script by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "script_id": {"type": "string", "description": "Script entity ID without 'script.' prefix"}
                },
                "required": ["script_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_state",
            "description": "Get the current state of a Home Assistant entity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "e.g. light.kitchen"}
                },
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_entities",
            "description": "List Home Assistant entities, optionally filtered by domain.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Optional: light, switch, climate, script, etc."}
                },
            },
        },
    },
]
