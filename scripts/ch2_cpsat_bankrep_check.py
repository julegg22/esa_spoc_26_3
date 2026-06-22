"""Ch2-small CP-SAT FEASIBILITY GATE (2026-06-22): is the known-feasible BANK representable in the
time-coupled candidate cell set? If not, the E-507 'INFEASIBLE in 77s' was a TRUNCATION artifact (the
model excluded the bank), and the table/top_k is the bug to fix BEFORE any solve — not the problem.

For each bank leg (i->j departing at the bank's t), check the candidate cells (same construction as
E-507) contain a cell (i,j,q) with q ~ bank-departure-quantum and tof_q >= bank tof (so the chrono
coupling t_node[j] >= q+tof_q can match the bank). Reports per-leg representability + the binding
discretization error (bank makespan vs quantized-bank makespan = the FLAW-C offset).

Usage: python ch2_cpsat_bankrep_check.py <table.npz> [top_k=60]"""
import sys, json
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/easy.kttsp")
BANK = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"


def candidates(cheap, exc, t_starts, top_k):
    n = cheap.shape[0]; q = float(t_starts[1] - t_starts[0])
    cand = {}
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            cells = []
            for qi in np.where(np.isfinite(cheap[i, j]))[0]:
                cells.append((int(qi), int(np.ceil(cheap[i, j, qi] / q)), False))
            for qi in np.where(np.isfinite(exc[i, j]))[0]:
                if not np.isfinite(cheap[i, j, qi]):
                    cells.append((int(qi), int(np.ceil(exc[i, j, qi] / q)), True))
            cells.sort(key=lambda c: c[0] + c[1])
            if cells:
                cand[i, j] = cells[:top_k]
    return cand, q


def main():
    tbl = sys.argv[1]
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    kt = KTTSP(INST); n = kt.n
    d = np.load(tbl); cheap, exc, t_starts = d["cheap"], d["exc"], d["t_starts"]
    q = float(t_starts[1] - t_starts[0])
    print(f"[BANKREP] table {tbl}: T={len(t_starts)} quantum={q:.4f}d top_k={top_k}", flush=True)
    cand, q = candidates(cheap, exc, t_starts, top_k)
    print(f"[BANKREP] {len(cand)} candidate pairs, {sum(len(v) for v in cand.values())} cells", flush=True)

    x = np.array(json.load(open(BANK))[0]["decisionVector"], float)
    times = x[:n - 1]; tofs = x[n - 1:2 * (n - 1)]; order = [round(v) for v in x[2 * (n - 1):]]
    bank_mk = times[-1] + tofs[-1]

    missing = []; tof_short = []; quant_arr = []
    for k in range(n - 1):
        i, j = order[k], order[k + 1]
        qd = int(round(times[k] / q))                       # bank departure -> nearest quantum
        cells = cand.get((i, j), [])
        # is there a cell near this departure with tof_q covering the bank tof?
        hit = [c for c in cells if abs(c[0] - qd) <= 1 and c[1] * q >= tofs[k] - q]
        if not (i, j) in cand:
            missing.append((k, i, j, "pair-absent"))
        elif not hit:
            # pair present but no cell at/near the bank's departure epoch
            near = min((abs(c[0] - qd) for c in cells), default=999)
            missing.append((k, i, j, f"no-cell-at-q (nearest dq={near})"))
        else:
            quant_arr.append(qd * q + hit[0][1] * q)        # quantized arrival proxy

    print(f"\n[BANKREP] {n-1-len(missing)}/{n-1} bank legs representable; {len(missing)} NOT", flush=True)
    for (k, i, j, why) in missing[:20]:
        print(f"   leg {k}: {i}->{j}  {why}", flush=True)
    if missing:
        print(f"\n[BANKREP] VERDICT: BANK NOT REPRESENTABLE ⇒ E-507 INFEASIBLE was a TRUNCATION ARTIFACT.", flush=True)
        print(f"   Fix the table coverage / top_k BEFORE solving (ensure every bank edge has a cell).", flush=True)
    else:
        print(f"\n[BANKREP] VERDICT: bank IS representable. Quantized-bank makespan proxy ~"
              f"{max(quant_arr):.3f}d vs official {bank_mk:.4f}d (FLAW-C discretization offset "
              f"{max(quant_arr)-bank_mk:+.3f}d). INFEASIBLE (if any) is a real modeling bug, not truncation.", flush=True)


if __name__ == "__main__":
    main()
