#!/data/data/com.termux/files/usr/bin/python
"""Savage multi-model runtime.

One local llama-server is kept resident at a time. Profiles can also point to an
OpenAI-compatible remote server. The Android frontend chooses a profile; "auto"
routes normal chat/general, code: -> code, and recon: -> recon.
"""

from __future__ import annotations

import fcntl
import json
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("SAVAGE_AI_ROOT", "/data/local/savage-ai"))
REGISTRY = ROOT / "config" / "models.json"
STATE = ROOT / "tmp" / "model-server.json"
LOCK = ROOT / "tmp" / "model-server.lock"
LOG = ROOT / "logs" / "llama-server.log"

DEFAULT_MODEL = ROOT / "models" / "Qwen3-1.7B-abliterated-Q4_K_M.gguf"

DEFAULT_REGISTRY = {
    "schema": 1,
    "default_profile": "general",
    "profiles": {
        "general": {
            "backend": "local_server",
            "model_path": str(DEFAULT_MODEL),
            "model_name": "qwen3-1.7b-general",
            "context_size": 768,
            "threads": 2,
            "max_tokens": 128,
            "temperature": 0.65,
            "port": 8081
        },
        "code": {
            "backend": "local_server",
            "model_path": str(DEFAULT_MODEL),
            "model_name": "qwen3-1.7b-code",
            "context_size": 768,
            "threads": 2,
            "max_tokens": 160,
            "temperature": 0.25,
            "port": 8081
        },
        "recon": {
            "backend": "local_server",
            "model_path": str(DEFAULT_MODEL),
            "model_name": "qwen3-1.7b-recon",
            "context_size": 768,
            "threads": 2,
            "max_tokens": 144,
            "temperature": 0.35,
            "port": 8081
        },
        "hf_fast": {
            "backend": "openai",
            "base_url": "https://router.huggingface.co/v1",
            "model": "openai/gpt-oss-120b:fastest",
            "api_key_env": "HF_TOKEN",
            "max_tokens": 320,
            "temperature": 0.55
        },
        "hf_code": {
            "backend": "openai",
            "base_url": "https://router.huggingface.co/v1",
            "model": "Qwen/Qwen3-Coder-480B-A35B-Instruct:fastest",
            "api_key_env": "HF_TOKEN",
            "max_tokens": 420,
            "temperature": 0.2
        },
        "hf_reasoning": {
            "backend": "openai",
            "base_url": "https://router.huggingface.co/v1",
            "model": "Qwen/Qwen3-4B-Thinking-2507:fastest",
            "api_key_env": "HF_TOKEN",
            "max_tokens": 420,
            "temperature": 0.35
        },
        "hf_custom": {
            "backend": "openai",
            "base_url": "https://router.huggingface.co/v1",
            "model": "openai/gpt-oss-120b:fastest",
            "api_key_env": "HF_TOKEN",
            "max_tokens": 512,
            "temperature": 0.5
        },
        "remote": {
            "backend": "openai",
            "base_url": "http://127.0.0.1:8088/v1",
            "model": "remote-model",
            "api_key_env": "SAVAGE_REMOTE_API_KEY",
            "max_tokens": 512,
            "temperature": 0.5
        }
    }
}


def ensure_dirs():
    for p in (ROOT / "config", ROOT / "tmp", ROOT / "logs"):
        p.mkdir(parents=True, exist_ok=True)


def ensure_registry():
    ensure_dirs()
    if not REGISTRY.exists():
        REGISTRY.write_text(json.dumps(DEFAULT_REGISTRY, indent=2) + "\n")
        return load_registry()

    data = load_registry()
    changed = False

    if "schema" not in data:
        data["schema"] = DEFAULT_REGISTRY["schema"]
        changed = True

    if "default_profile" not in data:
        data["default_profile"] = DEFAULT_REGISTRY["default_profile"]
        changed = True

    profiles = data.setdefault("profiles", {})
    for name, default_profile in DEFAULT_REGISTRY["profiles"].items():
        if name not in profiles:
            profiles[name] = default_profile
            changed = True

    if changed:
        REGISTRY.write_text(json.dumps(data, indent=2) + "\n")

    return data


def load_registry():
    with REGISTRY.open() as f:
        data = json.load(f)
    if not isinstance(data.get("profiles"), dict):
        raise RuntimeError("models.json has no profiles object")
    return data


def choose_profile(requested: str, prompt: str) -> str:
    reg = ensure_registry()
    profiles = reg["profiles"]
    req = (requested or "auto").strip().lower()

    if req and req != "auto":
        if req not in profiles:
            raise RuntimeError(f"unknown model profile: {req}")
        return req

    low = (prompt or "").lstrip().lower()
    hf_ready = bool(os.environ.get("HF_TOKEN"))

    if low.startswith("code:"):
        if hf_ready and "hf_code" in profiles:
            return "hf_code"
        if "code" in profiles:
            return "code"

    if low.startswith(("reason:", "think:", "research:")):
        if hf_ready and "hf_reasoning" in profiles:
            return "hf_reasoning"

    if low.startswith("recon:") and "recon" in profiles:
        return "recon"

    if hf_ready and "hf_fast" in profiles:
        return "hf_fast"

    return reg.get("default_profile", "general")


def server_binary() -> Path:
    candidates = [
        ROOT / "bin" / "llama" / "llama-server",
        ROOT / "src" / "llama.cpp" / "build" / "bin" / "llama-server",
        ROOT / "src" / "llama.cpp" / "build" / "llama-server",
    ]
    for p in candidates:
        if p.is_file() and os.access(p, os.X_OK):
            return p
    raise RuntimeError(
        "llama-server not found. Build it with: "
        "cd /data/local/savage-ai/src/llama.cpp && "
        "cmake --build build --target llama-server -j2"
    )


def read_state():
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def write_state(data):
    ensure_dirs()
    STATE.write_text(json.dumps(data, indent=2) + "\n")


def pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def http_json(url, payload=None, headers=None, timeout=180):
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers=req_headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
    return json.loads(raw)


def health(port, timeout=2):
    try:
        data = http_json(f"http://127.0.0.1:{port}/health", timeout=timeout)
        return data.get("status") == "ok"
    except Exception:
        return False


def stop_local_server():
    st = read_state()
    pid = st.get("pid")
    if pid and pid_alive(pid):
        try:
            os.kill(int(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        for _ in range(30):
            if not pid_alive(pid):
                break
            time.sleep(0.1)
        if pid_alive(pid):
            try:
                os.kill(int(pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
    try:
        STATE.unlink()
    except FileNotFoundError:
        pass


def ensure_local_server(profile_name, profile):
    ensure_dirs()
    LOCK.touch(exist_ok=True)

    with LOCK.open("r+") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)

        model = Path(profile["model_path"])
        if not model.is_file():
            raise RuntimeError(f"model missing: {model}")

        port = int(profile.get("port", 8081))
        context = int(profile.get("context_size", 768))
        threads = int(profile.get("threads", 2))

        wanted = {
            "profile": profile_name,
            "model_path": str(model),
            "port": port,
            "context_size": context,
            "threads": threads,
        }

        st = read_state()
        same = all(st.get(k) == v for k, v in wanted.items())
        if same and pid_alive(st.get("pid", -1)) and health(port):
            return port

        stop_local_server()

        exe = server_binary()
        logf = LOG.open("ab", buffering=0)
        cmd = [
            str(exe),
            "-m", str(model),
            "-c", str(context),
            "-t", str(threads),
            "-b", "128",
            "-ub", "64",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--jinja",
        ]

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=logf,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )

        state = dict(wanted)
        state.update({
            "pid": proc.pid,
            "started": time.time(),
            "binary": str(exe),
        })
        write_state(state)

        deadline = time.time() + 120
        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(
                    f"llama-server exited with code {proc.returncode}; "
                    f"see {LOG}"
                )
            if health(port):
                return port
            time.sleep(0.75)

        stop_local_server()
        raise RuntimeError("llama-server did not become ready within 120 seconds")



def _hf_headers():
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        raise RuntimeError("HF_TOKEN is not configured")
    return {"Authorization": f"Bearer {token}"}


def hf_list_models(search="", limit=100):
    """Return live HF Router chat models ranked by observed provider throughput."""
    data = http_json(
        "https://router.huggingface.co/v1/models",
        headers=_hf_headers(),
        timeout=45,
    )
    rows = data.get("data", []) if isinstance(data, dict) else []
    query = (search or "").strip().lower()
    out = []

    for item in rows:
        model_id = str(item.get("id", "")).strip()
        if not model_id:
            continue
        if query and query not in model_id.lower():
            continue

        providers = [
            p for p in (item.get("providers") or [])
            if p.get("status") == "live"
        ]
        if not providers:
            continue

        best = max(
            providers,
            key=lambda p: float(p.get("throughput") or 0),
        )

        context = max(
            [int(p.get("context_length") or 0) for p in providers] or [0]
        )
        throughput = float(best.get("throughput") or 0)
        latency = best.get("first_token_latency_ms")
        free = any(bool(p.get("is_free")) for p in providers)
        tools = any(bool(p.get("supports_tools")) for p in providers)

        out.append({
            "id": model_id,
            "throughput": round(throughput, 1),
            "latency_ms": round(float(latency), 0) if latency is not None else None,
            "context": context or None,
            "free": free,
            "tools": tools,
            "provider": best.get("provider"),
        })

    out.sort(
        key=lambda x: (
            x["throughput"],
            1 if x["free"] else 0,
        ),
        reverse=True,
    )
    return out[:max(1, min(int(limit), 200))]


def hf_select_model(model_id):
    model_id = str(model_id or "").strip()
    if not model_id or "/" not in model_id:
        raise RuntimeError("invalid Hugging Face model id")

    reg = ensure_registry()
    profile = reg["profiles"].setdefault("hf_custom", {})
    profile.update({
        "backend": "openai",
        "base_url": "https://router.huggingface.co/v1",
        "model": model_id + ":fastest",
        "api_key_env": "HF_TOKEN",
        "max_tokens": int(profile.get("max_tokens", 512)),
        "temperature": float(profile.get("temperature", 0.5)),
    })
    reg["last_hf_model"] = model_id
    REGISTRY.write_text(json.dumps(reg, indent=2) + "\n")
    return profile


class RegistryProvider:
    name = "Savage model registry"

    def __init__(self, profile_name, history_rows=None):
        self.registry = ensure_registry()
        self.profile_name = profile_name
        try:
            self.profile = self.registry["profiles"][profile_name]
        except KeyError as e:
            raise RuntimeError(f"unknown model profile: {profile_name}") from e
        self.history_rows = history_rows or []

    def available(self):
        try:
            return self.status()["status"] == "READY"
        except Exception:
            return False

    def status(self):
        backend = self.profile.get("backend", "local_server")
        if backend == "local_server":
            model = Path(self.profile["model_path"])
            try:
                binary = str(server_binary())
                server_ok = True
            except Exception:
                binary = None
                server_ok = False
            return {
                "provider": self.name,
                "profile": self.profile_name,
                "backend": backend,
                "status": "READY" if model.is_file() and server_ok else "NOT INSTALLED",
                "model_path": str(model),
                "model_present": model.is_file(),
                "server_binary": binary,
                "context_size": self.profile.get("context_size"),
                "threads": self.profile.get("threads"),
            }

        if backend == "openai":
            env_name = self.profile.get("api_key_env", "SAVAGE_REMOTE_API_KEY")
            needs_key = bool(self.profile.get("base_url", "").startswith("https://router.huggingface.co"))
            have_key = bool(os.environ.get(env_name))
            return {
                "provider": self.name,
                "profile": self.profile_name,
                "backend": backend,
                "status": "READY" if (have_key or not needs_key) else "AUTH REQUIRED",
                "base_url": self.profile.get("base_url"),
                "model": self.profile.get("model"),
                "api_key_env": env_name,
            }

        return {
            "provider": self.name,
            "profile": self.profile_name,
            "backend": backend,
            "status": "NOT INSTALLED",
        }

    def _messages(self, prompt):
        messages = [{
            "role": "system",
            "content": (
                "You are Savage, a local AI assistant. Continue the conversation "
                "naturally and use prior turns when relevant. Be concise unless the "
                "user asks for detail."
            )
        }]

        for _, _, role, content, _ in self.history_rows[-8:]:
            if role not in ("user", "assistant"):
                continue
            text = str(content).replace("\x00", "").strip()
            if not text:
                continue
            if len(text) > 900:
                text = text[-900:]
            messages.append({"role": role, "content": text})

        messages.append({"role": "user", "content": str(prompt)})
        return messages

    def generate(self, prompt, **kw):
        backend = self.profile.get("backend", "local_server")
        max_tokens = int(
            kw.get("max_tokens")
            or self.profile.get("max_tokens", 192)
        )
        temperature = float(
            kw.get("temperature")
            if kw.get("temperature") is not None
            else self.profile.get("temperature", 0.6)
        )

        payload = {
            "messages": self._messages(prompt),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }

        if backend == "local_server":
            port = ensure_local_server(self.profile_name, self.profile)
            payload["model"] = self.profile.get("model_name", self.profile_name)
            data = http_json(
                f"http://127.0.0.1:{port}/v1/chat/completions",
                payload,
                timeout=240,
            )
        elif backend == "openai":
            base = self.profile["base_url"].rstrip("/")
            payload["model"] = self.profile.get("model", "model")
            env_name = self.profile.get("api_key_env", "SAVAGE_REMOTE_API_KEY")
            api_key = os.environ.get(env_name, "")
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            data = http_json(
                base + "/chat/completions",
                payload,
                headers=headers,
                timeout=240,
            )
        else:
            raise RuntimeError(f"unsupported backend: {backend}")

        try:
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            raise RuntimeError(f"invalid model server response: {data}") from e


def runtime_status():
    reg = ensure_registry()
    st = read_state()

    # A killed Android/Termux process can leave a stale JSON state file.
    # Treat a dead PID as stopped and remove the stale marker.
    pid = st.get("pid")
    if pid and not pid_alive(pid):
        try:
            STATE.unlink()
        except FileNotFoundError:
            pass
        st = {}

    out = {
        "registry": str(REGISTRY),
        "profiles": list(reg["profiles"].keys()),
        "default_profile": reg.get("default_profile"),
        "server": st,
    }
    if st.get("port"):
        out["server_healthy"] = health(int(st["port"]))
    else:
        out["server_healthy"] = False
    return out


if __name__ == "__main__":
    import base64
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "status":
        print(json.dumps(runtime_status(), indent=2))
    elif cmd == "stop":
        stop_local_server()
        print("MODEL SERVER: STOPPED")
    elif cmd == "profiles":
        reg = ensure_registry()
        print("\n".join(reg["profiles"].keys()))
    elif cmd == "hf-models":
        query = os.environ.get("SAVAGE_HF_SEARCH", "")
        print(json.dumps(hf_list_models(query, 120), separators=(",", ":")))
    elif cmd == "hf-select":
        raw = os.environ.get("SAVAGE_HF_MODEL_B64", "")
        if not raw:
            raise SystemExit("SAVAGE_HF_MODEL_B64 is empty")
        model_id = base64.b64decode(raw).decode("utf-8")
        profile = hf_select_model(model_id)
        print(json.dumps({
            "selected": model_id,
            "profile": "hf_custom",
            "route": profile["model"],
        }, separators=(",", ":")))
    else:
        raise SystemExit(
            "usage: savage_model_runtime.py "
            "[status|stop|profiles|hf-models|hf-select]"
        )
