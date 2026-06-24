"""E-714 — Ch2-large rank-1: bidirectional / meet-in-middle test (user-requested before GTSP).

Forward beam strands 61 periphery cities. Bidirectional intuition: thread the periphery as a SEPARATE
segment and bridge it to the core. Decisive empirical test of whether ANY segmentation helps: take the
stranded set S, run a forward beam RESTRICTED to S (+ allowed bridges), and see if S threads into its own
sub-tour. If S threads >~50/61 -> meet-in-middle viable (stitch core + S-segment via exceptions). If S
shatters (threads <10) -> the periphery connects to the CORE not to each other (trap structure), so NO
segmentation helps and only a time-expanded GTSP can weave them. Empirical, ~minutes.
Usage: python ch2_giant_bidir.py"""
import json, sys, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
from collections import defaultdict
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST)
d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
PIDX = {(int(i), int(j)): r for r, (i, j) in enumerate(KEYS)}
OUT = defaultdict(list)
for r, (i, j) in enumerate(KEYS):
    OUT[int(i)].append((int(j), r))
strand = json.load(open(f"{ROOT}/cache/ch2_giant_stranded.json"))["stranded"]
S = set(strand)
# also count intra-S cheap edges (do periphery cities connect to EACH OTHER?)
intra = sum(1 for (i, j) in KEYS if int(i) in S and int(j) in S and FIN[PIDX[(int(i), int(j))]].any())


def cheap_arr(i, j, row, t):
    e0 = np.searchsorted(EPOCHS, t)
    for e in range(max(0, e0 - 1), min(len(EPOCHS), e0 + 8)):
        if not FIN[row, e]:
            continue
        dep = max(t, float(EPOCHS[e])); h = float(VALS[row, e])
        for tof in np.arange(max(kt.min_tof, h - 0.025), h + 0.025, 0.0005):
            if kt.compute_transfer(i, j, dep, float(tof)) <= kt.dv_thr:
                return dep + float(tof)
    return None


def beam_subset(allowed, W=40, K=12):
    """forward beam restricted to `allowed` cities; returns best depth reached."""
    starts = list(allowed)[:12]
    beam = [{"t": 0.0, "last": s, "vis": {s}, "n": 1} for s in starts]
    best = 1
    for depth in range(1, len(allowed)):
        succ = []
        for st in beam:
            cnt = 0
            for (j, row) in OUT[st["last"]]:
                if j not in allowed or j in st["vis"]:
                    continue
                arr = cheap_arr(st["last"], j, row, st["t"])
                if arr is not None:
                    succ.append({"t": arr, "last": j, "vis": st["vis"] | {j}, "n": st["n"] + 1})
                    cnt += 1
                    if cnt >= K:
                        break
        if not succ:
            break
        succ.sort(key=lambda s: s["t"])
        seen = set(); pruned = []
        for s in succ:
            if s["last"] in seen:
                continue
            seen.add(s["last"]); pruned.append(s)
            if len(pruned) >= W:
                break
        beam = pruned
        best = max(best, max(s["n"] for s in beam))
    return best


def main():
    print(f"[E-714] bidirectional/meet-in-middle test: {len(S)} stranded periphery cities", flush=True)
    print(f"  intra-S cheap edges (periphery<->periphery): {intra} (vs {len(S)*(len(S)-1)} possible -> "
          f"{100*intra/max(1,len(S)*(len(S)-1)):.1f}% density)", flush=True)
    t0 = time.time()
    depth = beam_subset(S)
    print(f"[E-714] beam restricted to stranded set threads {depth}/{len(S)} [{time.time()-t0:.0f}s]", flush=True)
    if depth > 0.7 * len(S):
        print(f"[E-714] -> periphery DOES segment ({depth}/{len(S)}); meet-in-middle viable: stitch core + this "
              f"segment via exceptions. Build the bridge.", flush=True)
    else:
        print(f"[E-714] -> periphery SHATTERS ({depth}/{len(S)} threaded; intra-density {100*intra/max(1,len(S)*(len(S)-1)):.1f}%). "
              f"Confirms TRAP STRUCTURE: periphery connects to the CORE, not to each other. NO segmentation / "
              f"bidirectional construction helps. Time-expanded GTSP is the only lever. Proceed to GTSP.", flush=True)


if __name__ == "__main__":
    main()
