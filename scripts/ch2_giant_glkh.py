"""E-718 — Ch2-large rank-1 via GLKH (Helsgaun's Generalized-TSP solver; user-authorized download).

The E-713 verdict named GLKH as the one missing tool: the time-expanded GTSP is the only formulation that
yields chronologically-feasible global orderings, but Noon-Bean+elkai blew up and the custom Lagrangian rests
on a DAG-by-level premise the data falsifies (96.6% of texp edges are intra-bucket, not strictly forward).
GLKH solves AGTSP (asymmetric generalized TSP) directly — no Noon-Bean big-M, no DAG assumption.

Build an AGTSP instance from the time-expanded graph:
  - one set per city (601) + a dummy DEPOT set (1 node) with 0-cost edges to/from every node -> the GTSP
    cycle becomes an OPEN chronological path.
  - matrix cost = the cached bucket min-tof (milli-days) for real forward arcs; BIG for non-arcs so GLKH only
    uses feasible edges. Cross-bucket arcs enforce coarse (39-level, 12-day) chronology; within-bucket slack
    is fixed by faithful fine-tof retiming of the decoded order.
GLKH gives the ORDER; we retime faithfully and report realized makespan + strands. Target <424d (rank-1).

Usage:
  python ch2_giant_glkh.py build  [tag=ch2giant] [npz=ch2_giant_texp.npz] [time_limit=1800]
  python ch2_giant_glkh.py decode [tag=ch2giant] [npz=ch2_giant_texp.npz]
"""
import sys, json, time
import numpy as np
ROOT = "/home/julian/Projects/esa_spoc_26_3"
GLKH = f"{ROOT}/reference/GLKH-1.1"
# BIG must exceed the worst feasible tour (~4.8e6 = 601 edges x 8000 milli-d) so one non-edge dominates any
# all-real tour, yet sit FAR below GLKH's cluster-binding M = INT_MAX/4/Precision (~5.37e8). Else the solver
# splits clusters to dodge a BIG edge -> "Illegal g-tour: cluster entered more than once" (no tour written).
BIG = 10_000_000

TAG = sys.argv[2] if len(sys.argv) > 2 else "ch2giant"
NPZ = sys.argv[3] if len(sys.argv) > 3 else "ch2_giant_texp.npz"
INST = f"{GLKH}/GTSPLIB/{TAG}.gtsp"
PAR = f"{GLKH}/{TAG}.par"
TOURF = f"{GLKH}/{TAG}.tour"

g = np.load(f"{ROOT}/cache/{NPZ}")
NODES = g["nodes"]; SRC0 = g["src"]; DST0 = g["dst"]; COST0 = g["cost"]; nb = int(g["nb"]); giant = g["giant"].tolist()
nidx = {int(n): k for k, n in enumerate(NODES)}
N = len(NODES); NC = len(giant)
node_city = (NODES // nb).astype(np.int64)


def build():
    su = np.array([nidx[int(s)] for s in SRC0]); dv = np.array([nidx[int(d)] for d in DST0])
    keep = node_city[su] != node_city[dv]
    su, dv, ec = su[keep], dv[keep], COST0[keep].astype(np.int64)
    M = N + 1                                              # +1 dummy depot at index N (0-based) -> 1-based N+1
    print(f"[E-718] building AGTSP: {M} nodes ({N} live + depot), {NC+1} sets, {len(su)} arcs", flush=True)
    mat = np.full((M, M), BIG, dtype=np.int32)             # int32: BIG=1e9 < 2^31, halves RAM + matches LKH
    mat[su, dv] = ec.astype(np.int32)                      # real forward arcs
    mat[N, :] = 0; mat[:, N] = 0                           # depot: 0-cost in/out (open path)
    np.fill_diagonal(mat, BIG)                             # forbid self
    t0 = time.time()
    with open(INST, "w") as f:
        f.write(f"NAME : {TAG}\nTYPE : AGTSP\nCOMMENT : Ch2-large time-expanded (E-718)\n")
        f.write(f"DIMENSION : {M}\nGTSP_SETS : {NC+1}\n")
        f.write("EDGE_WEIGHT_TYPE : EXPLICIT\nEDGE_WEIGHT_FORMAT : FULL_MATRIX\nEDGE_WEIGHT_SECTION\n")
        mat.tofile(f, sep=" ", format="%d")               # C-speed text dump of the full matrix
        f.write("\nGTSP_SET_SECTION\n")
        for c in range(NC):                               # one set per city: its epoch-node indices (1-based)
            members = np.where(node_city == c)[0] + 1
            f.write(f"{c+1} " + " ".join(map(str, members.tolist())) + " -1\n")
        f.write(f"{NC+1} {N+1} -1\n")                      # depot set = the single depot node
        f.write("EOF\n")
    print(f"[E-718] wrote {INST} [{time.time()-t0:.0f}s]", flush=True)
    with open(PAR, "w") as f:
        f.write(f"PROBLEM_FILE = {INST}\n")
        f.write("ASCENT_CANDIDATES = 500\nINITIAL_PERIOD = 1000\nMAX_CANDIDATES = 30\n")
        f.write("MAX_TRIALS = 5000\nPOPULATION_SIZE = 1\nPRECISION = 1\nRUNS = 1\nSEED = 1\nTRACE_LEVEL = 1\n")
        tl = int(sys.argv[4]) if len(sys.argv) > 4 else 1800
        f.write(f"OUTPUT_TOUR_FILE = {TOURF}\nTIME_LIMIT = {tl}\n")
    print(f"[E-718] wrote {PAR}; run: cd {GLKH} && ./GLKH ch2giant.par", flush=True)


def fine_tof(i, j, t):
    d2 = fine_tof.d2
    EPOCHS, KEYS, VALS, FIN, PIDX, kt = d2
    row = PIDX.get((i, j))
    if row is None:
        return None
    e0 = np.searchsorted(EPOCHS, t)
    for e in range(max(0, e0 - 1), min(len(EPOCHS), e0 + 8)):
        if not FIN[row, e]:
            continue
        dep = max(t, float(EPOCHS[e])); h = float(VALS[row, e])
        for tof in np.arange(max(kt.min_tof, h - 0.025), h + 0.025, 0.0005):
            if kt.compute_transfer(i, j, dep, float(tof)) <= kt.dv_thr:
                return dep + float(tof)
    return None


def _load_fine():
    sys.path.insert(0, f"{ROOT}/src")
    from esa_spoc_26.ch2_kttsp import KTTSP
    kt = KTTSP(f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling Salesperson Problem/problems/hard.kttsp")
    d2 = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
    EPOCHS = d2["epochs"]; KEYS = d2["keys"]; VALS = d2["vals"]; FIN = np.isfinite(VALS)
    PIDX = {(int(i), int(j)): r for r, (i, j) in enumerate(KEYS)}
    fine_tof.d2 = (EPOCHS, KEYS, VALS, FIN, PIDX, kt)


def retime(order):
    t = 0.0; strand = 0
    for k in range(len(order) - 1):
        r = fine_tof(giant[order[k]], giant[order[k + 1]], t)
        if r is None:
            strand += 1; t += 9.0
        else:
            t = r
    return t, strand


def decode():
    # read GLKH tour (1-based node ids; -1 terminates)
    ids = []
    with open(TOURF) as f:
        intour = False
        for ln in f:
            ln = ln.strip()
            if ln == "TOUR_SECTION":
                intour = True; continue
            if not intour:
                continue
            v = int(ln)
            if v == -1 or ln == "EOF":
                break
            ids.append(v - 1)                              # back to 0-based
    # rotate so depot (index N) is first, drop it, map nodes->cities, dedup preserving order
    if N in ids:
        p = ids.index(N); ids = ids[p + 1:] + ids[:p]
    order = []; seen = set()
    for v in ids:
        if v == N:
            continue
        c = int(node_city[v])
        if c not in seen:
            seen.add(c); order.append(c)
    print(f"[E-718] decoded {len(order)}/{NC} cities; faithful retiming ...", flush=True)
    _load_fine()
    t0 = time.time()
    mk, strand = retime(order)
    print(f"[E-718] GLKH tour: {len(order)}/{NC} cities, realized makespan {mk:.1f}d, strands {strand} "
          f"(rank-1=424.62) [{time.time()-t0:.0f}s]", flush=True)
    json.dump({"order": order, "makespan": mk, "strands": strand},
              open(f"{ROOT}/cache/{TAG}_glkh_tour.json", "w"))
    if strand == 0 and mk < 424:
        print(f"[E-718] *** RANK-1 ({mk:.0f}d) -> stitch satellites + udp verify + guard-bank + ESCALATE.", flush=True)
    elif strand == 0:
        print(f"[E-718] complete feasible tour @ {mk:.0f}d (>=424) -> refine epochs/buckets.", flush=True)
    else:
        print(f"[E-718] {strand} strands -> within-bucket order infeasible; repair or finer buckets.", flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    {"build": build, "decode": decode}[cmd]()
