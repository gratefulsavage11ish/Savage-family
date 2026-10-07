#!/data/data/com.termux/files/usr/bin/python
import base64
import os
from pathlib import Path

from savage.cli import App
from savage.config import Config

MAX_HISTORY_MESSAGES = 6
MAX_HISTORY_CHARS = 1800


def decode_prompt():
    raw = os.environ.get("SAVAGE_PROMPT_B64", "")
    if not raw:
        raise RuntimeError("SAVAGE_PROMPT_B64 is empty")
    return base64.b64decode(raw).decode("utf-8")


def compact_history(rows):
    parts = []
    total = 0

    for _, _, role, content, _ in rows:
        if role not in ("user", "assistant"):
            continue

        text = str(content).replace("\x00", "").strip()
        if not text:
            continue

        text = text[-500:]
        label = "User" if role == "user" else "Savage"
        item = f"{label}: {text}"

        if total + len(item) > MAX_HISTORY_CHARS:
            remaining = MAX_HISTORY_CHARS - total
            if remaining <= 80:
                break
            item = item[-remaining:]

        parts.append(item)
        total += len(item)

    return "\n".join(parts)


class ContextProvider:
    def __init__(self, inner, history):
        self.inner = inner
        self.history = history

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def generate(self, prompt, **kw):
        if not self.history:
            return self.inner.generate(prompt, **kw)

        enriched = (
            "CONTINUING CONVERSATION\n"
            "Use the recent conversation below as context. "
            "Do not repeat it unless useful. Answer the current request naturally.\n\n"
            f"{self.history}\n\n"
            "CURRENT TURN\n"
            f"{prompt}"
        )
        return self.inner.generate(enriched, **kw)


def wrap_provider(provider, history, cache):
    key = id(provider)
    if key not in cache:
        cache[key] = ContextProvider(provider, history)
    return cache[key]


def add_context_to_commander(app, history):
    cache = {}
    cmd = app.cmd

    if hasattr(cmd, "providers"):
        cmd.providers = [
            wrap_provider(p, history, cache)
            for p in cmd.providers
        ]

    for name in ("code", "recon"):
        agent = getattr(cmd, name, None)
        if agent is not None and getattr(agent, "provider", None) is not None:
            agent.provider = wrap_provider(agent.provider, history, cache)


def main():
    prompt = decode_prompt()
    app = App(Config())

    try:
        rows = app.mem.history(app.sid, MAX_HISTORY_MESSAGES)
        history = compact_history(rows)
        add_context_to_commander(app, history)

        result = app.cmd.handle(app.sid, prompt)
        print(result["output"])
    finally:
        app.close()


if __name__ == "__main__":
    main()
