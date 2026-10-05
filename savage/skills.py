"""Skill registry and deterministic READ_ONLY built-ins."""
import os, platform, shutil, subprocess
from . import permissions as P
from .permissions import Perm

MAX_OUT = 4096
MAX_FILE = 64 * 1024
MAX_LIST = 200


class Skill:
    def __init__(self, name, perm, desc, fn, status="READY"):
        self.name, self.perm, self.desc, self.fn, self.status = name, perm, desc, fn, status


class Registry:
    def __init__(self, cfg, mem=None):
        self.cfg, self.mem = cfg, mem
        self.skills = {}
        for s in (
            Skill("system_info", Perm.READ_ONLY, "OS, arch, Python, CPU count", self.system_info),
            Skill("memory_info", Perm.READ_ONLY, "RAM and swap from /proc/meminfo", self.memory_info),
            Skill("disk_info", Perm.READ_ONLY, "Free/total space of Savage root", self.disk_info),
            Skill("git_status", Perm.READ_ONLY, "git status of a repo (short)", self.git_status),
            Skill("read_text_file", Perm.READ_ONLY, "Read text file under allowed paths", self.read_text_file),
            Skill("list_directory", Perm.READ_ONLY, "List directory under allowed paths", self.list_directory),
        ):
            self.skills[s.name] = s

    def sync(self):
        """Register built-in skills in the memory database."""
        for s in self.skills.values():
            self.mem.upsert_skill(s.name, s.perm.name, s.status, s.desc)

    def names(self):
        return sorted(self.skills)

    def allowed_paths(self):
        return [os.path.realpath(p) for p in (self.cfg.root, os.getcwd())]

    def safe_path(self, p):
        rp = os.path.realpath(os.path.expanduser(p))
        for base in self.allowed_paths():
            if rp == base or rp.startswith(base + os.sep):
                return rp
        raise P.PermissionDenied(f"path outside allowed locations: {p}")

    def run(self, name, *args):
        s = self.skills.get(name)
        if not s:
            raise KeyError(f"unknown skill: {name}")
        P.check(s.perm, self.cfg.get("operator_mode"))
        out = str(s.fn(*args))[:MAX_OUT]
        if self.mem:
            self.mem.add_event(None, "skill", name)
        return out

    # --- built-ins ---
    def system_info(self):
        return (f"{platform.system()} {platform.release()} {platform.machine()}; "
                f"Python {platform.python_version()}; CPUs {os.cpu_count()}")

    def memory_info(self):
        from .core import meminfo
        m = meminfo()
        return (f"RAM {m.get('MemTotal', '?')} MiB total, {m.get('MemAvailable', '?')} MiB available; "
                f"swap {m.get('SwapTotal', '?')} MiB")

    def disk_info(self, path=None):
        du = shutil.disk_usage(self.safe_path(path or self.cfg.root) if path else
                               (self.cfg.root if os.path.isdir(self.cfg.root) else os.path.expanduser("~")))
        g = 2**30
        return f"{du.free / g:.1f} GiB free of {du.total / g:.1f} GiB"

    def git_status(self, path=None):
        d = self.safe_path(path or os.getcwd())
        try:
            p = subprocess.run(["git", "-C", d, "status", "--short", "--branch"],
                               capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired) as e:
            return f"git unavailable: {e.__class__.__name__}"
        return (p.stdout + p.stderr).strip() or "clean"

    def read_text_file(self, path):
        p = self.safe_path(path)
        with open(p, "rb") as f:
            data = f.read(MAX_FILE + 1)
        if b"\0" in data:
            return "binary file; refusing to display"
        t = data[:MAX_FILE].decode("utf-8", "replace")
        return t + ("\n[truncated]" if len(data) > MAX_FILE else "")

    def list_directory(self, path="."):
        p = self.safe_path(path)
        names = sorted(os.listdir(p))
        out = [n + ("/" if os.path.isdir(os.path.join(p, n)) else "") for n in names[:MAX_LIST]]
        if len(names) > MAX_LIST:
            out.append(f"... {len(names) - MAX_LIST} more")
        return "\n".join(out)
