#!/data/data/com.termux/files/usr/bin/python
import base64
import os

from savage.cli import App
from savage.config import Config
from savage_model_runtime import RegistryProvider, choose_profile


def decode_prompt():
    raw = os.environ.get("SAVAGE_PROMPT_B64", "")
    if not raw:
        raise RuntimeError("SAVAGE_PROMPT_B64 is empty")
    return base64.b64decode(raw).decode("utf-8")


def main():
    prompt = decode_prompt()
    requested = os.environ.get("SAVAGE_MODEL_PROFILE", "auto")

    app = App(Config())
    try:
        rows = app.mem.history(app.sid, 8)
        profile = choose_profile(requested, prompt)
        provider = RegistryProvider(profile, rows)

        app.cmd.providers = [provider]

        for name in ("code", "recon"):
            agent = getattr(app.cmd, name, None)
            if agent is not None and hasattr(agent, "provider"):
                agent.provider = provider

        result = app.cmd.handle(app.sid, prompt)
        print(result["output"])
    finally:
        app.close()


if __name__ == "__main__":
    main()
