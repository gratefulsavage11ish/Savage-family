import argparse, json, os, sqlite3, sys, time
from . import __version__, core, doctor
from .agents import agent_list
from .commander import Commander
from .config import Config, setup_logging
from .memory import Memory
from .doctor import storage_problem
from .providers import get_providers
from .skills import Registry

COMMANDS = ["help", "status", "doctor", "memory", "skills", "agents", "model", "history", "clear", "version", "exit", "quit"]
HELP = """Commands: help status doctor memory skills agents model history clear version exit
Anything else goes to Savage Commander."""


class App:
    def __init__(self, cfg, out=None):
        self.cfg, self.out = cfg, out or sys.stdout
        cfg.ensure_dirs()
        self.log = setup_logging(cfg)
        self.mem = Memory(cfg)
        self.sid = self.mem.session()
        self.reg = Registry(cfg, self.mem)
        self.cmd = Commander(cfg, self.mem, self.reg)

    def p(self, s=""):
        print(s, file=self.out)

    def close(self):
        self.mem.close()

    def prefix(self):
        return os.environ.get("PREFIX") if core.is_termux() else None

    def model_status(self):
        return get_providers(self.cfg)[0].status()

    def header(self):
        ms = self.model_status()
        mode = str(self.cfg.get("operator_mode")).upper()
        self.p("=" * 32 + "\n          SAVAGE AI\n" + "=" * 32)
        self.p(f"Device: {'Android ' if core.is_android() else ''}{core.platform.machine()}")
        self.p("Mode: LOCAL\nCommander: READY\nMemory: READY\nSkills: READY")
        self.p(f"Operator: {mode} MODE")
        self.p(f"Model: {ms['status']}")
        self.p(f"Session: {self.sid}  (type 'help')")

    def run_command(self, line):
        """Return False to exit."""
        parts = line.split()
        c = parts[0].lower()
        if c in ("exit", "quit"):
            return False
        if c == "help":
            self.p(HELP)
        elif c == "version":
            self.p(__version__)
        elif c == "status":
            for k, v in core.status(self.cfg).items():
                self.p(f"{k}: {v}")
        elif c == "doctor":
            # In the REPL doctor is read-only unless --yes is given; run `savage doctor` for interactive repair.
            yes = "--yes" in parts or "-y" in parts
            doctor.main(self.cfg, check=not yes, yes=yes, verbose="--verbose" in parts or "-v" in parts,
                        out=self.out, prefix=self.prefix())
        elif c == "memory":
            for k, v in self.mem.stats().items():
                self.p(f"{k}: {v}")
            self.p(f"session: {self.sid}")
        elif c == "skills":
            for s in self.reg.skills.values():
                self.p(f"{s.name:15} {s.perm.name:10} {s.status:6} {s.desc}")
        elif c == "agents":
            for n, s in agent_list(self.cfg):
                self.p(f"{n:10} {s}")
        elif c == "model":
            for k, v in self.model_status().items():
                self.p(f"{k}: {v}")
        elif c == "history":
            n = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
            rows = self.mem.history(self.sid, n)
            if not rows:
                self.p("(no history)")
            for ts, _, role, content, tid in rows:
                self.p(f"{time.strftime('%m-%d %H:%M', time.localtime(ts))} {role[:4]:4} {content[:100].replace(chr(10), ' ')}")
        elif c == "clear":
            self.p("\033[2J\033[H" if getattr(self.out, "isatty", lambda: False)() else "")
        return True

    def handle_line(self, line):
        line = line.strip()
        if not line:
            return True
        if line.split()[0].lower() in COMMANDS:
            self.mem.add_message(self.sid, "command", line)
            try:
                return self.run_command(line)
            except Exception as e:
                self.log.exception("command failed: %s", line.split()[0])
                self.p(f"error: {e.__class__.__name__}: {e}")
                return True
        res = self.cmd.handle(self.sid, line)
        self.p(f"[{res['task_id']}] {res['output']}")
        return True

    def repl(self, inp=input):
        self.header()
        while True:
            try:
                line = inp("Savage > ")
            except EOFError:
                self.p()
                break
            except KeyboardInterrupt:
                self.p("\n(Ctrl+C: type 'exit' to quit)")
                continue
            try:
                if not self.handle_line(line):
                    break
            except KeyboardInterrupt:
                self.p("\n(interrupted)")
            except Exception as e:
                self.log.exception("unhandled")
                self.p(f"error: {e.__class__.__name__}")
        self.p("bye")


def main(argv=None, cfg=None):
    p = argparse.ArgumentParser(prog="savage")
    p.add_argument("command", nargs="?", choices=["doctor", "status", "version", "model", "memory", "skills", "agents"])
    p.add_argument("--json", action="store_true", help="machine-readable output (status)")
    p.add_argument("--check", action="store_true", help="doctor: read-only inspection")
    p.add_argument("--yes", "-y", action="store_true", help="doctor: approve SAFE repairs automatically")
    p.add_argument("--verbose", "-v", action="store_true", help="doctor: detailed diagnostics")
    a = p.parse_args(argv)
    cfg = cfg or Config()
    if a.command == "version":
        print(__version__)
        return 0
    if a.command == "doctor":
        return doctor.main(cfg, a.check, a.yes, a.verbose, prefix=os.environ.get("PREFIX") if core.is_termux() else None)
    if a.command == "status" and a.json:
        print(json.dumps(core.status(cfg)))
        return 0
    prob = storage_problem(cfg)
    if prob:
        print(prob + "\nRun: savage doctor", file=sys.stderr)
        return 2
    try:
        app = App(cfg)
    except (OSError, RuntimeError, sqlite3.Error) as e:
        print(f"error: cannot start Savage with root {cfg.root}: {e}\n"
              "If this is /data/local/savage-ai, your non-root Termux user may lack access; "
              "Savage will not change permissions. Run: savage doctor --check", file=sys.stderr)
        return 2
    try:
        if a.command:
            app.run_command(a.command)
            return 0
        app.repl()
        return 0
    finally:
        app.close()
