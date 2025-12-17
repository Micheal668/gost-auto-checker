import json

def load_rules(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("Invalid runtime json: root must be object")
    if data.get("runtime_format") != "GOST_RUNTIME_RULESET":
        raise ValueError("Invalid runtime json: runtime_format mismatch")
    if "rules" not in data or not isinstance(data["rules"], list):
        raise ValueError("Invalid runtime json: missing rules list")
    return data
