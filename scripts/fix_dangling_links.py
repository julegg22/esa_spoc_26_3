"""One-off: resolve dangling [[wikilinks]] in the vault to current note files.

Strategy (safe-by-construction):
  1. BARE-ID  (`[[C-015]]`)            -> the unique current file with that ID prefix.
  2. TOPIC    (`[[C-011-cp-sat]]`)     -> a current file whose slug ends with / strongly overlaps the
     link's slug, REGARDLESS of ID (handles the historical ID-reassignment correctly: the old link's
     TOPIC is matched, not its stale number).
  Apply only CONFIDENT matches (unique target). Report ambiguous + genuinely-missing (incl. template NNN
  placeholders) without touching them. --apply to write; default is dry-run.
"""
import re, glob, os, sys
from collections import defaultdict

ROOT = "/home/julian/Projects/esa_spoc_26_3"
APPLY = "--apply" in sys.argv
files = [f for f in glob.glob(f"{ROOT}/vault/**/*.md", recursive=True) if "/_templates/" not in f]
stems = {os.path.basename(f)[:-3] for f in files}
STOP = {"ch1", "ch2", "ch3", "the", "and", "a", "of", "to", "on", "in", "for", "with", "large", "small",
        "medium", "v2", "v3", "and", "problem", "ch1trajectory", "ch2large", "ch2small"}

# Curated high-confidence semantic mappings the token-matcher cannot infer (memory-slug -> vault node;
# old concept name -> current concept; same-ID experiment reslugs). Validated against stems below.
MANUAL_MAP = {
    "anti-oscillation-discipline": "M-general-anti-oscillation-discipline",
    "basin-overarching-search": "M-general-basin-overarching-search",
    "foundation-then-search-methodology": "M-general-foundation-then-search",
    "deep-single-prompt-audit": "M-general-deep-single-prompt-audit",
    "architecture-change-on-large-gaps": "M-general-architecture-change-on-large-gaps",
    "methodology-triggers": "M-applying-methodology-triggers",
    "feedback-instrument-experiments": "M-general-instrument-experiments-before-launch",
    "competitor-algorithm-inference": "O-014-2026-06-07-competitor-algorithm-inference",
    "ch1-matching-solver-bound-refuted": "E-673-ch1-matching-solver-bound-REFUTED",
    "ch1-raan-feasibility-refuted": "E-047-ch1-raan-argp-feasibility-refuted",
    "C-001-lambert-two-point-bvp": "C-006-lambert-problem-and-orbital-tsp",
    "C-002-highs-mip-solver": "C-004-mip-and-mip-lns",
    "E-001-ch1-matching-mip-highs": "E-001-ch1-matching-first-attempts",
    "E-034-ch2-large-bank": "E-034-ch2-large-epoch-aware-reorder",
    "E-034-ch2-large-first-bank": "E-034-ch2-large-epoch-aware-reorder",
    # 2026-06-24 vault-consistency pass: memory-slug / old-ID -> current vault node (topic-verified)
    "ch1-eccentric-orbit-fix": "E-701-ch1-eccentric-departure-solver-fix",
    "ch1-coherent-model-r3": "A-2026-05-29-coherent-physics-model",
    "ch1-trajectory-mass-lever-exhausted": "E-049-ch1-trajectory-filled-pair-dof-exhausted",
    "ch1-trajectory-udp-floor-confirmed": "T-009-ch1-trajectory-architectural-plateau",
    "ch1-lambert-dc-solver": "C-005-differential-correction-shooting",
    "ch2-large-time-ordering-wall": "E-710-ch2-large-time-aware-decomp",
    "ch2-large-bank": "E-034-ch2-large-epoch-aware-reorder",
    "ch2-large-first-bank-topology": "E-034-ch2-large-epoch-aware-reorder",
    "ch2-medium-bank": "E-040-ch2-medium-ultrafine-retime",
    "ch2-medium-subtour-pattern": "C-013-cluster-bridge-insertion-pattern",
    "ch2-find-transfer-pattern": "C-012-earliest-feasible-tof",
    "ch2-compute-parallelization-roi": "E-019-ch2-edge-compute-marginal-value-zero",
    "ch2-small-audit-2026-05-30": "A-2026-05-30-ch2-small",
    "ch2-small-floor-14292": "E-618-ch2-small-grasp-multistart-floor",
    "spoc4-leaderboard-api": "O-017-leaderboard-2026-06-13",
    "submission-policy-rank3": "Q-001-rank3-each-regular-instance",
    "objective-optimal-not-points": "S-2026-06-12-points-strategy-and-loop-operating-model",
    "E-707-ch1-trajectory-longtof-probe": "E-708-ch1-trajectory-extended-tof-sweep",
    "O-002-ch2-keplerian-tomato-tsp": "C-032-kttsp-problem",
    "O-006-ch3-luna-tomato-advertising-grounding": "O-001-spoc4-problem-grounding",
    "C-009-differential-evolution": "C-014-cma-es-and-evolution-strategies",
    "C-010-memetic-algorithm": "C-011-metaheuristic-local-search-routing",
    "M-015-cardinality-vs-constraint-satisfaction-framing": "C-009-constraint-programming-cp-sat",
}
MANUAL_MAP = {k: v for k, v in MANUAL_MAP.items() if v in stems}   # drop any target that isn't a real note


def idpref(s):
    m = re.match(r"^([A-Z]-(?:general|\d{4}-\d{2}-\d{2}|\d+))", s)
    return m.group(1) if m else None


def toks(slug):
    return {t for t in slug.split("-") if t and t not in STOP and not t.isdigit()}


by_id = defaultdict(list)
file_toks = {}
for s in stems:
    p = idpref(s)
    if p:
        by_id[p].append(s)
    fp = idpref(s)
    file_toks[s] = toks(s[len(fp) + 1:] if fp and len(s) > len(fp) else s)

link_re = re.compile(r"\[\[([^\]|#]+)")
dangling = defaultdict(set)
for f in files:
    for m in link_re.findall(open(f, encoding="utf-8", errors="ignore").read()):
        tgt = m.strip().split("/")[-1]
        if tgt and tgt not in stems and not tgt.endswith(".base"):
            dangling[tgt].add(f)

mapping = {}        # old -> new (confident)
ambiguous = {}      # old -> candidates
missing = []
for t in sorted(dangling):
    if re.search(r"-?NNN", t) or t in ("C-NNN", "E-NNN"):
        missing.append((t, "template-placeholder"))
        continue
    if t in MANUAL_MAP:                                    # curated override
        mapping[t] = MANUAL_MAP[t]
        continue
    if t.endswith("\\") and t.rstrip("\\") in stems:      # repair escaped [[...\]] link
        mapping[t] = t.rstrip("\\")
        continue
    p = idpref(t)
    slug = t[len(p) + 1:] if p and len(t) > len(p) else ""
    if not slug:                                            # bare ID
        cand = by_id.get(p, [])
        if len(cand) == 1:
            mapping[t] = cand[0]
        elif cand:
            ambiguous[t] = cand
        else:
            missing.append((t, "no-file-for-id"))
        continue
    # slug present. CONFIDENT only via: exact slug-suffix (handles ID-reassignment safely) OR same-ID
    # reslug. Fuzzy CROSS-ID token overlap is NOT trusted (it mismaps e.g. ch3->ch2) -> ambiguous.
    want = toks(slug)
    exact = [s for s in stems if s.endswith("-" + slug)]
    if len(exact) == 1:
        mapping[t] = exact[0]
        continue
    same = sorted(((len(want & file_toks[s]), s) for s in by_id.get(p, [])), reverse=True)
    if same and same[0][0] >= 2 and sum(1 for n, _ in same if n == same[0][0]) == 1:
        mapping[t] = same[0][1]                            # same-ID reslug, unique strong overlap
        continue
    cross = sorted(((len(want & file_toks[s]), s) for s in stems if want & file_toks[s]), reverse=True)
    if cross:
        ambiguous[t] = [s for _, s in cross[:4]]
    else:
        missing.append((t, "no-topic-match"))

print(f"=== dangling-link resolution ({'APPLY' if APPLY else 'DRY-RUN'}) ===")
print(f"confident rewrites: {len(mapping)} | ambiguous: {len(ambiguous)} | missing: {len(missing)}\n")
print("-- CONFIDENT (will rewrite):")
for o, n in sorted(mapping.items()):
    print(f"   [[{o}]] -> [[{n}]]")
print("\n-- AMBIGUOUS (left as-is, needs human):")
for o, c in sorted(ambiguous.items()):
    print(f"   [[{o}]] ?? {c}")
print("\n-- MISSING (note never created / placeholder; left as-is):")
for o, why in missing:
    print(f"   [[{o}]] ({why})")

DELINK = "--delink" in sys.argv


def delink_unresolved(txt):
    """Strip [[ ]] from any link whose target is NOT an existing note (keep alias/basename text). Protects
    inline + fenced code spans so methodology-note link EXAMPLES are untouched."""
    spans = []

    def mask(m):
        spans.append(m.group(0)); return f"\x00{len(spans)-1}\x00"
    txt = re.sub(r"```.*?```", mask, txt, flags=re.S)
    txt = re.sub(r"`[^`\n]*`", mask, txt)

    def repl(m):
        inner = m.group(1); tgt = inner.split("|")[0].split("#")[0].split("/")[-1]
        if tgt.endswith(".md"):
            tgt = tgt[:-3]
        if tgt in stems or tgt.endswith(".base") or re.search(r"-?NNN", tgt):
            return m.group(0)                                 # valid link / placeholder -> keep
        if not re.match(r"^[\w][\w.\-]*$", tgt):
            return m.group(0)                                 # code/artifact -> leave
        return inner.split("|", 1)[1] if "|" in inner else tgt  # de-link: keep alias else target text
    txt = re.sub(r"\[\[([^\]]+)\]\]", repl, txt)
    for i, s in enumerate(spans):
        txt = txt.replace(f"\x00{i}\x00", s)
    return txt


if APPLY:
    # path-aware: matches [[old]], [[folder/old]], [[old|alias]], [[old#anchor]] (and escaped backslash)
    pats = [(re.compile(r"\[\[(?:[^\[\]|#\n]*?/)?" + re.escape(o) + r"(?=[\]|#])"), "[[" + n) for o, n in mapping.items()]
    changed = 0
    for f in files:
        txt = open(f, encoding="utf-8", errors="ignore").read()
        orig = txt
        for pat, repl in pats:
            txt = pat.sub(repl, txt)
        if DELINK:
            txt = delink_unresolved(txt)
        if txt != orig:
            open(f, "w", encoding="utf-8").write(txt)
            changed += 1
    print(f"\n[APPLIED] rewrote {len(mapping)} mappings in {changed} file(s){' + de-linked unresolved' if DELINK else ''}.")
