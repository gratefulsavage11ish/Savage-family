import io, json, os, shutil, sqlite3, subprocess, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from savage import bootstrap, cli, doctor, memory
from savage.config import Config

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # savage-ai/


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "root")
        os.makedirs(self.root)
        self.prefix = os.path.join(self.tmp.name, "prefix")
        os.makedirs(os.path.join(self.prefix, "bin"))
        self.env = {"SAVAGE_AI_ROOT": self.root, "SAVAGE_SOURCE_DIR": SRC}
        self.cfg = Config(env=self.env)

    def tearDown(self):
        self.tmp.cleanup()

    def doc(self, check=False, yes=True, answers=None, verbose=False, cfg=None):
        out = io.StringIO()
        it = iter(answers or [])

        def inp(_):
            try:
                return next(it)
            except StopIteration:
                raise EOFError
        d = doctor.Doctor(cfg or self.cfg, check, yes, verbose, inp, out, self.prefix)
        rc = d.run()
        return rc, out.getvalue(), d

    def snapshot(self):
        return sorted(os.path.relpath(os.path.join(dp, f), self.root)
                      for dp, dn, fn in os.walk(self.root) for f in fn + dn)

    def install(self):
        rc, out, _ = self.doc()
        self.assertEqual(rc, 0, out)


class TestFresh(Base):
    def test_fresh_install_yes(self):
        rc, out, d = self.doc()
        self.assertEqual(rc, 0, out)
        self.assertIn("CORE SYSTEM READY", out)
        self.assertIn("Operator          SAFE MODE", out)
        self.assertIn("llama.cpp         NOT INSTALLED", out)
        for dname in doctor.DIRS:
            self.assertTrue(os.path.isdir(os.path.join(self.root, dname)), dname)
        st = json.load(open(os.path.join(self.root, "config", "install-state.json")))
        self.assertIn("memory", st["stages"])
        self.assertTrue(os.path.getsize(os.path.join(self.root, "logs", "doctor.log")) > 0)
        # launcher works from a clean environment
        p = subprocess.run([os.path.join(self.prefix, "bin", "savage"), "version"], capture_output=True, text=True,
                           env={"PATH": os.environ["PATH"]})
        self.assertEqual(p.returncode, 0, p.stderr)
        # selftest left no residue
        db = sqlite3.connect(os.path.join(self.root, "memory", "savage.db"))
        self.assertEqual(db.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 0)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 0)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM skills").fetchone()[0], 6)
        self.assertEqual(os.listdir(os.path.join(self.root, "tmp")), [])

    def test_interactive_prompts_and_decline(self):
        prompts = []
        out = io.StringIO()
        d = doctor.Doctor(self.cfg, False, False, False, lambda q: prompts.append(q) or "n", out, self.prefix)
        self.assertEqual(d.run(), 1)
        self.assertEqual(prompts, ["    Create missing directories? [Y/n] "])
        self.assertFalse(os.path.exists(os.path.join(self.root, "memory")))

    def test_interactive_accept_default(self):
        rc, out, _ = self.doc(yes=False, answers=[""] * 12)
        self.assertEqual(rc, 0, out)

    def test_no_input_is_safe(self):
        rc, out, _ = self.doc(yes=False)
        self.assertEqual(rc, 1)
        self.assertEqual(self.snapshot(), [])


class TestCheck(Base):
    def test_check_changes_nothing(self):
        rc, out, _ = self.doc(check=True, yes=False)
        self.assertEqual(rc, 1)
        self.assertIn("ACTION NEEDED", out)
        self.assertEqual(self.snapshot(), [])

    def test_check_with_yes_is_ignored(self):
        out = io.StringIO()
        rc = doctor.main(self.cfg, check=True, yes=True, out=out, prefix=self.prefix)
        self.assertEqual(rc, 1)
        self.assertEqual(self.snapshot(), [])

    def test_check_on_healthy_install(self):
        self.install()
        before = self.snapshot()
        rc, out, _ = self.doc(check=True, yes=False)
        self.assertEqual(rc, 0, out)
        self.assertIn("read-only check", out)
        self.assertEqual(self.snapshot(), before)


class TestResume(Base):
    def test_rerun_is_idempotent_and_preserves_data(self):
        self.install()
        m = memory.Memory(self.cfg)
        m.add_message(m.session(), "user", "keep me")
        m.close()
        cfgp = os.path.join(self.root, "config", "savage.json")
        c = json.load(open(cfgp)); c["threads"] = 2; json.dump(c, open(cfgp, "w"))
        unknown = os.path.join(self.root, "models", "mine.gguf"); open(unknown, "w").write("x")
        rc, out, _ = self.doc()
        self.assertEqual(rc, 0)
        self.assertNotIn("[→]", out.replace("[>]", "[→]"))
        self.assertEqual(json.load(open(cfgp))["threads"], 2)
        self.assertTrue(os.path.exists(unknown))
        self.assertEqual(memory.Memory(self.cfg).stats()["messages"], 1)

    def test_partial_install_resumes(self):
        self.install()
        shutil.rmtree(os.path.join(self.root, "src"))
        os.remove(os.path.join(self.root, "memory", "savage.db"))
        os.remove(os.path.join(self.root, "bin", "savage"))
        shutil.rmtree(os.path.join(self.root, "memory"))
        rc, out, _ = self.doc()
        self.assertEqual(rc, 0, out)
        self.assertTrue(os.path.isfile(os.path.join(self.root, "memory", "savage.db")))

    def test_failure_midway_then_resume(self):
        with mock.patch.object(doctor.Doctor, "c_config", side_effect=RuntimeError("boom")):
            rc, out, d = self.doc()
        self.assertEqual(rc, 1)
        self.assertEqual(d.res("app"), doctor.PASS)
        self.assertEqual(d.res("config"), doctor.FAIL)
        rc, out, d = self.doc()
        self.assertEqual(rc, 0, out)

    def test_state_file_not_trusted(self):
        self.install()
        os.remove(os.path.join(self.root, "config", "savage.json"))
        rc, out, d = self.doc(check=True, yes=False)
        self.assertEqual(rc, 1)
        self.assertEqual(d.res("config"), doctor.ACTION)
        st = json.load(open(os.path.join(self.root, "config", "install-state.json")))
        self.assertIn("config", st["stages"])  # check mode must not rewrite state

    def test_corrupt_state_ignored(self):
        self.install()
        open(os.path.join(self.root, "config", "install-state.json"), "w").write("{nope")
        rc, out, _ = self.doc()
        self.assertEqual(rc, 0, out)


class TestRepairs(Base):
    def test_missing_memory_db(self):
        self.install()
        os.remove(os.path.join(self.root, "memory", "savage.db"))
        rc, out, _ = self.doc()
        self.assertEqual(rc, 0, out)
        self.assertEqual(memory.inspect(os.path.join(self.root, "memory", "savage.db"))["version"], memory.LATEST)

    def test_old_v0_db_migrated_with_backup(self):
        self.install()
        p = os.path.join(self.root, "memory", "savage.db")
        os.remove(p)
        db = sqlite3.connect(p)
        db.executescript(memory.MIGRATIONS[0][1]); db.execute("INSERT INTO sessions VALUES('a',1,1)"); db.commit(); db.close()
        rc, out, _ = self.doc(check=True, yes=False)
        self.assertIn("migration", out)
        rc, out, _ = self.doc()
        self.assertEqual(rc, 0, out)
        self.assertEqual(memory.Memory(self.cfg).stats()["sessions"], 1)
        self.assertTrue(os.listdir(os.path.join(self.root, "backups")))

    def test_future_db_not_touched(self):
        self.install()
        p = os.path.join(self.root, "memory", "savage.db")
        db = sqlite3.connect(p); db.execute("PRAGMA user_version=99"); db.commit(); db.close()
        rc, out, _ = self.doc()
        self.assertEqual(rc, 1)
        self.assertEqual(memory.inspect(p)["version"], 99)

    def test_corrupt_db_not_touched(self):
        self.install()
        p = os.path.join(self.root, "memory", "savage.db")
        open(p, "wb").write(b"not a database" * 50)
        rc, out, _ = self.doc()
        self.assertEqual(rc, 1)
        self.assertEqual(open(p, "rb").read(), b"not a database" * 50)

    def test_missing_dirs(self):
        self.install()
        shutil.rmtree(os.path.join(self.root, "knowledge")); shutil.rmtree(os.path.join(self.root, "engagements"))
        rc, out, _ = self.doc()
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isdir(os.path.join(self.root, "knowledge")))

    def test_dir_is_file_not_touched(self):
        open(os.path.join(self.root, "models"), "w").write("x")
        rc, out, _ = self.doc()
        self.assertEqual(rc, 1)
        self.assertTrue(os.path.isfile(os.path.join(self.root, "models")))

    def test_missing_or_stale_launcher(self):
        self.install()
        os.remove(os.path.join(self.prefix, "bin", "savage"))
        open(os.path.join(self.root, "bin", "savage"), "w").write("#!/bin/sh\necho stale\n")
        rc, out, d = self.doc(check=True, yes=False)
        self.assertEqual(d.res("launcher"), doctor.ACTION)
        rc, out, d = self.doc()
        self.assertEqual(rc, 0, out)
        self.assertTrue(os.path.exists(os.path.join(self.prefix, "bin", "savage")))

    def test_outdated_app_updated(self):
        self.install()
        open(os.path.join(self.root, "src", "savage", "agents.py"), "a").write("\n# stale\n")
        rc, out, d = self.doc(check=True, yes=False)
        self.assertEqual(d.res("app"), doctor.ACTION)
        self.assertEqual(self.doc()[0], 0)

    def test_broken_config_backed_up(self):
        self.install()
        p = os.path.join(self.root, "config", "savage.json")
        open(p, "w").write('{"threads": "lots", "context_size": 2048}')
        rc, out, _ = self.doc()
        self.assertEqual(rc, 0, out)
        c = json.load(open(p))
        self.assertEqual(c["context_size"], 2048)
        self.assertEqual(c["threads"], 4)
        self.assertTrue(os.listdir(os.path.join(self.root, "backups")))

    def test_false_agent_registry_repaired(self):
        self.install()
        p = os.path.join(self.root, "agents", "registry.json")
        r = json.load(open(p)); r["agents"][1]["status"] = "READY"; json.dump(r, open(p, "w"))
        self.assertEqual(self.doc(check=True, yes=False)[2].res("agents"), doctor.ACTION)
        self.assertEqual(self.doc()[0], 0)
        self.assertEqual([a["status"] for a in json.load(open(p))["agents"]],
                         ["READY", "SKELETON", "SKELETON", "SAFE MODE"])

    def test_missing_inference_is_not_failure(self):
        rc, out, d = self.doc()
        self.assertEqual(rc, 0)
        self.assertIn("NOT INSTALLED", out)


class TestStorage(Base):
    def test_unmounted_stops(self):
        cfg = Config(env=dict(self.env, SAVAGE_REQUIRE_MOUNT="1"))
        with mock.patch.object(doctor, "is_mount_point", return_value=False):
            rc, out, _ = self.doc(cfg=cfg)
        self.assertEqual(rc, 2)
        self.assertIn("SAVAGE AI STORAGE NOT MOUNTED", out)
        self.assertEqual(self.snapshot(), [])

    def test_missing_required_root_not_created(self):
        root = os.path.join(self.tmp.name, "gone")
        cfg = Config(env={"SAVAGE_AI_ROOT": root, "SAVAGE_REQUIRE_MOUNT": "1"})
        rc, out, _ = self.doc(cfg=cfg)
        self.assertEqual(rc, 2)
        self.assertFalse(os.path.exists(root))

    def test_mounted_ok(self):
        cfg = Config(env=dict(self.env, SAVAGE_REQUIRE_MOUNT="1"))
        with mock.patch.object(doctor, "is_mount_point", return_value=True):
            rc, out, _ = self.doc(cfg=cfg)
        self.assertEqual(rc, 0, out)

    def test_phone_root_requires_mount(self):
        self.assertTrue(Config(env={"SAVAGE_AI_ROOT": "/data/local/savage-ai"}).require_mount)
        self.assertFalse(self.cfg.require_mount)

    def test_read_only_root(self):
        with mock.patch.object(doctor, "can_write", return_value=False):
            rc, out, _ = self.doc()
        self.assertEqual(rc, 2)
        self.assertIn("not writable", out)
        self.assertEqual(self.snapshot(), [])

    def test_noexec(self):
        with mock.patch.object(doctor.core, "check_exec", return_value=False):
            rc, out, _ = self.doc()
        self.assertEqual(rc, 2)
        self.assertIn("noexec", out)

    def test_android_requires_explicit_root(self):
        cfg = Config(env={})
        with mock.patch.object(doctor.core, "is_android", return_value=True):
            rc, out, _ = self.doc(cfg=cfg, check=True)
        self.assertIn("SAVAGE_AI_ROOT is not set", out)
        self.assertEqual(rc, 2)

    def test_cli_refuses_unmounted(self):
        cfg = Config(env=dict(self.env, SAVAGE_REQUIRE_MOUNT="1"))
        with mock.patch.object(doctor, "is_mount_point", return_value=False):
            self.assertEqual(cli.main(["status"], cfg), 2)
        self.assertEqual(self.snapshot(), [])

    def test_never_runs_forbidden_commands(self):
        with mock.patch("subprocess.run", wraps=subprocess.run) as r:
            self.doc()
        progs = {os.path.basename(str(c.args[0][0])) for c in r.call_args_list}
        for bad in ("mkfs", "mkfs.ext4", "losetup", "mount", "umount", "fsck", "e2fsck", "resize2fs",
                    "setenforce", "su", "sudo", "tsu"):
            self.assertNotIn(bad, progs)


class TestSafety(Base):
    def test_yes_does_not_approve_unsafe(self):
        d = doctor.Doctor(self.cfg, yes=True, inp=lambda _: "n", out=io.StringIO())
        self.assertFalse(d.confirm("format?", safe=False))
        self.assertTrue(d.confirm("create dirs?", safe=True))

    def test_verbose(self):
        self.install()
        rc, out, _ = self.doc(check=True, yes=False, verbose=True)
        self.assertIn("context_size", out)


class TestBootstrap(Base):
    def test_bootstrap_then_doctor_then_cli(self):
        rc = bootstrap.main(self.cfg, self.prefix)
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isfile(os.path.join(self.root, "src", "savage", "doctor.py")))
        self.assertFalse(os.path.exists(os.path.join(self.root, "memory")))  # doctor's job
        env = {"PATH": os.environ["PATH"] + os.pathsep + os.path.join(self.prefix, "bin")}
        sav = os.path.join(self.prefix, "bin", "savage")
        p = subprocess.run([sav, "doctor", "--yes"], capture_output=True, text=True, env=env, input="")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("CORE SYSTEM READY", p.stdout)
        p = subprocess.run([sav], capture_output=True, text=True, env=env, input="agents\nhi\nexit\n")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("Savage >", p.stdout)
        self.assertIn("Code       SKELETON", p.stdout)
        self.assertIn("not configured", p.stdout)

    def test_bootstrap_refuses_unmounted(self):
        cfg = Config(env=dict(self.env, SAVAGE_REQUIRE_MOUNT="1"))
        with mock.patch.object(doctor, "is_mount_point", return_value=False), mock.patch.object(bootstrap, "storage_problem", doctor.storage_problem):
            self.assertEqual(bootstrap.main(cfg, self.prefix), 2)
        self.assertEqual(self.snapshot(), [])

    def test_script_exists_and_small(self):
        s = os.path.join(os.path.dirname(SRC), "scripts", "bootstrap-termux.sh")
        self.assertTrue(os.access(s, os.X_OK))
        self.assertLess(len(open(s).read().splitlines()), 20)


if __name__ == "__main__":
    unittest.main()
