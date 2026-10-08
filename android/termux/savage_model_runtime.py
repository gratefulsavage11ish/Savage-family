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
    if low.startswith("code:") and "code" in profiles:
        return "code"
    if low.startswith("recon:") and "recon" in profiles:
        return "recon"
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
        context = int(profile.get("context_size", 1536))
        threads = int(profile.get("threads", 4))

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
            return {
                "provider": self.name,
                "profile": self.profile_name,
                "backend": backend,
                "status": "READY",
                "base_url": self.profile.get("base_url"),
                "model": self.profile.get("model"),
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
    else:
        raise SystemExit("usage: savage_model_runtime.py [status|stop|profiles]")
