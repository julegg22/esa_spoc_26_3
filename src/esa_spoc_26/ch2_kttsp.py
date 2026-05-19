"""Ch2 Keplerian Tomato TSP — official-mirror scorer + greedy baseline.

Mirrors the official KTTSP UDP (reference/spoc4_udp/kttsp-*.py, L-002):
time-dependent orbital ATSP, minimise makespan = times[-1]+tofs[-1];
each leg Δv≤600, ≤5 legs in (100,600], rest ≤100; chronological;
Δv via multi-rev Lambert about the Moon. H-003. Greedy nearest-
feasible constructor → early valid baseline (META.md §2).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pykep as pk

MU_MOON = 4.904869500000000e12
CHALLENGE = "spoc-4-keplerian-tomato-traveling-salesperson"


class KTTSP:
    def __init__(self, path, max_revs=20):
        self.max_revs = max_revs
        hdr, rows = None, []
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                s = raw.strip()
                if not s or s.startswith("c"):
                    continue
                if s.startswith("p "):
                    hdr = s.split()
                    continue
                rows.append([float(v) for v in s.split()])
        self.t0 = pk.epoch(float(hdr[2]))
        self.min_tof = float(hdr[3])
        self.max_time = float(hdr[4])
        self.dv_thr = float(hdr[5])
        self.dv_exc = float(hdr[6])
        self.n_exc = int(hdr[7])
        self.opar = np.asarray(rows, float)
        self.n = self.opar.shape[0]
        self.tom = [
            pk.planet.keplerian(self.t0, list(r), MU_MOON, 0.0, 0.0, 0.0)
            for r in self.opar
        ]

    def compute_transfer(self, i, j, t_start, tof):
        ri, vi = self.tom[i].eph(t_start)
        rj, vj = self.tom[j].eph(t_start + tof)
        best = float("inf")
        for cw in (False, True):
            try:
                lp = pk.lambert_problem(ri, rj, tof * pk.DAY2SEC,
                                        MU_MOON, cw, self.max_revs)
            except Exception:
                continue
            for v1, v2 in zip(lp.get_v1(), lp.get_v2(), strict=False):
                dv = (np.linalg.norm(np.array(v1) - np.array(vi))
                      + np.linalg.norm(np.array(v2) - np.array(vj)))
                best = min(best, dv)
        return best

    def fitness(self, x):
        n = self.n
        times = x[:n - 1]
        tofs = x[n - 1:2 * n - 2]
        order = [round(v) for v in x[2 * n - 2:]]
        perm_c = len(set(order)) - n
        dv_cnt = exc_cnt = time_cnt = 0
        for i in range(n - 1):
            dv = self.compute_transfer(order[i], order[i + 1],
                                       times[i], tofs[i])
            if dv <= self.dv_exc + 1e-6:
                dv_cnt += 1
            if self.dv_thr < dv <= self.dv_exc + 1e-6:
                exc_cnt += 1
            if i < n - 2 and times[i] + tofs[i] <= times[i + 1] + 1e-6:
                time_cnt += 1
        return [times[-1] + tofs[-1], perm_c, dv_cnt - (n - 1),
                time_cnt - (n - 2), exc_cnt - self.n_exc]

    def is_feasible(self, f):
        return (f[1] == 0 and f[2] == 0 and f[3] == 0 and f[4] <= 0)


def greedy(kt: KTTSP, start=0, tof_grid=None):
    """No-wait greedy: from current tomato pick the next minimising leg
    Δv (≤ dv_thr if possible, else accept an exception, ≤5) over a TOF
    grid; depart on arrival (chronological by construction)."""
    if tof_grid is None:
        tof_grid = np.concatenate([np.arange(0.2, 5, 0.4),
                                   np.arange(5, 30, 2.0)])
    n = kt.n
    unvis = set(range(n))
    unvis.discard(start)
    order = [start]
    times, tofs = [], []
    t, exc_used = 0.0, 0
    cur = start
    while unvis:
        best = None  # (dv, tof, j, is_exc)
        for j in unvis:
            for tf in tof_grid:
                dv = kt.compute_transfer(cur, j, t, float(tf))
                if dv > kt.dv_exc + 1e-6:
                    continue
                is_exc = dv > kt.dv_thr
                if is_exc and exc_used >= kt.n_exc:
                    continue
                key = (dv, float(tf), j, is_exc)
                if best is None or dv < best[0]:
                    best = key
        if best is None:  # no feasible next under any tof → fail
            return None
        dv, tf, j, is_exc = best
        times.append(t)
        tofs.append(tf)
        t += tf
        exc_used += int(is_exc)
        order.append(j)
        unvis.discard(j)
        cur = j
    return times + tofs + [float(o) for o in order]


def greedy_wait(kt: KTTSP, start, wait=4.0, d_dep=0.3,
                tof_grid=None, prefer_normal=True):
    """Earliest-feasible-arrival greedy WITH waiting. From each tomato,
    scan departure times t_dep∈[t_ready, t_ready+wait] and a TOF grid;
    pick the (j, t_dep, tof) feasible (Δv≤dv_thr, else an exception ≤5)
    minimising arrival time t_dep+tof (≈ makespan). Chronology holds by
    construction (t_dep ≥ t_ready = previous arrival)."""
    if tof_grid is None:
        tof_grid = np.concatenate([np.arange(0.2, 4, 0.4),
                                   np.arange(4, 20, 1.5)])
    n = kt.n
    unvis = set(range(n)) - {start}
    order, times, tofs = [start], [], []
    cur, t_ready, exc = start, 0.0, 0
    while unvis:
        best = None  # (arr, t_dep, tof, j, is_exc, dv)
        for j in unvis:
            for t_dep in np.arange(t_ready, t_ready + wait + 1e-9, d_dep):
                for tf in tof_grid:
                    if t_dep + tf > kt.max_time:
                        continue
                    dv = kt.compute_transfer(cur, j, float(t_dep), float(tf))
                    if dv > kt.dv_exc + 1e-6:
                        continue
                    is_exc = dv > kt.dv_thr
                    if is_exc and exc >= kt.n_exc:
                        continue
                    arr = t_dep + tf
                    rank = (arr, dv) if not prefer_normal else (
                        is_exc, arr, dv)
                    if best is None or rank < best[0]:
                        best = (rank, float(t_dep), float(tf), j, is_exc)
        if best is None:
            return None
        _, t_dep, tf, j, is_exc = best
        times.append(t_dep)
        tofs.append(tf)
        t_ready = t_dep + tf
        exc += int(is_exc)
        order.append(j)
        unvis.discard(j)
        cur = j
    return times + tofs + [float(o) for o in order]


def _windows_worker(args):
    """Per-pair cheap-window extractor: scan Δv vs t_dep at fixed tof
    (the pair's precomputed-optimal TF[i,j]); return up to K windows
    (representative t_dep values) where Δv ≤ thr_max. Each window =
    a contiguous t_dep region where Δv ≤ thr_max; we keep ONE
    representative per window (the local minimum)."""
    inst, i, j, tof_fix, max_time, thr_max, max_k, step = args
    kt = _WORKER_KT[0] if _WORKER_KT else KTTSP(inst)
    n_pts = int((max_time - tof_fix - 0.5) / step) + 1
    if n_pts < 2:
        return i, j, []
    tds = np.linspace(0.0, max_time - tof_fix - 0.5, n_pts)
    dvs = np.array([kt.compute_transfer(i, j, float(td), float(tof_fix))
                    for td in tds])
    # find contiguous regions where dv ≤ thr_max; per region pick the arg-min
    mask = (dvs <= thr_max) & np.isfinite(dvs)
    if not mask.any():
        return i, j, []
    wins = []
    k = 0
    while k < n_pts:
        if not mask[k]:
            k += 1
            continue
        start = k
        while k < n_pts and mask[k]:
            k += 1
        end = k
        seg_dv = dvs[start:end]
        idx = start + int(np.argmin(seg_dv))
        wins.append((float(dvs[idx]), float(tds[idx]), float(tof_fix)))
    # Temporal-coverage diversification: split td range into max_k bins,
    # take the best (lowest Δv) representative from each bin. Ensures
    # windows span the full [0, max_time-tof] range so a chronologically
    # chainable Hamiltonian path has flexibility per arc.
    edges = np.linspace(0.0, max_time - tof_fix, max_k + 1)
    kept = []
    for b in range(max_k):
        cands = [w for w in wins if edges[b] <= w[1] < edges[b + 1]]
        if cands:
            kept.append(min(cands))   # min by Δv (first tuple element)
    return i, j, kept


def precompute_windows(inst,
                       npz_in="/home/julian/Projects/esa_spoc_26_3/edges_small.npz",
                       npz_out="/home/julian/Projects/esa_spoc_26_3/windows_small.npz",
                       max_k=8, thr_max=600.0, step=0.5, n_workers=4):
    """Parallel cheap-window precompute: per ordered pair (i,j), list
    up to max_k windows (Δv, t_dep, tof=TF[i,j]) with Δv ≤ thr_max,
    derived from a fine t_dep scan over [0, max_time-tof]. Output is a
    compact npz: per-pair array of windows (padded with inf)."""
    import multiprocessing as mp

    kt = KTTSP(inst)
    n = kt.n
    TF = np.load(npz_in)["tf"]
    args = [(inst, i, j, float(TF[i, j]) if TF[i, j] > 0 else 1.0,
             kt.max_time, thr_max, max_k, step)
            for i in range(n) for j in range(n) if i != j]
    W = np.full((n, n, max_k, 3), np.inf)
    counts = np.zeros((n, n), dtype=int)
    with mp.Pool(n_workers, initializer=_init_worker,
                 initargs=(inst,)) as pool:
        for i, j, wins in pool.imap_unordered(_windows_worker, args,
                                              chunksize=16):
            for k, w in enumerate(wins):
                W[i, j, k] = w
            counts[i, j] = len(wins)
    np.savez(npz_out, W=W, counts=counts)
    cheap_total = int((W[..., 0] <= 100).sum())
    exc_total = int(((W[..., 0] > 100) & (W[..., 0] <= 600)).sum())
    return {"n": n, "max_k": max_k, "windows_le100": cheap_total,
            "windows_100_600": exc_total,
            "avg_windows_per_pair": float(counts.mean()),
            "max_windows_pair": int(counts.max()),
            "pairs_with_any_le100": int(((W[..., 0] <= 100).any(axis=-1)).sum()),
            "saved": npz_out}


def _windows2d_worker(args):
    """Joint (td, tof) scan: per pair (i,j), build a 2D grid of Δv
    over (td, tof), find local minima ≤ thr_max, return up to max_k
    representatives diversified across BOTH td and tof. The single-tof
    precompute was infeasible at the chronological level because the
    static-optimal tof was ~33d on cheap pairs → 48 legs >> 200d cap.
    Short-tof low-Δv windows exist when orbital phasing aligns; the
    joint scan finds them."""
    inst, i, j, max_time, thr_max, max_k, tofs, td_step = args
    kt = _WORKER_KT[0] if _WORKER_KT else KTTSP(inst)
    cand = []  # (Δv, td, tof) tuples ≤ thr_max
    for tof in tofs:
        if tof + 0.5 >= max_time:
            continue
        n_pts = max(2, int((max_time - tof - 0.5) / td_step) + 1)
        tds = np.linspace(0.0, max_time - tof - 0.5, n_pts)
        dvs = np.array([kt.compute_transfer(i, j, float(td), float(tof))
                        for td in tds])
        mask = (dvs <= thr_max) & np.isfinite(dvs)
        if not mask.any():
            continue
        k = 0
        while k < n_pts:
            if not mask[k]:
                k += 1
                continue
            start = k
            while k < n_pts and mask[k]:
                k += 1
            seg = dvs[start:k]
            idx = start + int(np.argmin(seg))
            cand.append((float(dvs[idx]), float(tds[idx]), float(tof)))
    if not cand:
        return i, j, []
    # Diversify across (td, tof) 2D plane: split td range × tof range
    # into a sqrt(max_k) × sqrt(max_k) grid, pick min-Δv per cell.
    nx = ny = int(np.ceil(np.sqrt(max_k)))
    td_edges = np.linspace(0.0, max_time, nx + 1)
    tof_edges = np.linspace(min(tofs), max(tofs) + 1e-6, ny + 1)
    bins = {}  # (tx, ty) -> best (Δv, td, tof)
    for (dv, td, tof) in cand:
        tx = min(nx - 1, int(np.searchsorted(td_edges, td, "right") - 1))
        ty = min(ny - 1, int(np.searchsorted(tof_edges, tof, "right") - 1))
        key = (tx, ty)
        if key not in bins or dv < bins[key][0]:
            bins[key] = (dv, td, tof)
    kept = sorted(bins.values())[:max_k]
    return i, j, kept


def precompute_windows_2d(
    inst,
    npz_out="/home/julian/Projects/esa_spoc_26_3/windows2d_small.npz",
    max_k=12, thr_max=600.0, td_step=1.0,
    tofs=(0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 24.0, 36.0),
    n_workers=4,
):
    """Joint (td, tof)-grid window precompute. Per pair (i,j), scans
    Δv(td, tof) over the cartesian product of td_grid × tof_grid, finds
    local minima ≤ thr_max, returns up to max_k diversified
    representatives covering both axes. Critical when rank-3 makespan
    is tight (~112d / 49 nodes ⇒ avg leg 2.3d) but single-tof
    precompute had median tof 33d."""
    import multiprocessing as mp

    kt = KTTSP(inst)
    n = kt.n
    tofs = tuple(t for t in tofs if t < kt.max_time)
    args = [(inst, i, j, kt.max_time, thr_max, max_k, tofs, td_step)
            for i in range(n) for j in range(n) if i != j]
    W = np.full((n, n, max_k, 3), np.inf)
    counts = np.zeros((n, n), dtype=int)
    with mp.Pool(n_workers, initializer=_init_worker,
                 initargs=(inst,)) as pool:
        for i, j, wins in pool.imap_unordered(_windows2d_worker, args,
                                              chunksize=8):
            for k, w in enumerate(wins):
                W[i, j, k] = w
            counts[i, j] = len(wins)
    np.savez(npz_out, W=W, counts=counts)
    return {"n": n, "max_k": max_k, "tofs": list(tofs),
            "windows_le100": int((W[..., 0] <= 100).sum()),
            "windows_100_600": int(((W[..., 0] > 100)
                                    & (W[..., 0] <= 600)).sum()),
            "avg_windows_per_pair": float(counts.mean()),
            "pairs_with_any_le100": int(((W[..., 0] <= 100)
                                         .any(axis=-1)).sum()),
            "median_tof_le100": float(np.median(
                W[..., 2][W[..., 0] <= 100])) if (W[..., 0] <= 100).any()
                                              else float("nan"),
            "saved": npz_out}


def structure_accurate_sampled(inst, sample=60, n_workers=4, seed=0):
    """Q6: hi-accuracy `_edge_worker` over a node-sample; stats only.
    For medium/large to test whether the small instance's cluster/
    feasibility structure generalises at the same edge-search resolution."""
    import multiprocessing as mp

    kt = KTTSP(inst)
    n = kt.n
    nodes = (list(range(n)) if sample >= n
             else sorted(np.random.default_rng(seed).choice(
                 n, sample, replace=False).tolist()))
    pairs = [(inst, i, j, kt.max_time, kt.min_tof)
             for i in nodes for j in nodes if i != j]
    M = {}
    with mp.Pool(n_workers, initializer=_init_worker,
                 initargs=(inst,)) as pool:
        for i, j, dv, _td, _tf in pool.imap_unordered(
                _edge_worker, pairs, chunksize=16):
            M[(i, j)] = dv
    vals = np.array(list(M.values()))
    fin = vals[np.isfinite(vals)]
    # cluster the sampled subgraph at ≤100
    idx = {g: k for k, g in enumerate(nodes)}
    A = np.zeros((len(nodes), len(nodes)), int)
    for (i, j), d in M.items():
        if d <= 100.0:
            A[idx[i], idx[j]] = 1
            A[idx[j], idx[i]] = 1
    import scipy.sparse as sp
    from scipy.sparse.csgraph import connected_components
    nc, lab = connected_components(sp.csr_matrix(A), directed=False)
    sizes = sorted(np.bincount(lab).tolist(), reverse=True)
    outdeg = np.array([sum(M.get((nodes[k], nodes[m]), np.inf) <= 100
                           for m in range(len(nodes)))
                       for k in range(len(nodes))])
    return {
        "instance": Path(inst).name, "n": n, "sampled_nodes": len(nodes),
        "pairs": len(M),
        "frac_le100": round(float((vals <= 100).mean()), 4),
        "frac_le600": round(float((vals <= 600).mean()), 4),
        "median_min_dv": round(float(np.median(fin)), 1),
        "p10_min_dv": round(float(np.percentile(fin, 10)), 1),
        "min_min_dv": round(float(fin.min()), 1),
        "le100_components_in_sample": nc,
        "le100_component_sizes_top": sizes[:8],
        "dead_end_le100_frac": round(float((outdeg == 0).sum())
                                     / len(nodes), 3),
        "median_outdeg_le100": float(np.median(outdeg)),
    }


def _row_min_dv(args):
    """Coarse min-Δv from node i to a set of targets (no local refine);
    fast structural probe. Returns (i, {j: min_dv})."""
    inst, i, targets, n_t, n_tof, max_time = args
    kt = _WORKER_KT[0] if _WORKER_KT else KTTSP(inst)
    tg = np.linspace(0.0, min(40.0, max_time * 0.2), n_t)
    fg = np.linspace(0.3, 26.0, n_tof)
    out = {}
    for j in targets:
        if j == i:
            continue
        b = np.inf
        for td in tg:
            for tf in fg:
                b = min(b, kt.compute_transfer(i, j, float(td), float(tf)))
        out[j] = b
    return i, out


def structure_quick(inst, sample=None, n_t=8, n_tof=10, n_workers=4):
    """Fast coarse structural probe (optionally node-sampled for large
    instances) to compare cheap-edge-graph structure across instances."""
    import multiprocessing as mp

    kt = KTTSP(inst)
    n = kt.n
    nodes = (list(range(n)) if sample is None or sample >= n
             else sorted(np.random.default_rng(0).choice(
                 n, sample, replace=False).tolist()))
    args = [(inst, i, nodes, n_t, n_tof, kt.max_time) for i in nodes]
    rows = {}
    with mp.Pool(n_workers, initializer=_init_worker,
                 initargs=(inst,)) as pool:
        for i, d in pool.imap_unordered(_row_min_dv, args, chunksize=4):
            rows[i] = d
    vals = np.array([v for d in rows.values() for v in d.values()])
    fin = vals[np.isfinite(vals)]
    outdeg = np.array([sum(1 for v in rows[i].values() if v <= 100.0)
                       for i in nodes])
    pairs = sum(len(d) for d in rows.values())
    return {
        "instance": Path(inst).name, "n": n, "sampled_nodes": len(nodes),
        "pairs_probed": pairs,
        "frac_le100": round(float((vals <= 100).sum()) / max(pairs, 1), 4),
        "frac_le600": round(float((vals <= 600).sum()) / max(pairs, 1), 4),
        "median_min_dv": round(float(np.median(fin)), 1),
        "p10_min_dv": round(float(np.percentile(fin, 10)), 1),
        "dead_end_le100_frac": round(float((outdeg == 0).sum())
                                     / len(nodes), 3),
        "median_outdeg_le100": float(np.median(outdeg)),
    }


def _edge_worker(args):
    """min Δv for ordered pair (i,j): global t_dep scan over [0,max_time]
    + tof grid + built-in multi-rev → top-K seeds → Nelder-Mead polish.
    Returns (i, j, best_dv, t_dep, tof)."""
    inst, i, j, max_time, min_tof = args
    kt = _WORKER_KT[0] if _WORKER_KT else KTTSP(inst)
    from scipy.optimize import minimize

    # HIGH-ACCURACY (E-017): fine t_dep over the FULL horizon + long
    # multi-rev TOF + many local-opt seeds. Cheap windows are narrow &
    # recur on the synodic-beat period; multi-rev needs long TOF.
    t_grid = np.arange(0.0, max_time - 0.5, 1.0)
    tof_grid = np.concatenate([np.arange(0.2, 6, 0.25),
                               np.arange(6, 80, 2.5)])
    cands = []
    for td in t_grid:
        for tf in tof_grid:
            if td + tf > max_time:
                continue
            dv = kt.compute_transfer(i, j, float(td), float(tf))
            cands.append((dv, float(td), float(tf)))
    cands.sort(key=lambda c: c[0])
    best = cands[0]
    seen = []
    for _dv0, td0, tf0 in cands:             # refine up to 15 distinct basins
        if any(abs(td0 - s) < 3.0 for s in seen):
            continue
        seen.append(td0)
        if len(seen) > 15:
            break
        try:
            r = minimize(
                lambda p: kt.compute_transfer(
                    i, j, max(p[0], 0.0),
                    min(max(p[1], min_tof), max_time - max(p[0], 0.0))),
                np.array([td0, tf0]), method="Nelder-Mead",
                options={"xatol": 1e-4, "fatol": 1e-3, "maxiter": 150},
            )
            if r.fun < best[0]:
                td = float(max(r.x[0], 0.0))
                best = (float(r.fun), td,
                        float(min(max(r.x[1], min_tof), max_time - td)))
        except Exception:
            pass
    return (i, j, best[0], best[1], best[2])


_WORKER_KT = []


def _init_worker(inst):
    _WORKER_KT.append(KTTSP(inst))


def precompute_edges(inst, n_workers=4,
                     out="/home/julian/Projects/esa_spoc_26_3/edges_small.npz"):
    """Parallel time-optimal per-edge Δv matrix + realizing (t_dep,tof)."""
    import multiprocessing as mp

    kt = KTTSP(inst)
    n, mt, mtof = kt.n, kt.max_time, kt.min_tof
    args = [(inst, i, j, mt, mtof)
            for i in range(n) for j in range(n) if i != j]
    DV = np.full((n, n), np.inf)
    TD = np.zeros((n, n))
    TF = np.zeros((n, n))
    with mp.Pool(n_workers, initializer=_init_worker,
                 initargs=(inst,)) as pool:
        for i, j, dv, td, tf in pool.imap_unordered(_edge_worker, args,
                                                    chunksize=16):
            DV[i, j], TD[i, j], TF[i, j] = dv, td, tf
    np.savez(out, dv=DV, td=TD, tf=TF)
    le100 = int((DV <= 100).sum())
    return {"n": n, "edges_le100": le100,
            "edges_100_600": int(((DV > 100) & (DV <= 600)).sum()),
            "dead_end_le100": int(((DV <= 100).sum(axis=1) == 0).sum()),
            "median_outdeg_le100": float(np.median((DV <= 100).sum(axis=1))),
            "saved": out}


def analyze_structure(kt: KTTSP, n_t=10, n_tof=14):
    """M-002 ultrathink probe: pairwise min-Δv over a (t_dep,tof,rev)
    search → reveal the cheap-edge graph structure (is Ch2 a clustered
    constrained-Hamiltonian-path problem?)."""
    n = kt.n
    t_grid = np.linspace(0.0, min(20.0, kt.max_time * 0.1), n_t)
    tof_grid = np.concatenate([np.arange(0.2, 4, 0.3),
                               np.arange(4, 25, 2.0)])[:n_tof]
    from scipy.optimize import minimize

    def edge_min(i, j):
        # coarse grid → seed → Nelder-Mead local polish (cheap Δv
        # windows are narrow; multi-rev handled inside compute_transfer)
        best, seed = np.inf, (0.0, 1.0)
        for td in t_grid:
            for tf in tof_grid:
                dv = kt.compute_transfer(i, j, float(td), float(tf))
                if dv < best:
                    best, seed = dv, (float(td), float(tf))
        try:
            r = minimize(
                lambda p: kt.compute_transfer(
                    i, j, max(p[0], 0.0),
                    min(max(p[1], kt.min_tof), kt.max_time)),
                np.array(seed), method="Nelder-Mead",
                options={"xatol": 1e-3, "fatol": 1e-2, "maxiter": 60},
            )
            best = min(best, float(r.fun))
        except Exception:
            pass
        return best

    M = np.full((n, n), np.inf)
    for i in range(n):
        for j in range(n):
            if i != j:
                M[i, j] = edge_min(i, j)
    finite = M[np.isfinite(M)]
    le100 = int((M <= 100).sum())
    le600 = int(((M > 100) & (M <= 600)).sum())
    outdeg100 = (M <= 100).sum(axis=1)
    return {
        "n": n,
        "pairs": n * (n - 1),
        "min_dv_m_s": {"min": float(finite.min()),
                       "median": float(np.median(finite)),
                       "p10": float(np.percentile(finite, 10)),
                       "max_finite": float(finite.max())},
        "edges_le100": le100,
        "edges_100_600": le600,
        "nodes_with_no_le100_out": int((outdeg100 == 0).sum()),
        "min_outdeg_le100": int(outdeg100.min()),
        "median_outdeg_le100": float(np.median(outdeg100)),
    }


def _leg_retime(kt, i, j, t_ready, window=10.0):
    """Min Δv for (i,j) with t_dep ≥ t_ready over a few orbital periods
    (cheap windows recur) + tof + multi-rev + local polish.
    Returns (dv, t_dep, tof)."""
    from scipy.optimize import minimize

    tg = np.arange(t_ready, min(t_ready + window, kt.max_time - 0.5), 0.25)
    fg = np.concatenate([np.arange(0.2, 4, 0.3), np.arange(4, 28, 2.0)])
    best = (np.inf, t_ready, 1.0)
    for td in tg:
        for tf in fg:
            if td + tf > kt.max_time:
                continue
            dv = kt.compute_transfer(i, j, float(td), float(tf))
            if dv < best[0]:
                best = (dv, float(td), float(tf))
    def _obj(p):
        d = kt.compute_transfer(
            i, j, max(p[0], t_ready),
            min(max(p[1], kt.min_tof), kt.max_time - max(p[0], t_ready)))
        return d if np.isfinite(d) else 1e12  # guard nan/inf (E-013 warn)

    try:
        r = minimize(_obj, np.array([best[1], best[2]]),
                     method="Nelder-Mead",
                     options={"xatol": 1e-3, "fatol": 1e-2, "maxiter": 60})
        if r.fun < best[0]:
            td = max(r.x[0], t_ready)
            best = (float(r.fun), float(td),
                    float(min(max(r.x[1], kt.min_tof),
                              kt.max_time - td)))
    except Exception:
        pass
    return best


def route(kt, DV, start, rng):
    """Cheap-graph-guided nearest-feasible-arrival router with per-leg
    windowed re-timing and a ≤n_exc exception budget. The DV matrix
    restricts/orders candidates so we don't strand (E-012 failure)."""
    n = kt.n
    unvis = set(range(n)) - {start}
    order, times, tofs = [start], [], []
    cur, t_ready, exc = start, 0.0, 0
    while unvis:
        # principled shortlist (no random truncation — that strands
        # the tour falsely): all cheap-graph successors + the next best
        # by precomputed static Δv (a good proxy for retimed cost).
        uv = sorted(unvis, key=lambda j: DV[cur, j])
        cheap = [j for j in uv if DV[cur, j] <= 100.0]
        shortlist = cheap + [j for j in uv if j not in cheap][:8]
        best = None  # (is_exc, arrival, dv, j, t_dep, tof)
        for j in shortlist:
            dv, td, tf = _leg_retime(kt, cur, j, t_ready)
            if dv > kt.dv_exc + 1e-6:
                continue
            is_exc = dv > kt.dv_thr
            if is_exc and exc >= kt.n_exc:
                continue
            key = (is_exc, td + tf, dv)
            if best is None or key < best[:3]:
                best = (is_exc, td + tf, dv, j, td, tf)
        if best is None:
            return None
        is_exc, arr, dv, j, td, tf = best
        times.append(td)
        tofs.append(tf)
        t_ready = arr
        exc += int(is_exc)
        order.append(j)
        unvis.discard(j)
        cur = j
    return times + tofs + [float(o) for o in order]


def solve_small(inst, problem="small", n_starts=8,
                out="/home/julian/Projects/esa_spoc_26_3/solutions/upload"):
    """Multi-start greedy_wait; keep the best FEASIBLE tour by makespan;
    bank the artifact. Establishes the early valid Ch2 baseline."""
    from pathlib import Path

    kt = KTTSP(inst)
    starts = np.linspace(0, kt.n - 1, min(n_starts, kt.n), dtype=int)
    best_x, best_f = None, None
    for s in dict.fromkeys(int(v) for v in starts):
        x = greedy_wait(kt, s)
        if x is None:
            continue
        f = kt.fitness(x)
        if kt.is_feasible(f) and (best_f is None or f[0] < best_f[0]):
            best_x, best_f = x, f
    if best_x is None:
        return {"problem": problem, "feasible": False,
                "note": "no feasible tour across starts (greedy_wait)"}
    p = Path(out) / f"{problem}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([{"decisionVector": best_x, "problem": problem,
                              "challenge": CHALLENGE}]))
    return {"problem": problem, "n": kt.n, "makespan_d": best_f[0],
            "feasible": True, "rank3_small_d": 111.76,
            "artifact": str(p)}


def route_small(inst, problem="small", n_starts=6,
                npz="/home/julian/Projects/esa_spoc_26_3/edges_small.npz",
                out="/home/julian/Projects/esa_spoc_26_3/solutions/upload"):
    """Structure-aware router: multi-start cheap-graph routing with
    per-leg re-timing; keep best FEASIBLE by makespan; bank artifact."""
    from pathlib import Path

    kt = KTTSP(inst)
    DV = np.load(npz)["dv"]
    rng = np.random.default_rng(0)
    best_x = best_f = None
    starts = list(dict.fromkeys(
        int(v) for v in np.linspace(0, kt.n - 1,
                                    min(n_starts, kt.n), dtype=int)))
    for s in starts:
        x = route(kt, DV, s, rng)
        if x is None:
            continue
        f = kt.fitness(x)
        if kt.is_feasible(f) and (best_f is None or f[0] < best_f[0]):
            best_x, best_f = x, f
    if best_x is None:
        return {"problem": problem, "feasible": False,
                "note": "router found no feasible tour"}
    p = Path(out) / f"{problem}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([{"decisionVector": best_x,
                              "problem": problem, "challenge": CHALLENGE}]))
    return {"problem": problem, "n": kt.n, "makespan_d": best_f[0],
            "feasible": True, "rank3_small_d": 111.76, "artifact": str(p)}


if __name__ == "__main__":
    inst = (
        "reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/easy.kttsp")
    if len(sys.argv) > 1 and sys.argv[1] == "probe":
        print(json.dumps(analyze_structure(KTTSP(inst)), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "route":
        print(json.dumps(route_small(inst), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "edges":
        print(json.dumps(precompute_edges(inst), indent=2))
    elif len(sys.argv) > 2 and sys.argv[1] == "struct":
        smp = int(sys.argv[3]) if len(sys.argv) > 3 else None
        print(json.dumps(structure_quick(sys.argv[2], sample=smp),
                         indent=2))
    elif len(sys.argv) > 2 and sys.argv[1] == "structacc":
        smp = int(sys.argv[3]) if len(sys.argv) > 3 else 60
        print(json.dumps(structure_accurate_sampled(sys.argv[2],
                                                    sample=smp), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "windows":
        print(json.dumps(precompute_windows(inst), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "windows2d":
        print(json.dumps(precompute_windows_2d(inst), indent=2))
    else:
        print(json.dumps(solve_small(inst), indent=2))
