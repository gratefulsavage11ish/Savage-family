"""Tiny first step: put enough of Savage AI under SAVAGE_AI_ROOT that `savage doctor` can take over.
Doctor does all real setup. Never creates/mounts/formats storage."""
import os, sys
from . import core
from .config import Config, PHONE_ROOT
from .doctor import (can_write, install_app, package_dir, storage_problem, write_launchers)


def main(cfg=None, prefix=None):
    cfg = cfg or Config()
    if prefix is None and core.is_termux():
        prefix = os.environ.get("PREFIX")
    if core.is_android() and not cfg.explicit_root:
        print(f"error: set SAVAGE_AI_ROOT first: export SAVAGE_AI_ROOT={PHONE_ROOT}", file=sys.stderr)
        return 2
    prob = storage_problem(cfg)
    if prob:
        print(prob, file=sys.stderr)
        return 2
    if not os.path.isdir(cfg.root):
        if cfg.require_mount or os.path.exists(cfg.root):
            print(f"error: {cfg.root} is not a usable directory", file=sys.stderr)
            return 2
        os.makedirs(cfg.root, exist_ok=True)  # development fallback root only
    if not can_write(cfg.root):
        print(f"error: {cfg.root} is not writable by this user; Savage will not change permissions.", file=sys.stderr)
        return 2
    source = os.path.dirname(package_dir())
    for d in ("src", "bin", "config", "logs", "tmp"):
        os.makedirs(cfg.path(d), exist_ok=True)
    install_app(cfg, source)
    done = write_launchers(cfg, source, prefix)
    print("Bootstrap complete. Launcher(s): " + ", ".join(done))
    if len(done) < 2:
        print(f"Add to PATH:  export PATH={cfg.path('bin')}:$PATH")
    print("Next:  savage doctor")
    return 0


if __name__ == "__main__":
    sys.exit(main())
