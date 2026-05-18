"""Ch1 Luna Tomato Logistics — beginner (weighted 3-D matching) exact MIP.

Maximise sum of selected transfer weights subject to each Earth orbit,
Moon orbit, and destination being used at most once. This is a binary
set-packing / 3-dimensional-assignment ILP; solved exactly with HiGHS.

Instance file: one line per transfer `e l d w` (ints e/l/d, float w).
Decision vector: binary array of length |T| (1 = transfer selected).

Used by H-001 / E-001. Agent never submits (GOALS.md §4) — this only
writes solutions/upload/<problem>.json for manual upload.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import highspy
import numpy as np
import scipy.sparse as sp

CHALLENGE = "spoc-4-luna-tomato-logistics"


def load_instance(path: str | Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    raw = np.loadtxt(path)
    e = raw[:, 0].astype(np.int64)
    ll = raw[:, 1].astype(np.int64)
    d = raw[:, 2].astype(np.int64)
    w = raw[:, 3].astype(np.float64)
    return e, ll, d, w


def greedy(e, ll, d, w) -> np.ndarray:
    """Weight-descending greedy 3-D matching: take a transfer if its e,
    l, d are all still free. Fast, feasible, strong incumbent / warm start."""
    n = w.shape[0]
    order = np.argsort(-w, kind="stable")
    use_e = np.zeros(int(e.max()) + 1, dtype=bool)
    use_l = np.zeros(int(ll.max()) + 1, dtype=bool)
    use_d = np.zeros(int(d.max()) + 1, dtype=bool)
    x = np.zeros(n, dtype=np.int8)
    for i in order:
        ei, li, di = e[i], ll[i], d[i]
        if use_e[ei] or use_l[li] or use_d[di]:
            continue
        x[i] = 1
        use_e[ei] = use_l[li] = use_d[di] = True
    return x


def _owner_maps(e, ll, d, x, ne, nl, nd):
    """sel_*[node] = index of the selected transfer owning that node, else -1."""
    se = np.full(ne, -1, np.int64)
    sl = np.full(nl, -1, np.int64)
    sd = np.full(nd, -1, np.int64)
    sel = np.flatnonzero(x)
    se[e[sel]] = sel
    sl[ll[sel]] = sel
    sd[d[sel]] = sel
    return se, sl, sd


def ejection_improve(e, ll, d, w, x, order, se, sl, sd):
    """Strictly-improving pass: for each excluded transfer i (weight desc),
    if w_i exceeds the total weight of the ≤3 selected transfers it conflicts
    with, swap them in. Then greedy-fill freed nodes. Repeat until no move."""
    moved = True
    while moved:
        moved = False
        for i in order:
            if x[i]:
                continue
            ei, li, di = e[i], ll[i], d[i]
            c = {se[ei], sl[li], sd[di]}
            c.discard(-1)
            if w[i] - sum(w[j] for j in c) > 1e-9:
                for j in c:
                    x[j] = 0
                    se[e[j]] = sl[ll[j]] = sd[d[j]] = -1
                x[i] = 1
                se[ei] = sl[li] = sd[di] = i
                moved = True
        # greedy-fill any nodes freed by ejections
        for i in order:
            if x[i]:
                continue
            ei, li, di = e[i], ll[i], d[i]
            if se[ei] == -1 and sl[li] == -1 and sd[di] == -1:
                x[i] = 1
                se[ei] = sl[li] = sd[di] = i
                moved = True
    return float(w[x == 1].sum())


def lns(e, ll, d, w, x0, iters=100000, frac=0.12, seed=0, time_budget_s=120.0):
    """Perturbation LNS: ruin a random fraction, then ejection-improve to a
    new local optimum; keep best (accept equal for plateau drift)."""
    rng = np.random.default_rng(seed)
    order = np.argsort(-w, kind="stable")
    ne, nl, nd = int(e.max()) + 1, int(ll.max()) + 1, int(d.max()) + 1
    best = x0.copy()
    se, sl, sd = _owner_maps(e, ll, d, best, ne, nl, nd)
    best_mass = ejection_improve(e, ll, d, w, best, order, se, sl, sd)
    cur = best.copy()
    t0 = time.time()
    it = 0
    while it < iters and time.time() - t0 < time_budget_s:
        it += 1
        x = cur.copy()
        sel = np.flatnonzero(x)
        x[rng.choice(sel, size=max(1, int(frac * sel.size)), replace=False)] = 0
        se, sl, sd = _owner_maps(e, ll, d, x, ne, nl, nd)
        m = ejection_improve(e, ll, d, w, x, order, se, sl, sd)
        if m >= best_mass:
            best, best_mass, cur = x.copy(), m, x
        else:
            cur = best.copy()
    return best, best_mass, it


def _solve_sub(e, ll, d, w, time_limit, threads):
    """Exact max-weight 3-D matching on a (small) transfer subset."""
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    h.setOptionValue("time_limit", float(time_limit))
    h.setOptionValue("mip_rel_gap", 0.0)
    if threads:
        h.setOptionValue("threads", int(threads))
    h.passModel(build_model(e, ll, d, w))
    h.run()
    return (np.asarray(h.getSolution().col_value) > 0.5).astype(np.int8)


def _read_pool_best(path):
    try:
        v = np.load(path, allow_pickle=False)
        return float(v[0]), v[1:].astype(np.int8)
    except Exception:
        return -1.0, None


def _write_pool_best(path, mass, x):
    try:
        tmp = f"{path}.{os.getpid()}.tmp"
        np.save(tmp, np.concatenate([[mass], x.astype(np.int8)]))
        os.replace(tmp + ".npy", path)
    except Exception:
        pass


def coop_mip_lns(e, ll, d, w, x0, seed=0, threads=1, time_budget_s=600.0,
                 time_per_sub=8.0, pool_best_path=None, sync_every=20):
    """Cooperative + adaptive MIP-LNS. Workers share a global-best via
    `pool_best_path`; a stuck worker escalates destroy size (diversify)
    and periodically restarts from the shared best. Breaks the per-worker
    plateau that plain mip_lns hit at ~99 % of rank-3 (H-004/E-002)."""
    rng = np.random.default_rng(seed)
    ne, nl, nd = int(e.max()) + 1, int(ll.max()) + 1, int(d.max()) + 1
    best, best_m = x0.copy(), float(w[x0 == 1].sum())
    fracs = [0.10, 0.15, 0.20, 0.30, 0.45, 0.65]  # escalates when stuck
    stuck, fi = 0, seed % 3
    t0, rounds = time.time(), 0
    while time.time() - t0 < time_budget_s:
        rounds += 1
        x = best.copy()
        sel = np.flatnonzero(x)
        x[rng.choice(sel, size=max(1, int(fracs[fi] * sel.size)),
                      replace=False)] = 0
        kept = np.flatnonzero(x)
        ue = np.zeros(ne, bool)
        ul = np.zeros(nl, bool)
        ud = np.zeros(nd, bool)
        ue[e[kept]] = True
        ul[ll[kept]] = True
        ud[d[kept]] = True
        free = (x == 0) & ~ue[e] & ~ul[ll] & ~ud[d]
        idx = np.flatnonzero(free)
        if idx.size:
            x[idx[_solve_sub(e[idx], ll[idx], d[idx], w[idx],
                             time_per_sub, threads) == 1]] = 1
        m = float(w[x == 1].sum())
        if m > best_m + 1e-6:
            best, best_m = x.copy(), m
            stuck, fi = 0, seed % 3
            if pool_best_path:
                _write_pool_best(pool_best_path, best_m, best)
        else:
            stuck += 1
            if stuck % 8 == 0:  # escalate destroy when plateaued
                fi = min(fi + 1, len(fracs) - 1)
        if pool_best_path and rounds % sync_every == 0:
            gm, gx = _read_pool_best(pool_best_path)
            if gx is not None and gm > best_m + 1e-6:
                best, best_m, stuck, fi = gx.copy(), gm, 0, seed % 3
        if rounds % 25 == 0:
            print(f"[coop seed={seed} f={fracs[fi]:.2f}] r={rounds} "
                  f"best={best_m:.1f} t={time.time() - t0:.0f}s", flush=True)
    return best, best_m, rounds


def mip_lns(e, ll, d, w, x0, drop_frac=0.25, time_per_sub=8.0,
            seed=0, threads=1, time_budget_s=300.0):
    """MIP-based LNS: drop a random subset of selected transfers, then
    EXACTLY re-optimise the freed region (sub-ILP) with HiGHS. Each round
    is monotone on the region (the kept-minus-dropped state is feasible),
    so it escapes the greedy local optimum that pure greedy/ejection cannot."""
    rng = np.random.default_rng(seed)
    ne, nl, nd = int(e.max()) + 1, int(ll.max()) + 1, int(d.max()) + 1
    x = x0.copy()
    best, best_m = x.copy(), float(w[x == 1].sum())
    t0 = time.time()
    rounds = 0
    while time.time() - t0 < time_budget_s:
        rounds += 1
        x = best.copy()
        sel = np.flatnonzero(x)
        x[rng.choice(sel, size=max(1, int(drop_frac * sel.size)), replace=False)] = 0
        kept = np.flatnonzero(x)
        ue = np.zeros(ne, bool)
        ul = np.zeros(nl, bool)
        ud = np.zeros(nd, bool)
        ue[e[kept]] = True  # nodes blocked by kept transfers
        ul[ll[kept]] = True
        ud[d[kept]] = True
        free = (x == 0) & ~ue[e] & ~ul[ll] & ~ud[d]
        idx = np.flatnonzero(free)
        if idx.size:
            sub = _solve_sub(e[idx], ll[idx], d[idx], w[idx],
                             time_per_sub, threads)
            x[idx[sub == 1]] = 1
        m = float(w[x == 1].sum())
        if m >= best_m:
            best, best_m = x.copy(), m
        if rounds % 25 == 0:
            print(
                f"[mip_lns seed={seed} drop={drop_frac:.2f}] "
                f"round={rounds} best={best_m:.1f} "
                f"elapsed={time.time() - t0:.0f}s",
                flush=True,
            )
    return best, best_m, rounds


def build_model(e, ll, d, w) -> highspy.HighsModel:
    n = w.shape[0]
    # contiguous row blocks: Earth orbits, then Moon orbits, then destinations
    _, e_row = np.unique(e, return_inverse=True)
    _, l_row = np.unique(ll, return_inverse=True)
    _, d_row = np.unique(d, return_inverse=True)
    n_e, n_l, n_d = e_row.max() + 1, l_row.max() + 1, d_row.max() + 1
    rows = np.concatenate([e_row, l_row + n_e, d_row + n_e + n_l])
    cols = np.tile(np.arange(n), 3)
    data = np.ones(3 * n, dtype=np.float64)
    m = n_e + n_l + n_d
    csr = sp.csr_matrix((data, (rows, cols)), shape=(m, n))

    model = highspy.HighsModel()
    lp = model.lp_
    lp.num_col_ = n
    lp.num_row_ = m
    lp.sense_ = highspy.ObjSense.kMaximize
    lp.col_cost_ = w
    lp.col_lower_ = np.zeros(n)
    lp.col_upper_ = np.ones(n)
    lp.row_lower_ = np.zeros(m)
    lp.row_upper_ = np.ones(m)  # each node used at most once
    lp.integrality_ = [highspy.HighsVarType.kInteger] * n
    lp.a_matrix_.format_ = highspy.MatrixFormat.kRowwise
    lp.a_matrix_.start_ = csr.indptr.astype(np.int32)
    lp.a_matrix_.index_ = csr.indices.astype(np.int32)
    lp.a_matrix_.value_ = csr.data
    return model


def solve(
    path,
    problem,
    out_dir="solutions/upload",
    time_limit=1800.0,
    threads=0,
    warm_start=False,
    log_file=None,
    mip_heuristic_effort=None,
):
    e, ll, d, w = load_instance(path)
    n = w.shape[0]
    model = build_model(e, ll, d, w)

    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    if log_file:  # L-001: keep the watchdog able to see B&B progress
        h.setOptionValue("log_file", str(log_file))
        h.setOptionValue("log_to_console", False)
    h.setOptionValue("time_limit", float(time_limit))
    h.setOptionValue("mip_rel_gap", 0.0)
    if threads:
        h.setOptionValue("threads", int(threads))
    if mip_heuristic_effort is not None:
        h.setOptionValue("mip_heuristic_effort", float(mip_heuristic_effort))
    h.passModel(model)
    if warm_start:  # greedy incumbent → better pruning + improving heuristics
        gx = greedy(e, ll, d, w)
        s = highspy.HighsSolution()
        s.col_value = gx.astype(float).tolist()
        h.setSolution(s)
    t0 = time.time()
    h.run()
    wall = time.time() - t0

    status = str(h.getModelStatus())
    info = h.getInfo()
    sol = h.getSolution()
    xb = (np.asarray(sol.col_value) > 0.5).astype(int)

    # exact objective + feasibility from the rounded integer vector
    obj = float(w[xb == 1].sum())
    feasible = True
    for arr in (e, ll, d):
        sel = arr[xb == 1]
        if sel.size != np.unique(sel).size:
            feasible = False
    gap = getattr(info, "mip_gap", float("nan"))

    out_path = Path(out_dir) / f"{problem}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            [{"decisionVector": xb.tolist(), "problem": problem, "challenge": CHALLENGE}]
        )
    )

    return {
        "problem": problem,
        "n_transfers": int(n),
        "status": status,
        "objective_mass": obj,
        "n_selected": int(xb.sum()),
        "mip_gap": float(gap),
        "feasible": feasible,
        "wall_s": round(wall, 2),
        "artifact": str(out_path),
    }


def _lns_worker(args):
    path, seed, drop_frac, time_per_sub, budget = args
    e, ll, d, w = load_instance(path)
    g = greedy(e, ll, d, w)
    best, bm, rounds = mip_lns(
        e, ll, d, w, g, drop_frac=drop_frac, time_per_sub=time_per_sub,
        seed=seed, threads=1, time_budget_s=budget,
    )
    return float(bm), best.astype(np.int8), int(seed), int(rounds), float(drop_frac)


def parallel_mip_lns(path, problem, out_dir="solutions/upload",
                     n_workers=4, time_budget_s=600.0, time_per_sub=8.0):
    """Probe→campaign (META.md §6): N parallel MIP-LNS workers, varied
    drop_frac/seed; keep the best; write the submission artifact."""
    import multiprocessing as mp

    fracs = [0.15, 0.20, 0.25, 0.30]
    args = [
        (path, s, fracs[s % len(fracs)], time_per_sub, time_budget_s)
        for s in range(n_workers)
    ]
    t0 = time.time()
    with mp.Pool(n_workers) as pool:
        res = pool.map(_lns_worker, args)
    bm, bx, seed, rounds, frac = max(res, key=lambda r: r[0])

    e, ll, d, _ = load_instance(path)
    feasible = all(
        arr[bx == 1].size == np.unique(arr[bx == 1]).size for arr in (e, ll, d)
    )
    out_path = Path(out_dir) / f"{problem}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            [{"decisionVector": bx.tolist(), "problem": problem,
              "challenge": CHALLENGE}]
        )
    )
    return {
        "problem": problem,
        "method": "parallel_mip_lns",
        "n_workers": n_workers,
        "best_mass": bm,
        "best_seed": seed,
        "best_drop_frac": frac,
        "rounds_best": rounds,
        "n_selected": int(bx.sum()),
        "feasible": feasible,
        "wall_s": round(time.time() - t0, 1),
        "per_worker_mass": sorted(round(r[0], 1) for r in res),
        "artifact": str(out_path),
    }


def _load_artifact_x(artifact, n):
    try:
        v = json.loads(Path(artifact).read_text())[0]["decisionVector"]
        x = np.asarray(v, dtype=np.int8)
        return x if x.shape[0] == n else None
    except Exception:
        return None


def _coop_worker(args):
    path, seed, budget, time_per_sub, pool_best_path, warm_artifact = args
    e, ll, d, w = load_instance(path)
    g = greedy(e, ll, d, w)
    if warm_artifact:
        wx = _load_artifact_x(warm_artifact, w.shape[0])
        if wx is not None and float(w[wx == 1].sum()) > float(w[g == 1].sum()):
            g = wx  # warm-start from the existing strong incumbent
    best, bm, _ = coop_mip_lns(
        e, ll, d, w, g, seed=seed, threads=1, time_budget_s=budget,
        time_per_sub=time_per_sub, pool_best_path=pool_best_path,
    )
    return float(bm), best.astype(np.int8), int(seed)


def parallel_coop_mip_lns(path, problem, out_dir="solutions/upload",
                          n_workers=4, time_budget_s=600.0, time_per_sub=8.0,
                          warm_artifact=None):
    """Cooperative campaign: workers share a global-best file + adaptive
    escalating destroy. `warm_artifact` (a prior solutions JSON) seeds the
    strong incumbent for an exact-polish run with large `time_per_sub`."""
    import multiprocessing as mp
    import tempfile

    pool_best = os.path.join(
        tempfile.gettempdir(), f"poolbest_{problem}_{os.getpid()}.npy"
    )
    args = [
        (path, s, time_budget_s, time_per_sub, pool_best, warm_artifact)
        for s in range(n_workers)
    ]
    t0 = time.time()
    with mp.Pool(n_workers) as pool:
        res = pool.map(_coop_worker, args)
    bm, bx, seed = max(res, key=lambda r: r[0])

    e, ll, d, _ = load_instance(path)
    feasible = all(
        arr[bx == 1].size == np.unique(arr[bx == 1]).size for arr in (e, ll, d)
    )
    out_path = Path(out_dir) / f"{problem}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            [{"decisionVector": bx.tolist(), "problem": problem,
              "challenge": CHALLENGE}]
        )
    )
    if os.path.exists(pool_best):
        os.remove(pool_best)
    return {
        "problem": problem,
        "method": "parallel_coop_mip_lns",
        "n_workers": n_workers,
        "best_mass": bm,
        "best_seed": seed,
        "n_selected": int(bx.sum()),
        "feasible": feasible,
        "wall_s": round(time.time() - t0, 1),
        "per_worker_mass": sorted(round(r[0], 1) for r in res),
        "artifact": str(out_path),
    }


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode in ("mip-lns", "coop", "polish"):
        inst, prob = sys.argv[2], sys.argv[3]
        budget = float(sys.argv[4]) if len(sys.argv) > 4 else 600.0
        nw = int(sys.argv[5]) if len(sys.argv) > 5 else 4
        if mode == "polish":  # warm-start from current artifact, big sub-MIPs
            print(json.dumps(parallel_coop_mip_lns(
                inst, prob, n_workers=nw, time_budget_s=budget,
                time_per_sub=25.0,
                warm_artifact=f"solutions/upload/{prob}.json"), indent=2))
        else:
            fn = parallel_coop_mip_lns if mode == "coop" else parallel_mip_lns
            print(json.dumps(fn(inst, prob, n_workers=nw,
                                time_budget_s=budget), indent=2))
    else:  # default: single exact solve
        inst, prob = sys.argv[1], sys.argv[2]
        tl = float(sys.argv[3]) if len(sys.argv) > 3 else 1800.0
        print(json.dumps(solve(inst, prob, time_limit=tl), indent=2))
