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


def solve(path, problem, out_dir="solutions/upload", time_limit=1800.0, threads=0):
    e, ll, d, w = load_instance(path)
    n = w.shape[0]
    model = build_model(e, ll, d, w)

    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    h.setOptionValue("time_limit", float(time_limit))
    h.setOptionValue("mip_rel_gap", 0.0)
    if threads:
        h.setOptionValue("threads", int(threads))
    h.passModel(model)
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


if __name__ == "__main__":
    inst, prob = sys.argv[1], sys.argv[2]
    tl = float(sys.argv[3]) if len(sys.argv) > 3 else 1800.0
    res = solve(inst, prob, time_limit=tl)
    print(json.dumps(res, indent=2))
