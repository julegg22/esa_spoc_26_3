"""E-746 — Ch2-SMALL time-expanded GTSP (C-035 applied where it is MOST tractable). The small audit
(ch2-small-floor-14292) diagnosed the 112.996 floor as a SEARCH-ARCHITECTURE gap: every method we tried is
construction+local-moves on a fixed graph with deterministic epochs; the named missing lever is "joint
sequence+epoch global search (LKH time-expanded, epochs free)". That lever IS the time-expanded GTSP — and at
n=49 the resolution-vs-tractability wall that cripples it on large (n=1051) vanishes: 49 cities x K fine windows
is ~1500 nodes, trivial for GLKH, with FINE time resolution affordable.
Build: each city -> K uniform-fine time-window copies; full adjacency; faithful arcs via batch_earliest (cheap
dv<=thr); GLKH AGTSP (one node/city + dummy depot = open path) -> order+epochs; faithful chrono-walk -> makespan.
Target < 112.996 (bank, rank 6); rank-1 ~101.65.
Usage: CH2_K=30 CH2_H=130 python ch2_small_texp_gtsp.py [build|solve|decode|all]"""
import os, sys, json, time, subprocess
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
import ch2_fast_transfer as ft
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
GLKHDIR = f"{ROOT}/reference/GLKH-1.1"; GLKH = f"{GLKHDIR}/GLKH"
INST_KT = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
           "Tomato Traveling Salesperson Problem/problems/easy.kttsp")
kt = KTTSP(INST_KT)
OPAR = kt.opar.astype(np.float64); THR = kt.dv_thr; MINTOF = kt.min_tof; DAY = 86400.0
NC = OPAR.shape[0]                                                # 49 cities
K = int(os.environ.get("CH2_K", "30")); H = float(os.environ.get("CH2_H", "130"))
MR = int(os.environ.get("CH2_MR", "20")); TOFHI = float(os.environ.get("CH2_TOFHI", "8.0"))
GRAPHF = f"{ROOT}/cache/ch2_small_texp_graph.npz"
TAG = "ch2smalltexp"; GINST = f"{GLKHDIR}/GTSPLIB/{TAG}.gtsp"; PAR = f"{GLKHDIR}/{TAG}.par"; TOURF = f"{GLKHDIR}/{TAG}.tour"
BIG = 10_000_000
ft.cheap_first_tof(OPAR[0], OPAR[1], np.array([0.0, DAY]), MINTOF * DAY, TOFHI * DAY, 0.02 * DAY, THR, MR)


def build():
    t0 = time.time()
    wins = np.linspace(0.0, H, K)                                 # uniform-fine windows (affordable at n=49)
    allj = np.arange(NC, dtype=np.int64)
    node_city = []; node_t = []; cluster = [[] for _ in range(NC)]
    for c in range(NC):
        for t in wins:
            nid = len(node_city); node_city.append(c); node_t.append(float(t)); cluster[c].append(nid)
    NN = len(node_city); node_city = np.array(node_city); node_t = np.array(node_t)
    print(f"[E-746] {NC} cities, K={K} -> {NN} nodes; building faithful arcs (full adjacency)", flush=True)
    rows = []; cols = []; vals = []
    for nid in range(NN):
        i = int(node_city[nid]); ta = node_t[nid]
        js = allj[allj != i]
        arrs, _ = ft.batch_earliest(OPAR, i, ta * DAY, js, 4.0 * DAY, 0.05 * DAY, MINTOF * DAY,
                                    TOFHI * DAY, 0.02 * DAY, THR, MR)
        for q in range(len(js)):
            if arrs[q] <= 0:
                continue
            j = int(js[q]); arr_d = arrs[q] / DAY
            cand = wins[wins >= arr_d - 1e-6]
            if not len(cand):
                continue
            tb = cand.min(); dest = cluster[j][int(np.where(wins == tb)[0][0])]
            rows.append(nid); cols.append(dest); vals.append(int((arr_d - ta) * 1000) + 1)
        if nid % 300 == 0:
            print(f"[E-746] arcs node {nid}/{NN} ({len(rows)} arcs) [{time.time()-t0:.0f}s]", flush=True)
    np.savez(GRAPHF, node_city=node_city, node_t=node_t,
             clusters=np.array([cluster[c] for c in range(NC)], dtype=object),
             rows=np.array(rows), cols=np.array(cols), vals=np.array(vals), NN=NN)
    print(f"[E-746] BUILT {NN} nodes, {len(rows)} arcs -> {GRAPHF} [{time.time()-t0:.0f}s]", flush=True)


def solve():
    g = np.load(GRAPHF, allow_pickle=True)
    clusters = g["clusters"]; rows = g["rows"]; cols = g["cols"]; vals = g["vals"].astype(np.int64); NN = int(g["NN"])
    M = NN + 1
    print(f"[E-746] AGTSP {M} nodes ({NN}+depot), {NC+1} sets, {len(rows)} arcs", flush=True)
    mat = np.full((M, M), BIG, dtype=np.int32)
    mat[rows, cols] = np.minimum(vals, BIG - 1).astype(np.int32)
    mat[NN, :] = 0; mat[:, NN] = 0; np.fill_diagonal(mat, BIG)
    with open(GINST, "w") as f:
        f.write(f"NAME : {TAG}\nTYPE : AGTSP\nDIMENSION : {M}\nGTSP_SETS : {NC+1}\n"
                "EDGE_WEIGHT_TYPE : EXPLICIT\nEDGE_WEIGHT_FORMAT : FULL_MATRIX\nEDGE_WEIGHT_SECTION\n")
        mat.tofile(f, sep=" ", format="%d")
        f.write("\nGTSP_SET_SECTION\n")
        for c in range(NC):
            f.write(f"{c+1} " + " ".join(str(int(x) + 1) for x in clusters[c]) + " -1\n")
        f.write(f"{NC+1} {NN+1} -1\nEOF\n")
    tl = int(os.environ.get("CH2_TL", "600"))
    with open(PAR, "w") as f:
        f.write(f"PROBLEM_FILE = {GINST}\nASCENT_CANDIDATES = 500\nMAX_CANDIDATES = 30\nMAX_TRIALS = 5000\n"
                f"POPULATION_SIZE = 5\nPRECISION = 1\nRUNS = 5\nSEED = 1\nTRACE_LEVEL = 1\n"
                f"OUTPUT_TOUR_FILE = {TOURF}\nTIME_LIMIT = {tl}\n")
    print(f"[E-746] running GLKH (TL={tl}s)...", flush=True)
    r = subprocess.run([GLKH, f"{TAG}.par"], cwd=GLKHDIR, capture_output=True, text=True, timeout=tl + 300)
    print(r.stdout[-1200:], flush=True)


def chrono_walk(order, t0=0.0, W=6.0):
    t = t0; tofs = []
    for k in range(len(order) - 1):
        deps = np.arange(t, t + W, 0.02)
        tof = ft.cheap_first_tof(OPAR[order[k]], OPAR[order[k + 1]], deps * DAY, MINTOF * DAY, TOFHI * DAY,
                                 0.02 * DAY, THR, MR)
        m = tof > 0
        if not m.any():
            return t, k, tofs
        ix = np.argmin(deps[m] + tof[m] / DAY); t = float(deps[m][ix] + tof[m][ix] / DAY); tofs.append((float(deps[m][ix]), float(tof[m][ix] / DAY)))
    return t, len(order) - 1, tofs


def decode():
    g = np.load(GRAPHF, allow_pickle=True); node_city = g["node_city"]; NN = int(g["NN"])
    ids = []
    with open(TOURF) as f:
        intour = False
        for ln in f:
            ln = ln.strip()
            if ln == "TOUR_SECTION":
                intour = True; continue
            if not intour:
                continue
            if ln in ("-1", "EOF"):
                break
            ids.append(int(ln) - 1)
    if NN in ids:
        p = ids.index(NN); ids = ids[p + 1:] + ids[:p]
    order = []; seen = set()
    for v in ids:
        if v == NN:
            continue
        c = int(node_city[v])
        if c not in seen:
            seen.add(c); order.append(c)
    print(f"[E-746] decoded {len(order)}/{NC} cities; faithful chrono-walk...", flush=True)
    mk, nl, tofs = chrono_walk(order)
    ok = nl == len(order) - 1 and len(order) == NC
    print(f"[E-746] GLKH order {len(order)} cities, {'COMPLETE' if nl==len(order)-1 else 'STRAND@'+str(nl)} "
          f"makespan {mk:.3f}d [bank 112.996 rank6, rank1~101.65]", flush=True)
    if ok:
        deps = [d for d, _ in tofs]; tfs = [tf for _, tf in tofs]
        dv = deps + tfs + [float(c) for c in order]
        fit = kt.fitness(dv); feas = max(float(x) for x in fit[1:]) <= 1e-6
        print(f"[E-746] kt.fitness {float(fit[0]):.3f}d feas={feas} (bank 112.996, gain {112.996-float(fit[0]):+.3f})", flush=True)
        json.dump({"order": order, "dv": dv, "makespan": float(fit[0]), "feas": feas},
                  open(f"{ROOT}/cache/ch2_small_texp_tour.json", "w"))
        if feas and float(fit[0]) < 112.996:
            print(f"[E-746] *** BEATS BANK ({float(fit[0]):.3f}<112.996) -> guard-bank candidate + ESCALATE submission decision", flush=True)


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    if stage in ("build", "all"):
        build()
    if stage in ("solve", "all"):
        solve()
    if stage in ("decode", "all"):
        decode()
    print("[E-746] done", flush=True)
