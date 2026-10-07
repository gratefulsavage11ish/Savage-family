"""Configuration: SAVAGE_AI_ROOT, fallback storage, settings file, bounded logging."""
import json, logging, os
from logging.handlers import RotatingFileHandler

PHONE_ROOT = "/data/local/savage-ai"
DEFAULTS = {
    "model_path": "",            # empty -> first *.gguf in $ROOT/models
    "llama_cpp_executable": "",  # empty -> $ROOT/bin/llama-cli
    "context_size": 4096,
    "threads": 4,
    "log_level": "INFO",
    "operator_mode": "SAFE",
}
SECRET_HINTS = ("key", "token", "secret", "password")


class Config:
    def __init__(self, root=None, env=None):
        env = os.environ if env is None else env
        self.env = env
        r = root or env.get("SAVAGE_AI_ROOT", "")
        self.explicit_root = bool(r)
        if not r:
            r = os.path.join(os.path.expanduser("~"), ".savage-ai")
        self.root = os.path.abspath(r)
        # The phone filesystem must be a real mount; never silently use an unmounted directory.
        self.require_mount = self.root == PHONE_ROOT or env.get("SAVAGE_REQUIRE_MOUNT") == "1"
        self.settings = dict(DEFAULTS)
        self.settings.update(self._load_file())
        for k in DEFAULTS:
            v = env.get("SAVAGE_" + k.upper())
            if v is not None:
                self.settings[k] = type(DEFAULTS[k])(v) if isinstance(DEFAULTS[k], int) else v

    def path(self, *p):
        return os.path.join(self.root, *p)

    @property
    def config_file(self):
        return self.path("config", "savage.json")

    def _load_file(self):
        try:
            with open(self.config_file) as f:
                d = json.load(f)
            return {k: v for k, v in d.items() if k in DEFAULTS and not any(s in k for s in SECRET_HINTS)}
        except (OSError, ValueError):
            return {}

    def default_file_dict(self):
        d = {"schema": 1, "savage_ai_root": self.root}
        d.update(DEFAULTS)
        return d

    def ensure_dirs(self):
        for d in ("config", "memory", "logs", "models", "skills", "bin", "tmp"):
            os.makedirs(self.path(d), exist_ok=True)

    def get(self, k, default=None):
        return self.settings.get(k, default)


def setup_logging(cfg):
    """Rotating log: 256 KiB x 3 files max. File only; never prints to terminal."""
    log = logging.getLogger("savage")
    if log.handlers:
        return log
    log.setLevel(getattr(logging, str(cfg.get("log_level")).upper(), logging.INFO))
    log.propagate = False
    try:
        os.makedirs(cfg.path("logs"), exist_ok=True)
        h = RotatingFileHandler(cfg.path("logs", "savage.log"), maxBytes=256 * 1024, backupCount=2)
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)
    except OSError:
        log.addHandler(logging.NullHandler())
    return log
