"""E-746b — Ch2-small GTSP exception-PENALTY sweep. K=50 GTSP threaded a COMPLETE 49-city tour at 75.2d but
feas=False: it used 25 exception legs (budget 5) because they're fast. The graph + arcs are fixed; only the
penalty on exception arcs needs raising so GLKH uses <=5 bridges. Reuse the built graph (cheap arcs have
val<1e6, exception arcs were stored as val+1e6), re-derive base cost + exc flag, and re-solve GLKH at escalating
PEN. Report exc-count / feasible / makespan per PEN; guard-bank if a feasible tour beats 112.996.
Usage: python ch2_small_texp_pensweep.py"""
import sys, json, time, subprocess, shutil
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
import ch2_small_texp_gtsp as g                                   # kt, OPAR, chrono_walk, GLKHDIR, GLKH, NC, BIG, THR
ROOT = "/home/julian/Projects/esa_spoc_26_3"
kt = g.kt; BIG = g.BIG; NC = g.NC
TAG = "ch2smallsweep"; GINST = f"{g.GLKHDIR}/GTSPLIB/{TAG}.gtsp"; PAR = f"{g.GLKHDIR}/{TAG}.par"; TOURF = f"{g.GLKHDIR}/{TAG}.tour"


def solve_decode(base, exc, rows, cols, clusters, node_city, NN, PEN, tl=300):
    vals = (base + PEN * exc).astype(np.int64)
    M = NN + 1
    mat = np.full((M, M), BIG, dtype=np.int32)
    # keep min cost per (row,col)
    order_idx = np.argsort(-vals)                                 # so min overwrites last
    mat[rows[order_idx], cols[order_idx]] = np.minimum(vals[order_idx], BIG - 1).astype(np.int32)
    mat[NN, :] = 0; mat[:, NN] = 0; np.fill_diagonal(mat, BIG)
    with open(GINST, "w") as f:
        f.write(f"NAME : {TAG}\nTYPE : AGTSP\nDIMENSION : {M}\nGTSP_SETS : {NC+1}\n"
                "EDGE_WEIGHT_TYPE : EXPLICIT\nEDGE_WEIGHT_FORMAT : FULL_MATRIX\nEDGE_WEIGHT_SECTION\n")
        mat.tofile(f, sep=" ", format="%d")
        f.write("\nGTSP_SET_SECTION\n")
        for c in range(NC):
            f.write(f"{c+1} " + " ".join(str(int(x) + 1) for x in clusters[c]) + " -1\n")
        f.write(f"{NC+1} {NN+1} -1\nEOF\n")
    with open(PAR, "w") as f:
        f.write(f"PROBLEM_FILE = {GINST}\nASCENT_CANDIDATES = 500\nMAX_CANDIDATES = 30\nMAX_TRIALS = 3000\n"
                f"POPULATION_SIZE = 5\nRUNS = 3\nPRECISION = 1\nSEED = 1\nTRACE_LEVEL = 0\n"
                f"OUTPUT_TOUR_FILE = {TOURF}\nTIME_LIMIT = {tl}\n")
    subprocess.run([g.GLKH, f"{TAG}.par"], cwd=g.GLKHDIR, capture_output=True, timeout=tl + 200)
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
    seen = set(); o = []
    for v in ids:
        if v == NN:
            continue
        c = int(node_city[v])
        if c not in seen:
            seen.add(c); o.append(c)
    if len(o) != NC:
        return None
    mk, nl, tofs = g.chrono_walk(o)
    if nl != len(o) - 1:
        return ("STRAND", nl, None, None, None)
    deps = [d for d, _ in tofs]; tfs = [tf for _, tf in tofs]
    dv = deps + tfs + [float(c) for c in o]
    fit = kt.fitness(dv); feas = max(float(x) for x in fit[1:]) <= 1e-6
    nexc = sum(1 for k in range(len(o) - 1) if kt.compute_transfer(o[k], o[k + 1], deps[k], tfs[k]) > kt.dv_thr + 1e-6)
    return ("OK", float(fit[0]), feas, nexc, dv)


def main():
    gr = np.load(g.GRAPHF, allow_pickle=True)
    rows = gr["rows"]; cols = gr["cols"]; vals = gr["vals"].astype(np.int64)
    clusters = gr["clusters"]; node_city = gr["node_city"]; NN = int(gr["NN"])
    exc = (vals >= 1_000_000).astype(np.int64)
    base = vals - 1_000_000 * exc
    print(f"[E-746b] graph: {len(rows)} arcs, {exc.sum()} exception arcs; sweeping PEN", flush=True)
    best = None; t0 = time.time()
    for PEN in [2_000_000, 3_500_000, 5_000_000, 7_000_000, 9_000_000, 9_800_000]:
        r = solve_decode(base, exc, rows, cols, clusters, node_city, NN, PEN)
        if r is None:
            print(f"[E-746b] PEN={PEN/1e6:.1f}M: incomplete decode [{time.time()-t0:.0f}s]", flush=True); continue
        if r[0] == "STRAND":
            print(f"[E-746b] PEN={PEN/1e6:.1f}M: STRAND@{r[1]} [{time.time()-t0:.0f}s]", flush=True); continue
        _, mk, feas, nexc, dv = r
        ok = feas and nexc <= 5
        print(f"[E-746b] PEN={PEN/1e6:.1f}M: makespan {mk:.2f}d exc={nexc} feas={feas} {'<<FEASIBLE' if ok else ''} "
              f"[{time.time()-t0:.0f}s]", flush=True)
        if ok and (best is None or mk < best[0]):
            best = (mk, dv, PEN)
    if best and best[0] < 112.996:
        mk, dv, PEN = best
        shutil.copy(f"{ROOT}/solutions/upload/small.json", f"{ROOT}/solutions/upload/small.json.bak_texp")
        json.dump([{"decisionVector": [float(x) for x in dv], "problem": "easy",
                    "challenge": "spoc-4-keplerian-tomato-traveling-salesperson"}],
                  open(f"{ROOT}/solutions/upload/small.json", "w"))
        rt = kt.fitness(json.load(open(f"{ROOT}/solutions/upload/small.json"))[0]["decisionVector"])
        print(f"[E-746b] *** GUARD-BANKED small -> {float(rt[0]):.2f}d (PEN={PEN/1e6:.1f}M, was 112.996, RANK GAIN) "
              f"-> ESCALATE submission. NOT submitted.", flush=True)
    elif best:
        print(f"[E-746b] best feasible {best[0]:.2f}d (>=112.996, no rank gain)", flush=True)
    else:
        print(f"[E-746b] no feasible <=5-exc tour found in sweep -> need finer windows or hard exc-constraint", flush=True)


if __name__ == "__main__":
    main()
