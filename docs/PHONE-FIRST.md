# Savage AI — phone first

Target: rooted Android 16 ARM64, Termux, ~3.6 GiB RAM, runtime root `/data/local/savage-ai`
(an existing ext4 mount). This repo never creates, formats, mounts, resizes or repairs it, and
never assumes a loop-device number. No root is needed to run Savage.

## First install (Termux)

    git clone https://github.com/gratefulsavage11ish/stealth-savage && cd stealth-savage
    export SAVAGE_AI_ROOT=/data/local/savage-ai
    ./scripts/bootstrap-termux.sh      # copies the CLI into $SAVAGE_AI_ROOT/src, writes launcher
    savage doctor                      # builds/repairs everything else (asks Y/n)
    savage                             # interactive CLI ("Savage >")

Launcher: `$PREFIX/bin/savage` (already on PATH in Termux) plus `$SAVAGE_AI_ROOT/bin/savage`. If
`savage` is not found: `echo 'export PATH=/data/local/savage-ai/bin:$PATH' >> ~/.bashrc`.
Put `export SAVAGE_AI_ROOT=/data/local/savage-ai` in `~/.bashrc` too (the launcher also defaults to it).

## savage doctor

`savage doctor` interactive · `--check` read-only (only a probe file that is removed) ·
`--yes` approve SAFE repairs · `--verbose`. Exit: 0 ready, 1 not ready, 2 storage problem.

Stages: platform → storage → directories → Python venv → application → launcher →
configuration → memory (versioned SQLite migrations) → agents → skills → inference (reported,
optional) → self test → report. Each stage re-verifies real state, so reruns resume and never
redo finished work; `config/install-state.json` is only a progress record and is not trusted.
Log: `logs/doctor.log` (rotating, bounded).

**Storage guard:** if `SAVAGE_AI_ROOT` is `/data/local/savage-ai` (or `SAVAGE_REQUIRE_MOUNT=1`) and it
is not a mount point, doctor, bootstrap and the CLI stop with `SAVAGE AI STORAGE NOT MOUNTED` and
write nothing. Doctor never touches `/dev/block`, `/mnt/media_rw`, SELinux, boot settings, firewall
or network, and never downloads anything. Existing data it doesn't recognise is never deleted;
a changed database or config is backed up to `backups/` before repair; corrupt/newer databases are left alone.

## Layout
`models agents memory skills knowledge projects engagements logs config backups bin src tmp` (+ `venv`).
Without `SAVAGE_AI_ROOT`, development falls back to `~/.savage-ai` (on Android doctor refuses this).

## Settings
`config/savage.json` and/or env `SAVAGE_<NAME>`: `model_path`, `llama_cpp_executable`,
`context_size` (4096), `threads` (4), `log_level`, `operator_mode` (SAFE). No secrets are stored.

## Design
Stdlib-only Python core, separate from any UI. Commander reaches inference only through
`savage/providers.py`; skills and operations pass `savage/permissions.py`. Inference is not
installed in this milestone; Commander says so rather than inventing answers.
Tests: `cd savage-ai && python3 -m unittest discover -s tests`.
