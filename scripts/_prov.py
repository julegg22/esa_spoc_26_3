"""Run-time provenance stamp — capture the EXACT code version a run used, AT run time,
so the result self-documents (instead of being reconstructed later, which usually fails).

Every experiment script calls `prov.stamp(__file__, seed=...)` at the top of main(); the
`[PROV]` line lands in the run log. It records the short commit SHA, a DIRTY flag (working
tree not clean for this script -> the result maps to NO committed SHA), the script's own
content hash, the env, and a timestamp. When writing the E node, copy `commit=` into the
`commit:` frontmatter field; if DIRTY, the run is NOT reproducible from a SHA — commit first
for any run whose output gets banked (clean-tree-before-bank).
"""
import subprocess
import hashlib
import os
import sys
import time

ROOT = "/home/julian/Projects/esa_spoc_26_3"


def _git(*a):
    try:
        return subprocess.run(["git", "-C", ROOT, *a],
                              capture_output=True, text=True).stdout.strip()
    except Exception:
        return ""


def stamp(script_file, **kv):
    """Print a [PROV] line and return the provenance dict."""
    sha = _git("rev-parse", "--short", "HEAD") or "?"
    dirty = bool(_git("status", "--porcelain", "--", script_file))
    try:
        h = hashlib.sha1(open(script_file, "rb").read()).hexdigest()[:8]
    except Exception:
        h = "?"
    env = os.path.basename(os.environ.get("CONDA_PREFIX", "").strip()
                           or os.environ.get("VIRTUAL_ENV", "").strip())
    if not env and "/envs/" in sys.executable:               # micromamba python not "activated"
        env = sys.executable.split("/envs/")[-1].split("/")[0]
    env = env or "?"
    extra = " ".join(f"{k}={v}" for k, v in kv.items())
    line = (f"[PROV] commit={sha}{'+DIRTY' if dirty else ''} "
            f"script={os.path.basename(script_file)} sha1={h} env={env} "
            f"t={time.strftime('%Y-%m-%dT%H:%M:%S')} {extra}").rstrip()
    print(line, flush=True)
    return {"commit": sha, "dirty": dirty, "script_sha1": h, "env": env}
