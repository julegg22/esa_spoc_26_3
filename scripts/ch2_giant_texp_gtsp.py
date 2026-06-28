"""E-745 — Ch2-LARGE time-expanded GTSP (the real global TD solver; E-744 stage 2). Each comp0 city -> K
time-window copies placed at its ACTUAL cheap-departure regions (from dense1d, not E-718's uniform coarse
buckets). Arc (i@wa -> j@wb) built by the FAST FAITHFUL evaluator (batch_earliest): a cheap transfer i->j
departing in window wa arrives in window wb; cost = tof. GLKH solves the asymmetric GTSP (one node per
city-cluster) = joint order + per-city epoch. Decode -> chrono-walk faithfully -> kt.fitness.
Stages: build(graph) -> glkh(solve) -> decode. Checkpointed.
Usage: CH2_K=8 python ch2_giant_texp_gtsp.py [stage=build|solve|decode|all]"""
import os, sys, json, time, subprocess
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
import ch2_fast_transfer as ft
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
GLKH = f"{ROOT}/reference/GLKH-1.1/GLKH"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST)
OPAR = kt.opar.astype(np.float64); THR = kt.dv_thr; MINTOF = kt.min_tof; DAY = 86400.0
K = int(os.environ.get("CH2_K", "8")); MR = int(os.environ.get("CH2_MR", "5"))
TOFHI = float(os.environ.get("CH2_TOFHI", "3.0")); HMAX = 900.0
GRAPHF = f"{ROOT}/cache/ch2_texp_graph.npz"
ft.cheap_first_tof(OPAR[0], OPAR[1], np.array([0.0, DAY]), MINTOF * DAY, TOFHI * DAY, 0.04 * DAY, THR, MR)


def windows_for_cities():
    """K cheap-departure windows per comp0 city, from dense1d (epochs where the city has a cheap OUT-edge)."""
    d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz"); Kk = d["keys"]; V = d["vals"]
    cities = sorted(set(int(c) for ij in Kk for c in ij))
    nep = V.shape[1]; epochs = np.linspace(0, HMAX, nep)
    cheap_ep = {c: np.zeros(nep, bool) for c in cities}
    for r, (i, j) in enumerate(Kk):
        m = np.isfinite(V[r])
        if m.any():
            cheap_ep[int(i)] |= m
    wins = {}
    for c in cities:
        ep = epochs[cheap_ep[c]]
        if len(ep) == 0:
            wins[c] = np.array([0.0]); continue
        # K windows = K quantile centers of this city's cheap-departure epochs
        qs = np.linspace(0, 1, K + 2)[1:-1]
        wins[c] = np.unique(np.quantile(ep, qs))
    return cities, wins


def build():
    t0 = time.time()
    cities, wins = windows_for_cities()
    idx = {c: k for k, c in enumerate(cities)}
    # adjacency
    dz = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz"); Kk = dz["keys"]; F = np.isfinite(dz["vals"])
    NB = {}
    for r, (i, j) in enumerate(Kk):
        if F[r].any():
            NB.setdefault(int(i), []).append(int(j))
    NBA = {c: np.array(sorted(set(v)), dtype=np.int64) for c, v in NB.items()}
    # nodes: (city, win_index). flat id.
    nodes = []; node_city = []; node_t = []
    cluster = {c: [] for c in cities}
    for c in cities:
        for wi, t in enumerate(wins[c]):
            nid = len(nodes); nodes.append((c, float(t))); node_city.append(c); node_t.append(float(t))
            cluster[c].append(nid)
    NN = len(nodes)
    print(f"[E-745] {len(cities)} cities, K~{K} -> {NN} nodes (avg {NN/len(cities):.1f}/city)", flush=True)
    # arcs: for each node (i,ta), batch_earliest over i's neighbours from epoch ta -> arrival -> dest window node
    rows = []; cols = []; vals = []
    for nid in range(NN):
        i = node_city[nid]; ta = node_t[nid]
        js = NBA.get(i)
        if js is None:
            continue
        arrs, _ = ft.batch_earliest(OPAR, i, ta * DAY, js, 4.0 * DAY, 0.05 * DAY, MINTOF * DAY,
                                    TOFHI * DAY, 0.04 * DAY, THR, MR)
        for q in range(len(js)):
            if arrs[q] <= 0:
                continue
            j = int(js[q]); arr_d = arrs[q] / DAY
            # destination node = j's window whose center is the smallest >= arr_d (depart j at/after arrival)
            wj = wins[j]; cand = wj[wj >= arr_d - 1e-6]
            tb = cand.min() if len(cand) else None
            if tb is None:
                continue
            dest = cluster[j][int(np.where(wj == tb)[0][0])]
            cost = int((arr_d - ta) * 1000) + 1                # tof in ms (+1 to keep >0)
            rows.append(nid); cols.append(dest); vals.append(cost)
        if nid % 500 == 0:
            print(f"[E-745] arcs: node {nid}/{NN} ({len(rows)} arcs) [{time.time()-t0:.0f}s]", flush=True)
    np.savez(GRAPHF, cities=np.array(cities), node_city=np.array(node_city), node_t=np.array(node_t),
             clusters=np.array([cluster[c] for c in cities], dtype=object),
             rows=np.array(rows), cols=np.array(cols), vals=np.array(vals), NN=NN)
    print(f"[E-745] BUILT graph: {NN} nodes, {len(rows)} arcs -> {GRAPHF} [{time.time()-t0:.0f}s]", flush=True)


GLKHDIR = f"{ROOT}/reference/GLKH-1.1"
TAG = "ch2texp"
INST = f"{GLKHDIR}/GTSPLIB/{TAG}.gtsp"; PAR = f"{GLKHDIR}/{TAG}.par"; TOURF = f"{GLKHDIR}/{TAG}.tour"
BIG = 10_000_000                                                  # E-718: > worst real tour, << GLKH cluster-bind M


def solve():
    """AGTSP via GLKH (E-718 pattern): one set per city + dummy depot (open path); faithful arcs from build()."""
    g = np.load(GRAPHF, allow_pickle=True)
    cities = g["cities"].tolist(); node_city = g["node_city"]; clusters = g["clusters"]
    rows = g["rows"]; cols = g["cols"]; vals = g["vals"].astype(np.int64); NN = int(g["NN"])
    cidx = {c: k for k, c in enumerate(cities)}; NC = len(cities)
    M = NN + 1                                                    # +1 dummy depot (0-based index NN -> 1-based M)
    print(f"[E-745] AGTSP: {M} nodes ({NN} live + depot), {NC+1} sets, {len(rows)} arcs", flush=True)
    mat = np.full((M, M), BIG, dtype=np.int32)
    mat[rows, cols] = np.minimum(vals, BIG - 1).astype(np.int32)  # keep cheapest if dup (np.minimum.at would; rare)
    mat[NN, :] = 0; mat[:, NN] = 0; np.fill_diagonal(mat, BIG)
    t0 = time.time()
    with open(INST, "w") as f:
        f.write(f"NAME : {TAG}\nTYPE : AGTSP\nCOMMENT : Ch2-large time-expanded faithful (E-745)\n")
        f.write(f"DIMENSION : {M}\nGTSP_SETS : {NC+1}\n")
        f.write("EDGE_WEIGHT_TYPE : EXPLICIT\nEDGE_WEIGHT_FORMAT : FULL_MATRIX\nEDGE_WEIGHT_SECTION\n")
        mat.tofile(f, sep=" ", format="%d")
        f.write("\nGTSP_SET_SECTION\n")
        for k, c in enumerate(cities):
            members = [int(x) + 1 for x in clusters[k]]           # window-node ids (1-based)
            f.write(f"{k+1} " + " ".join(map(str, members)) + " -1\n")
        f.write(f"{NC+1} {NN+1} -1\nEOF\n")
    print(f"[E-745] wrote {INST} [{time.time()-t0:.0f}s]", flush=True)
    tl = int(os.environ.get("CH2_TL", "1800"))
    with open(PAR, "w") as f:
        f.write(f"PROBLEM_FILE = {INST}\nASCENT_CANDIDATES = 500\nINITIAL_PERIOD = 1000\nMAX_CANDIDATES = 30\n"
                f"MAX_TRIALS = 5000\nPOPULATION_SIZE = 1\nPRECISION = 1\nRUNS = 1\nSEED = 1\nTRACE_LEVEL = 1\n"
                f"OUTPUT_TOUR_FILE = {TOURF}\nTIME_LIMIT = {tl}\n")
    print(f"[E-745] running GLKH (TIME_LIMIT={tl}s)...", flush=True)
    r = subprocess.run([GLKH, f"{TAG}.par"], cwd=GLKHDIR, capture_output=True, text=True, timeout=tl + 600)
    print(r.stdout[-1500:], flush=True)
    if r.returncode != 0:
        print(f"[E-745] GLKH rc={r.returncode}; stderr {r.stderr[-500:]}", flush=True)


def chrono_walk(order, t0=0.0, W=4.0, mr=MR, tofhi=TOFHI):
    t = t0
    for k in range(len(order) - 1):
        deps = np.arange(t, t + W, 0.04)
        tof = ft.cheap_first_tof(OPAR[order[k]], OPAR[order[k + 1]], deps * DAY, MINTOF * DAY, tofhi * DAY,
                                 0.04 * DAY, THR, mr)
        m = tof > 0
        if not m.any():
            return t, k
        arr = deps[m] + tof[m] / DAY; t = float(arr[np.argmin(arr)])
    return t, len(order) - 1


def decode():
    g = np.load(GRAPHF, allow_pickle=True); cities = g["cities"].tolist(); node_city = g["node_city"]; NN = int(g["NN"])
    ids = []
    with open(TOURF) as f:
        intour = False
        for ln in f:
            ln = ln.strip()
            if ln == "TOUR_SECTION":
                intour = True; continue
            if not intour:
                continue
            if ln == "-1" or ln == "EOF":
                break
            ids.append(int(ln) - 1)
    if NN in ids:                                                # rotate so depot first -> open path
        p = ids.index(NN); ids = ids[p + 1:] + ids[:p]
    order = []; seen = set()
    for v in ids:
        if v == NN:
            continue
        c = int(node_city[v])
        if c not in seen:
            seen.add(c); order.append(c)
    print(f"[E-745] decoded {len(order)}/{len(cities)} cities; faithful chrono-walk...", flush=True)
    mk, nl = chrono_walk(order)
    print(f"[E-745] GLKH order: {len(order)} cities, chrono-walk {'COMPLETE' if nl==len(order)-1 else 'STRAND@'+str(nl)} "
          f"makespan {mk:.1f}d ({mk/max(nl,1):.3f} d/leg) [bank comp0 818d, beam 338, LKH-static strand@0]", flush=True)
    json.dump({"order": order, "makespan": mk, "n_legs": nl}, open(f"{ROOT}/cache/ch2_texp_glkh_tour.json", "w"))
    if nl == len(order) - 1:
        print(f"[E-745] *** chrono-walk COMPLETE {len(order)} cities @ {mk:.1f}d -> assemble + kt.fitness + guard-bank.", flush=True)


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "build"
    if stage in ("build", "all"):
        build()
    if stage in ("solve", "all"):
        solve()
    if stage in ("decode", "all"):
        decode()
    print("[E-745] stage done", flush=True)
