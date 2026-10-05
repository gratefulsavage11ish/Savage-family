"""Permission classes and checks. All skills/operations must pass through check()."""
import enum


class Perm(enum.IntEnum):
    READ_ONLY = 0
    LOCAL = 1
    NETWORK = 2
    PRIVILEGED = 3
    TARGET_AFFECTING = 4


class PermissionDenied(Exception):
    pass


# Highest class allowed per operator mode. SAFE allows read-only only.
MODE_MAX = {"SAFE": Perm.READ_ONLY}


def allowed(perm, mode="SAFE"):
    return perm <= MODE_MAX.get(str(mode).upper(), Perm.READ_ONLY)  # unknown mode -> safest


def check(perm, mode="SAFE"):
    if not allowed(perm, mode):
        raise PermissionDenied(f"{perm.name} not permitted in {str(mode).upper()} mode")
