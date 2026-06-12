"""E-571 — Ch2 LARGE: gap-decomposition probe (1048d -> r1=424d).

DECISIVE DIAGNOSTIC, NOT a search. Before committing cores to a
speculative topology rebuild, quantify WHERE the 624d gap lives.

The makespan = sum(tof) + idle. Our 1048d bank averages ~1d/leg; r1=424d
implies ~0.4d/leg over 1050 legs. Hypothesis (H-A): short cheap transfers
ARE available at the right departure epochs, but our chronological
greedy + frozen 4-component topology (E-562b) is forced into long legs by
ORDERING. If true, a time-dependent rebuild can recover the gap.

Two measurements:
  A) Current bank's realized per-leg tof distribution (sum, mean, pctiles,
     counts/excess over thresholds) -> where realized makespan sits.
  B) Epoch-availability probe: for a random sample of nodes, at a grid of
     departure epochs, find the MINIMUM cheap tof to any cheap-neighbor
     (find_earliest_transfer = earliest feasible tof). If the per-epoch
     median min-cheap-tof << realized avg leg, the gap is phasing/ordering
     -recoverable (justifies the time-dependent rebuild). If min-tof ~=
     realized, the floor is physical and 424 needs a different lever.

Read-only. Writes a JSON summary to /tmp ONLY. Banks nothing.
"""
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from esa_spoc_26.ch2_kttsp import KTTSP  # noqa: E402
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer  # noqa: E402

INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
BANK = f"{ROOT}/solutions/upload/large.json"
ADJ = "/tmp/ch2_e533_large_adj.npz"
OUT = "/tmp/ch2_e571_gap_probe.json"

N_SAMPLE = int(os.environ.get("E571_NSAMPLE", "150"))
N_NBR = int(os.environ.get("E571_NNBR", "40"))      # cheap-neighbors / node
N_EPOCHS = int(os.environ.get("E571_NEPOCHS", "11"))
EPOCH_HI = float(os.environ.get("E571_EPOCH_HI", "1100.0"))
TOF_WINDOW = float(os.environ.get("E571_TOFWIN", "12.0"))
N_STEPS = int(os.environ.get("E571_NSTEPS", "120"))
WORKERS = int(os.environ.get("E571_WORKERS", "4"))
SEED = 0

_KT = [None]
_CHEAP = [None]


def _init(inst, adj):
    _KT[0] = KTTSP(inst)
    _CHEAP[0] = np.load(adj)["cheap"]


def _probe_node(args):
    """For node i, at each epoch, the MIN cheap tof to its sampled
    cheap-neighbors. Returns (i, [min_tof_per_epoch], [n_feasible_per_epoch])."""
    i, nbrs, epochs = args
    kt = _KT[0]
    out_min = []
    out_cnt = []
    for t in epochs:
        best = np.inf
        cnt = 0
        for j in nbrs:
            tof, dv = find_earliest_transfer(
                kt, int(i), int(j), float(t), kt.dv_thr, TOF_WINDOW, N_STEPS)
            if tof is not None:
                cnt += 1
                if tof < best:
                    best = tof
        out_min.append(best if np.isfinite(best) else np.nan)
        out_cnt.append(cnt)
    return int(i), out_min, out_cnt


def main():
    kt = KTTSP(INST)
    cheap = np.load(ADJ)["cheap"]
    rng = np.random.default_rng(SEED)

    # ---- Part A: current bank realized tof distribution ----
    bank = json.load(open(BANK))[0]["decisionVector"]
    n = kt.n
    times = np.array(bank[:n - 1], dtype=float)
    tofs = np.array(bank[n - 1:2 * (n - 1)], dtype=float)
    perm = [int(round(v)) for v in bank[2 * (n - 1):]]
    fit = kt.fitness(bank)
    mk = float(fit[0])
    idle = mk - float(tofs.sum())
    pct = np.percentile(tofs, [10, 25, 50, 75, 90, 99])
    print(f"[A] bank mk={mk:.2f}d feas={bool(kt.is_feasible(fit))} "
          f"n_legs={len(tofs)}", flush=True)
    print(f"[A] tof: sum={tofs.sum():.1f} idle={idle:.1f} mean={tofs.mean():.3f} "
          f"max={tofs.max():.2f}", flush=True)
    print(f"[A] tof pctiles p10/25/50/75/90/99 = "
          f"{', '.join(f'{p:.3f}' for p in pct)}", flush=True)
    for thr in (0.5, 1.0, 2.0, 3.0):
        m = tofs > thr
        print(f"[A]   legs>{thr}d: {int(m.sum())} "
              f"excess_over_{thr}={float((tofs[m]-thr).sum()):.1f}d", flush=True)
    # r1 target avg
    print(f"[A] r1=424.62d -> avg/leg {424.62/len(tofs):.3f}d "
          f"(ours {mk/len(tofs):.3f}d)", flush=True)

    # ---- Part B: epoch-availability probe ----
    epochs = list(np.linspace(0.0, EPOCH_HI, N_EPOCHS))
    sample = rng.choice(n, size=min(N_SAMPLE, n), replace=False)
    tasks = []
    for i in sample:
        nbr_all = np.where(cheap[i])[0]
        nbr_all = nbr_all[nbr_all != i]
        if len(nbr_all) == 0:
            continue
        nbrs = rng.choice(nbr_all, size=min(N_NBR, len(nbr_all)),
                          replace=False)
        tasks.append((int(i), [int(x) for x in nbrs], epochs))
    print(f"\n[B] probing {len(tasks)} nodes x {N_EPOCHS} epochs "
          f"x <= {N_NBR} cheap-nbrs (window={TOF_WINDOW}d, steps={N_STEPS}, "
          f"workers={WORKERS})", flush=True)

    min_by_epoch = [[] for _ in range(N_EPOCHS)]
    cnt_by_epoch = [[] for _ in range(N_EPOCHS)]
    t0 = time.time()
    with mp.Pool(WORKERS, initializer=_init, initargs=(INST, ADJ)) as p:
        done = 0
        for i, mins, cnts in p.imap_unordered(_probe_node, tasks, chunksize=1):
            for e in range(N_EPOCHS):
                if not np.isnan(mins[e]):
                    min_by_epoch[e].append(mins[e])
                cnt_by_epoch[e].append(cnts[e])
            done += 1
            if done % 25 == 0:
                print(f"  [B] {done}/{len(tasks)} nodes "
                      f"({time.time()-t0:.0f}s)", flush=True)
    print(f"[B] done {time.time()-t0:.0f}s\n", flush=True)

    print(f"[B] {'epoch':>8} {'p10':>7} {'med':>7} {'p90':>7} "
          f"{'mean_cnt':>9} {'frac_feas':>9}", flush=True)
    rows = []
    for e in range(N_EPOCHS):
        arr = np.array(min_by_epoch[e]) if min_by_epoch[e] else np.array([np.nan])
        cnts = np.array(cnt_by_epoch[e])
        p10, med, p90 = np.percentile(arr, [10, 50, 90])
        mean_cnt = float(cnts.mean())
        frac = float((cnts > 0).mean())
        print(f"[B] {epochs[e]:8.0f} {p10:7.3f} {med:7.3f} {p90:7.3f} "
              f"{mean_cnt:9.1f} {frac:9.2f}", flush=True)
        rows.append(dict(epoch=epochs[e], min_p10=float(p10), min_med=float(med),
                         min_p90=float(p90), mean_feas_nbrs=mean_cnt,
                         frac_with_feas=frac))

    # ---- Verdict ----
    overall_med = float(np.nanmedian(np.concatenate(
        [np.array(x) for x in min_by_epoch if x] or [np.array([np.nan])])))
    realized_avg = float(mk / len(tofs))
    print(f"\n[VERDICT] overall median min-cheap-tof={overall_med:.3f}d vs "
          f"realized avg leg={realized_avg:.3f}d", flush=True)
    if overall_med < 0.6 * realized_avg:
        print("[VERDICT] => SHORT transfers ARE abundant at good epochs; the "
              "624d gap is largely ORDERING/PHASING-recoverable. A "
              "time-dependent rebuild (freed topology, epoch-aware LKH) is "
              "justified.", flush=True)
    else:
        print("[VERDICT] => min-cheap-tof ~ realized leg; per-leg floor is "
              "physical. 424d likely needs a different lever (not just "
              "ordering).", flush=True)

    json.dump(dict(
        bank_mk=mk, tof_sum=float(tofs.sum()), idle=float(idle),
        tof_mean=float(tofs.mean()),
        tof_pctiles=dict(zip(["p10", "p25", "p50", "p75", "p90", "p99"],
                             [float(x) for x in pct])),
        realized_avg_leg=realized_avg, overall_median_min_tof=overall_med,
        epochs=rows), open(OUT, "w"), indent=2)
    print(f"[OUT] {OUT}", flush=True)


if __name__ == "__main__":
    main()
