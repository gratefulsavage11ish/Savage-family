import os

AGENTS = [("Commander", "READY"), ("Code", "SKELETON"), ("Recon", "SKELETON"), ("Operator", "SAFE MODE")]


def agent_list(cfg):
    out = []
    for n, s in AGENTS:
        if n == "Operator":
            s = "SAFE MODE" if str(cfg.get("operator_mode")).upper() == "SAFE" else "SKELETON"
        out.append((n, s))
    return out


REGISTRY_SCHEMA = 1


def expected_registry(cfg):
    return {"schema": REGISTRY_SCHEMA,
            "agents": [{"name": n, "status": s} for n, s in agent_list(cfg)]}


def registry_path(cfg):
    return cfg.path("agents", "registry.json")


def registry_problem(cfg):
    """None if agents/registry.json matches the truthful expected state, else a description."""
    import json
    try:
        with open(registry_path(cfg)) as f:
            have = json.load(f)
    except FileNotFoundError:
        return "agent registry missing"
    except (OSError, ValueError):
        return "agent registry unreadable"
    if have != expected_registry(cfg):
        return "agent registry out of date or claims unfinished agents are ready"
    return None


def write_registry(cfg):
    import json
    os.makedirs(os.path.dirname(registry_path(cfg)), exist_ok=True)
    with open(registry_path(cfg), "w") as f:
        json.dump(expected_registry(cfg), f, indent=2)
