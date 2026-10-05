import io, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from savage import cli, core
from savage.config import Config
from savage.memory import Memory
from savage.skills import Registry
from savage.commander import Commander
from savage.permissions import Perm, PermissionDenied, check
from savage.providers import LlamaCppProvider


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(root=self.tmp.name, env={})
        self.cfg.ensure_dirs()

    def tearDown(self):
        self.tmp.cleanup()

    def app(self):
        out = io.StringIO()
        a = cli.App(self.cfg, out)
        self.addCleanup(a.close)
        return a, out


class TestConfig(Base):
    def test_env_and_fallback(self):
        c = Config(env={"SAVAGE_AI_ROOT": "/x/y", "SAVAGE_CONTEXT_SIZE": "2048"})
        self.assertEqual(c.root, "/x/y")
        self.assertEqual(c.get("context_size"), 2048)
        d = Config(env={})
        self.assertFalse(d.explicit_root)
        self.assertTrue(d.root.endswith(".savage-ai"))
        self.assertEqual(d.get("operator_mode"), "SAFE")


class TestMemory(Base):
    def test_sessions_history(self):
        m = Memory(self.cfg)
        s = m.session()
        self.assertEqual(m.session(), s)  # resume
        self.assertNotEqual(m.session(resume=False), s)
        m.add_message(s, "user", "hi")
        self.assertEqual(m.history(s)[0][3], "hi")
        st = m.stats()
        self.assertEqual(st["messages"], 1)
        self.assertTrue(st["path"].startswith(os.path.join(self.tmp.name, "memory")))
        m.close()


class TestSkills(Base):
    def test_builtin(self):
        r = Registry(self.cfg)
        self.assertEqual(set(r.names()), {"system_info", "memory_info", "disk_info", "git_status",
                                          "read_text_file", "list_directory"})
        self.assertIn("CPUs", r.run("system_info"))
        self.assertIn("GiB", r.run("disk_info"))
        p = os.path.join(self.tmp.name, "a.txt")
        open(p, "w").write("hello")
        self.assertEqual(r.run("read_text_file", p), "hello")
        self.assertIn("a.txt", r.run("list_directory", self.tmp.name))
        r.run("memory_info"); r.run("git_status", self.tmp.name)

    def test_path_restriction(self):
        r = Registry(self.cfg)
        with self.assertRaises(PermissionDenied):
            r.run("read_text_file", "/etc/passwd")


class TestPermissions(unittest.TestCase):
    def test_safe_mode(self):
        check(Perm.READ_ONLY, "SAFE")
        for p in (Perm.LOCAL, Perm.NETWORK, Perm.PRIVILEGED, Perm.TARGET_AFFECTING):
            with self.assertRaises(PermissionDenied):
                check(p, "SAFE")
        with self.assertRaises(PermissionDenied):
            check(Perm.LOCAL, "bogus")


class TestCommander(Base):
    def test_no_inference(self):
        m = Memory(self.cfg); sid = m.session()
        c = Commander(self.cfg, m, Registry(self.cfg, m))
        r = c.handle(sid, "explain what system I'm running on")
        self.assertEqual(r["status"], "DONE")
        self.assertEqual(r["inference"], "NOT CONFIGURED")
        self.assertIn("system_info", r["skills_run"])
        self.assertIn("not configured", r["output"])
        self.assertEqual(m.stats()["tasks"], 1)
        r2 = c.handle(sid, "nonsense")
        self.assertEqual(r2["skills_run"], [])
        m.close()


class TestModel(Base):
    def test_not_installed(self):
        s = LlamaCppProvider(self.cfg).status()
        self.assertEqual(s["status"], "NOT INSTALLED")
        self.assertEqual(s["provider"], "llama.cpp")


class TestCLI(Base):
    def test_repl_start_exit(self):
        a, out = self.app()
        it = iter(["status", "doctor", "memory", "skills", "agents", "model", "help",
                     "history", "clear", "hello there", "exit"])
        a.repl(lambda _: next(it))
        t = out.getvalue()
        for s in ("SAVAGE AI", "Operator: SAFE MODE", "Model: NOT INSTALLED", "Commander  READY",
                  "SKELETON", "READ_ONLY", "bye"):
            self.assertIn(s, t)
        self.assertEqual(a.mem.stats()["tasks"], 1)

    def test_eof_and_ctrl_c(self):
        a, out = self.app()
        calls = iter([KeyboardInterrupt, EOFError])
        def inp(_):
            raise next(calls)
        a.repl(inp)
        self.assertIn("bye", out.getvalue())

    def test_history_and_resume(self):
        a, out = self.app()
        a.handle_line("hello")
        a.handle_line("history")
        self.assertIn("hello", out.getvalue())
        b, _ = self.app()
        self.assertEqual(a.sid, b.sid)

    def test_shell_subcommands(self):
        self.assertEqual(cli.main(["version"], self.cfg), 0)
        self.assertEqual(cli.main(["status"], self.cfg), 0)
        cli.main(["doctor", "--check"], self.cfg)

    def test_doctor_status(self):
        self.assertEqual(core.status(self.cfg)["model"], "NOT INSTALLED")


if __name__ == "__main__":
    unittest.main()
