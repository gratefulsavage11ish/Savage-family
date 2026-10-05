"""Inference provider interface. Commander talks only to this; llama.cpp plugs in later."""
import glob, os


class Provider:
    name = "none"

    def status(self):
        raise NotImplementedError

    def available(self):
        return self.status()["status"] == "READY"

    def generate(self, prompt, **kw):
        raise NotImplementedError


class LlamaCppProvider(Provider):
    """Detection only for now; generate() is wired in the inference milestone."""
    name = "llama.cpp"

    def __init__(self, cfg):
        self.cfg = cfg

    def model_path(self):
        p = self.cfg.get("model_path")
        if p:
            return p
        found = sorted(glob.glob(self.cfg.path("models", "*.gguf")))
        return found[0] if found else ""

    def executable(self):
        return self.cfg.get("llama_cpp_executable") or self.cfg.path("bin", "llama-cli")

    def status(self):
        mp, exe = self.model_path(), self.executable()
        have_m = bool(mp) and os.path.isfile(mp)
        have_e = os.path.isfile(exe) and os.access(exe, os.X_OK)
        st = "READY" if (have_m and have_e) else "NOT INSTALLED"
        return {"provider": self.name, "status": st, "model_path": mp or None, "executable": exe,
                "model_present": have_m, "executable_present": have_e,
                "context_size": self.cfg.get("context_size"), "threads": self.cfg.get("threads")}

    def generate(self, prompt, **kw):
        raise NotImplementedError("llama.cpp inference is not implemented yet")


def get_providers(cfg):
    return [LlamaCppProvider(cfg)]
