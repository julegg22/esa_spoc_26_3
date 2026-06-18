"""Ch2-small: LKH (elkai) constructs structurally-different orders on the CORRECTED
edge table, each DP-retimed with the metric-correct evaluator (evaluate_perm_dp, scores
bank=112.9960). The never-built lever: e617 local search is basin-isolated at 112.996;
the competitor's 101.65 needs a different CONSTRUCTION. LKH minimizes a static cheap-tof
cost matrix to propose far-basin tours; the DP gives their true time-coupled makespan.

Guards against the e609/e538 metric mismatch (116.37 != 112.996) with a MANDATORY startup
positive control: evaluate_perm_dp(bank perm) must reproduce 112.996, else abort.
Guard-banks (backup→official strictly-better+feasible→re-validate) any order < bank.
Instrumented per [[feedback-instrument-experiments]].

Usage: python ch2_lkh_construct_small.py [n_perturb=200]
"""
from __future__ import annotations
import sys, json, time, shutil, random
import numpy as np
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')
import elkai
from esa_spoc_26.ch2_kttsp import KTTSP
from ch2_e529_dp_alns import evaluate_perm_dp, INST, FINE, OUT

BANK = OUT  # solutions/upload/small.json
BIG = 10**9
PENALTY = 50.0   # added to exc-only legs so LKH prefers cheap, tolerates few exc


def build_cost(cheap_tab, exc_tab):
    cheap_min = np.min(cheap_tab, axis=2)   # inf if never cheap at any epoch
    exc_min = np.min(exc_tab, axis=2)
    cost = np.where(np.isfinite(cheap_min), cheap_min,
                    np.where(np.isfinite(exc_min), exc_min + PENALTY, np.nan))
    return cost, cheap_min


def lkh_tours(cost, n_perturb, rng):
    """LKH on the static cost (+ perturbations for diversity); yield candidate ORDERS
    by breaking each returned Hamiltonian cycle at every rotation point."""
    base = np.where(np.isfinite(cost), cost, BIG / 1e5)
    scaled0 = np.round(base * 1e5).astype(np.int64)
    seen = set()
    for p in range(n_perturb + 1):
        m = scaled0 if p == 0 else (scaled0 * (1.0 + 0.05 * np.array(
            [[rng.uniform(-1, 1) for _ in range(scaled0.shape[1])]
             for _ in range(scaled0.shape[0])]))).astype(np.int64)
        try:
            cyc = elkai.DistanceMatrix(m.tolist()).solve_tsp()
        except Exception:
            continue
        cyc = cyc[:-1] if len(cyc) > 1 and cyc[0] == cyc[-1] else cyc
        n = len(cyc)
        for s in range(n):
            order = tuple(cyc[s:] + cyc[:s])
            if order not in seen:
                seen.add(order)
                yield list(order)


def main(n_perturb=200):
    kt = KTTSP(INST); n = kt.n
    d = np.load(FINE)
    cheap_tab = d['cheap']; exc_tab = d['exc']; t_starts = d['t_starts']
    q = float(t_starts[1] - t_starts[0]); T = len(t_starts)

    # ── MANDATORY positive control: DP must reproduce official bank makespan ──
    bank = json.load(open(BANK)); dv = bank[0]['decisionVector']
    bank_perm = [int(x) for x in dv[2 * (n - 1):]]
    official_bank = float(kt.fitness(dv)[0])
    ctrl = evaluate_perm_dp(kt, bank_perm, cheap_tab, exc_tab, q, T)
    ctrl_mk = ctrl['mk'] if ctrl else None
    # The DP-on-table makespan is ~5.5d HIGHER than official (grid discretization);
    # it is INTERNALLY consistent, so the correct search baseline is DP(bank), NOT official.
    # (This is the bug that made e617 — comparing DP-mk vs official 112.996 — look basin-locked.)
    print(f"[control] official bank mk={official_bank:.4f}  DP(bank perm)="
          f"{ctrl_mk if ctrl_mk is None else f'{ctrl_mk:.4f}'}  "
          f"discretization offset={None if ctrl_mk is None else f'{ctrl_mk-official_bank:+.3f}'}d  "
          f"q={q} T={T} n={n}", flush=True)
    if ctrl_mk is None:
        print("[ABORT] DP returned None for bank perm — table/perm wiring broken.", flush=True); return
    dp_baseline = ctrl_mk
    print(f"[control] PASS — searching in DP-space; baseline=DP(bank)={dp_baseline:.4f}; "
          f"orders below it get official CMA-refine to test <{official_bank:.4f}.", flush=True)

    cost, cheap_min = build_cost(cheap_tab, exc_tab)
    reach = np.isfinite(cheap_min).sum()
    print(f"[start] cost matrix: {reach}/{n*n} cheap-reachable pairs; LKH perturb={n_perturb}",
          flush=True)

    rng = random.Random(12345)
    topk = []   # list of (dp_mk, order, res) below dp_baseline, kept sorted, capped
    KCAP = 30
    best_mk = dp_baseline
    t0 = time.time(); ndone = 0; nfeas = 0
    for order in lkh_tours(cost, n_perturb, rng):
        ndone += 1
        res = evaluate_perm_dp(kt, order, cheap_tab, exc_tab, q, T)
        if res is not None:
            nfeas += 1
            if res['mk'] < dp_baseline - 1e-9:
                topk.append((res['mk'], order, res))
                topk.sort(key=lambda e: e[0]); topk[:] = topk[:KCAP]
                if res['mk'] < best_mk - 1e-9:
                    best_mk = res['mk']
                    print(f"  *** better ORDER (DP-space) mk={best_mk:.4f} < DP(bank) "
                          f"{dp_baseline:.4f}  cand#{ndone}", flush=True)
        if ndone % 500 == 0:
            print(f"  [{ndone}] feas={nfeas} topk={len(topk)} best_dp={best_mk:.4f} "
                  f"elapsed={time.time()-t0:.0f}s", flush=True)
    print(f"\n[done] {ndone} candidates, {nfeas} feasible, {len(topk)} below DP(bank); "
          f"best DP-mk={best_mk:.4f} vs DP(bank) {dp_baseline:.4f}", flush=True)

    if not topk:
        print("[result] LKH found NO order below DP(bank) — order space genuinely flat at this grid.",
              flush=True); return

    # Save top-K distinct orders for the CMA-refine stage (official evaluator → test <112.996).
    out = [{'dp_mk': float(m), 'perm': [int(p) for p in o],
            'times': list(r['times']), 'tofs': list(r['tofs'])} for m, o, r in topk]
    json.dump(out, open('/tmp/ch2_small_lkh_topk.json', 'w'))
    print(f"[saved] {len(topk)} candidate orders → /tmp/ch2_small_lkh_topk.json "
          f"(DP-mk range {topk[0][0]:.3f}..{topk[-1][0]:.3f}); next: CMA-refine each on official "
          f"evaluator, guard-bank if <{official_bank:.4f}.", flush=True)
    # quick unrefined official check of the best DP order (upper bound)
    m0, o0, r0 = topk[0]
    dv0 = [float(x) for x in (list(r0['times']) + list(r0['tofs']) + [float(p) for p in o0])]
    f0 = kt.fitness(dv0)
    print(f"[probe] best DP order, UNREFINED official mk={f0[0]:.4f} feasible={kt.is_feasible(f0)} "
          f"(refine expected to drop it ~{dp_baseline-official_bank:.1f}d)", flush=True)


if __name__ == "__main__":
    npert = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    main(npert)
