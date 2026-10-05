#!/bin/sh
# Phone environment check. Read-only except for a temp file in $SAVAGE_AI_ROOT.
SAVAGE_AI_ROOT="${SAVAGE_AI_ROOT:-}"
fail=0
ok()   { echo "[ OK ] $1"; }
warn() { echo "[WARN] $1"; }
bad()  { echo "[FAIL] $1"; fail=1; }

m=$(uname -m)
case "$m" in aarch64|arm64) ok "arch $m";; *) warn "arch $m (expected aarch64)";; esac
if [ -n "${ANDROID_ROOT:-}" ] || [ -e /system/build.prop ]; then ok android; else warn "Android not detected"; fi
case "${PREFIX:-}" in *com.termux*) ok termux;; *) warn "Termux not detected";; esac
command -v python3 >/dev/null 2>&1 && ok "python $(python3 -V 2>&1)" || bad "python3 missing (pkg install python)"
command -v git >/dev/null 2>&1 && ok git || bad "git missing (pkg install git)"
cc=""; for c in clang gcc cc; do command -v $c >/dev/null 2>&1 && { cc=$c; break; }; done
[ -n "$cc" ] && ok "compiler $cc" || bad "compiler missing (pkg install clang cmake make)"
mt=$(awk '/^MemTotal/{print int($2/1024)}' /proc/meminfo); ma=$(awk '/^MemAvailable/{print int($2/1024)}' /proc/meminfo)
st=$(awk '/^SwapTotal/{print int($2/1024)}' /proc/meminfo)
[ "${mt:-0}" -ge 2500 ] && ok "ram ${mt} MiB total, ${ma} MiB available" || warn "ram ${mt} MiB total (low)"
[ "${st:-0}" -gt 0 ] && ok "swap ${st} MiB" || warn "no swap"
if [ -z "$SAVAGE_AI_ROOT" ]; then bad "SAVAGE_AI_ROOT not set (export SAVAGE_AI_ROOT=/data/local/savage-ai)"
elif [ ! -d "$SAVAGE_AI_ROOT" ]; then bad "SAVAGE_AI_ROOT $SAVAGE_AI_ROOT is not a directory"
else
  ok "SAVAGE_AI_ROOT $SAVAGE_AI_ROOT"
  t="$SAVAGE_AI_ROOT/.doctor.$$"
  if ( : > "$t" ) 2>/dev/null; then
    ok "filesystem writable"
    printf '#!/bin/sh\nexit 0\n' > "$t"; chmod 700 "$t"
    "$t" 2>/dev/null && ok "filesystem executable" || bad "filesystem not executable (noexec?)"
    rm -f "$t"
  else bad "filesystem not writable"; fi
fi
exit $fail
