"""Savage Commander: orchestration skeleton. Never fakes model output."""
import logging, re
from .providers import get_providers

log = logging.getLogger("savage")

# Deterministic local intents -> skill (keyword routing, no LLM)
INTENTS = [
    (r"\b(system|running on|os|platform|device)\b", "system_info"),
    (r"\b(ram|memory|swap)\b", "memory_info"),
    (r"\b(disk|storage|space|free)\b", "disk_info"),
    (r"\bgit\b", "git_status"),
]


class Commander:
    def __init__(self, cfg, mem, registry):
        self.cfg, self.mem, self.reg = cfg, mem, registry
        self.providers = get_providers(cfg)

    def provider_status(self):
        return [p.status() for p in self.providers]

    def handle(self, sid, request):
        """Return structured result dict."""
        tid = self.mem.add_task(sid, request)
        self.mem.add_message(sid, "user", request, tid)
        res = {"task_id": tid, "request": request, "inference": "NOT CONFIGURED",
               "skills_available": self.reg.names(), "skills_run": [], "output": "", "status": "DONE"}
        try:
            active = next((p for p in self.providers if p.available()), None)
            res["providers"] = [(s["provider"], s["status"]) for s in self.provider_status()]
            low = request.lower()
            for pat, skill in INTENTS:
                if re.search(pat, low):
                    res["skills_run"].append(skill)
                    res["output"] += f"[{skill}] {self.reg.run(skill)}\n"
                    break
            if active:
                res["inference"] = "READY"
                try:
                    res["output"] += active.generate(request)
                except NotImplementedError:
                    res["inference"] = "NOT IMPLEMENTED"
            if res["inference"] != "READY":
                res["output"] += ("Inference is not configured: no local model/llama.cpp is active, "
                                  "so I cannot answer free-form requests yet. Deterministic skills still work "
                                  "(type 'skills').")
        except Exception as e:  # keep CLI alive
            log.exception("task %s failed", tid)
            res["status"], res["output"] = "ERROR", f"Task failed: {e.__class__.__name__}: {e}"
        res["output"] = res["output"].strip()
        self.mem.add_message(sid, "assistant", res["output"], tid)
        self.mem.add_event(sid, "task_" + res["status"].lower(), ",".join(res["skills_run"]), tid)
        self.mem.finish_task(tid, res["status"], res["output"])
        return res
