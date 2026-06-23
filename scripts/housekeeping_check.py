"""Vault + git housekeeping drift-check (mechanical, deterministic, ~1s, no LLM).

Run every /loop tick as a cheap gate and at session boundaries. Reports DRIFT the campaign accretes
silently: uncommitted/untracked source & journals, unpushed commits, dangling [[wikilinks]], MEMORY.md
pointer drift, and the commit-criteria trap (a gitignored cache whose generator script isn't committed).
Exit code 0 = clean, 1 = drift found (so it can gate CI / loop ticks). The JUDGMENT checks (did an insight
deserve a C-/L-/M- note? are journals complete?) stay with the agent per M-001 — this only flags mechanics.

Usage: python scripts/housekeeping_check.py [--memory-dir DIR]
See vault/methodology/M-general-housekeeping-cadence.md and
    vault/methodology/M-general-commit-criteria-reproduce-reconstruct-trace.md
"""
import subprocess, sys, re, glob, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEM_DIR = Path("/home/julian/.claude/projects/-home-julian-Projects-esa-spoc-26-3/memory")
for i, a in enumerate(sys.argv):
    if a == "--memory-dir" and i + 1 < len(sys.argv):
        MEM_DIR = Path(sys.argv[i + 1])


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True).stdout


def check_git_state():
    """Uncommitted vault journals, untracked source scripts, unpushed commits."""
    findings = []
    status = git("status", "--porcelain")
    vault_dirty = [l for l in status.splitlines() if " vault/" in l or l[3:].startswith("vault/")]
    scripts_untracked = [l for l in status.splitlines() if l.startswith("??") and "scripts/" in l]
    if vault_dirty:
        findings.append(("VAULT-UNCOMMITTED", f"{len(vault_dirty)} vault file(s) uncommitted (untraceable result)",
                         [l[3:] for l in vault_dirty[:8]]))
    if scripts_untracked:
        findings.append(("SCRIPT-UNTRACKED", f"{len(scripts_untracked)} untracked script(s) (reproducibility gap)",
                         [l[3:] for l in scripts_untracked[:8]]))
    unpushed = [l for l in git("log", "--oneline", "@{u}..").splitlines()]
    if unpushed:
        findings.append(("UNPUSHED", f"{len(unpushed)} commit(s) not pushed to remote", unpushed[:5]))
    return findings


def check_dangling_links():
    """[[wikilink]] targets with no matching vault note file."""
    nodes = {Path(f).stem for f in glob.glob(str(ROOT / "vault/**/*.md"), recursive=True)}
    link_re = re.compile(r"\[\[([^\]|#]+)")
    dangling = {}
    for f in glob.glob(str(ROOT / "vault/**/*.md"), recursive=True):
        txt = Path(f).read_text(encoding="utf-8", errors="ignore")
        for m in link_re.findall(txt):
            tgt = m.strip().split("/")[-1]
            if tgt and tgt not in nodes and not tgt.endswith(".base"):
                dangling.setdefault(tgt, []).append(Path(f).name)
    if dangling:
        sample = sorted(dangling)[:10]
        return [("DANGLING-LINK", f"{len(dangling)} [[link]] target(s) with no matching note", sample)]
    return []


def check_memory_pointers():
    """MEMORY.md pointer <-> file consistency (pointer to missing file; file with no pointer)."""
    findings = []
    idx = MEM_DIR / "MEMORY.md"
    if not idx.exists():
        return findings
    idx_txt = idx.read_text(encoding="utf-8", errors="ignore")
    pointed = set(re.findall(r"\(([\w./-]+\.md)\)", idx_txt))
    files = {f.name for f in MEM_DIR.glob("*.md") if f.name != "MEMORY.md"}
    missing = [p for p in pointed if p not in files]
    orphan = [f for f in files if f not in pointed]
    if missing:
        findings.append(("MEMORY-POINTER-DEAD", f"{len(missing)} MEMORY.md pointer(s) to missing file", missing[:8]))
    if orphan:
        findings.append(("MEMORY-FILE-ORPHAN", f"{len(orphan)} memory file(s) with no MEMORY.md pointer", orphan[:8]))
    return findings


def check_cache_without_generator():
    """Commit-criteria trap: a gitignored cache/ file whose producing script isn't committed."""
    cache_dir = ROOT / "cache"
    if not cache_dir.exists():
        return []
    tracked_scripts = set(git("ls-files", "scripts/").splitlines())
    blob = "\n".join((ROOT / s).read_text(errors="ignore") for s in tracked_scripts if (ROOT / s).exists())
    # strip variable suffixes (shard _w0of3, seed _s100, _NNN) so dynamic f-string names still match a base token
    strip = re.compile(r"(_w\d+of\d+|_s\d+|_\d+|of\d+)+$")
    orphan_caches = []
    for c in cache_dir.iterdir():
        if not c.is_file():
            continue
        base = strip.sub("", c.stem)
        # match full name OR the stripped base token (>=6 chars to avoid trivial hits) in any committed script
        if c.name in blob or (len(base) >= 6 and base in blob):
            continue
        orphan_caches.append(c.name)
    if orphan_caches:
        return [("CACHE-NO-GENERATOR", f"{len(orphan_caches)} cache file(s) not regenerable from a committed script",
                 orphan_caches[:8])]
    return []


def main():
    all_findings = []
    for fn in (check_git_state, check_dangling_links, check_memory_pointers, check_cache_without_generator):
        all_findings += fn()
    print("=" * 64)
    print("HOUSEKEEPING DRIFT-CHECK")
    print("=" * 64)
    if not all_findings:
        print("CLEAN — no mechanical drift. (Judgment checks per M-001 still apply.)")
        return 0
    for code, summary, items in all_findings:
        print(f"\n[{code}] {summary}")
        for it in items:
            print(f"    - {it}")
    print(f"\n{len(all_findings)} drift categor(ies). Fix mechanical items; then run the M-001 judgment review.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
