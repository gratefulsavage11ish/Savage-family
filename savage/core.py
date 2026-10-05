"""Core checks and status. No UI code; a future Android app calls this via the CLI (--json)."""
import os, platform, shutil, subprocess, tempfile

DEFAULT_ROOT = "/data/local/savage-ai"
MIN_RAM_MIB = 2500
MAX_OUT = 4096  # bound subprocess output


def run(cmd, timeout=10):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (p.stdout + p.stderr)[:MAX_OUT].strip()
    except Exception:
        return ""


def meminfo():
    d = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                k, _, v = line.partition(":")
                d[k] = int(v.split()[0]) // 1024
    except OSError:
        pass
    return d


def is_android():
    return "ANDROID_ROOT" in os.environ or os.path.exists("/system/build.prop")


def is_termux():
    return "com.termux" in os.environ.get("PREFIX", "") or bool(os.environ.get("TERMUX_VERSION"))


def check_exec(path):
    """Write a tiny script into path and execute it."""
    try:
        with tempfile.NamedTemporaryFile("w", dir=path, suffix=".sh", delete=False) as f:
            f.write("#!/bin/sh\nexit 0\n")
            name = f.name
        try:
            os.chmod(name, 0o700)
            return subprocess.run([name], timeout=5).returncode == 0
        finally:
            os.unlink(name)
    except Exception:
        return False


def status(cfg):
    r = cfg.root
    mi = meminfo()
    s = {"version": __import__("savage").__version__, "root": r, "root_explicit": cfg.explicit_root,
         "arch": platform.machine(), "android": is_android(), "termux": is_termux(),
         "ram_total_mib": mi.get("MemTotal"), "ram_available_mib": mi.get("MemAvailable"),
         "swap_total_mib": mi.get("SwapTotal"), "model": None}
    if r and os.path.isdir(r):
        du = shutil.disk_usage(r)
        s["disk_free_gib"] = round(du.free / 2**30, 1)
    from .providers import LlamaCppProvider
    ms = LlamaCppProvider(cfg).status()
    s["model"] = ms["status"]
    s["operator"] = str(cfg.get("operator_mode")).upper()
    return s
