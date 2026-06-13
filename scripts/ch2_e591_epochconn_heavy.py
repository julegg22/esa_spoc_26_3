"""E-591 — Ch2 LARGE epoch-connectivity diagnostic.

Tests whether the 2.2x makespan gap vs r1 (932.53 d bank vs 424.62 d leader)
is an EPOCH-ASSIGNMENT problem (heavy nodes visited at bad epochs; cheap
transfers exist at OTHER epochs) or INTRINSIC (those nodes have no cheap
transfer at ANY epoch).

Step 1: Read the bank decision vector directly (it carries explicit
times[i] departures, tofs[i], perm). List every leg with tof > 3 d (the
heavy tail) and record the bank epoch at which that leg departs.

Step 2: For each heavy-tail SOURCE node (and 739/343/753 specifically),
scan departure epochs across [0, max_time] and, at each epoch, count how
many cheap (dv < dv_thr=100) outgoing transfers it has to a representative
SAMPLE of target nodes, using the same find_earliest_transfer machinery the
evaluator uses. Output the epochs where >=1 cheap outgoing transfer exists.

Step 3: Verdict per node — epoch-locked (cheap epoch exists somewhere) vs
intrinsically expensive (no cheap epoch). Estimate a rough makespan floor.

Diagnostic only. Writes JSON to /tmp/ch2_large_epoch_conn.json. No bank.
"""
import json
import multiprocessing as mp
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
OUT = "/tmp/ch2_large_epoch_conn.json"

HEAVY_TOF = 3.0           # heavy-tail threshold (d)
EPOCH_STEP = 40.0         # epoch sampling step over [0, max_time] -> ~75 eps
N_TARGETS = 25            # representative sample of target nodes per source
TOF_WINDOW = 30.0         # transfer search window
N_STEPS = 60              # tof grid resolution (~0.5 d step over 30 d)
N_WORKERS = 2
FLAG = [739, 343, 753]    # nodes the prior finding (E-590) flagged

_KT = [None]


def _init(inst):
    _KT[0] = KTTSP(inst)


def _scan_node(args):
    """Scan one source node across all epochs; count cheap outgoing
    transfers to a fixed representative target sample at each epoch."""
    src, targets, epochs = args
    kt = _KT[0]
    thr = kt.dv_thr
    counts = []
    for ep in epochs:
        c = 0
        for tgt in targets:
            tof, _ = find_earliest_transfer(kt, src, tgt, float(ep), thr,
                                            TOF_WINDOW, N_STEPS)
            if tof is not None:
                c += 1
        counts.append(c)
    return src, counts


def main():
    t0 = time.time()
    kt = KTTSP(INST)
    n = kt.n
    bank = json.load(open(BANK))[0]["decisionVector"]
    times = bank[:n - 1]
    tofs = bank[n - 1:2 * (n - 1)]
    perm = [int(round(v)) for v in bank[2 * (n - 1):]]
    mk = times[-1] + tofs[-1]
    print(f"[E-591] n={n} bank makespan={mk:.4f} max_time={kt.max_time}",
          flush=True)

    # ---- Step 1: identify heavy-tail legs from the bank vector directly ----
    heavy = []  # (leg_idx, src, dst, dep_epoch, tof, arr_epoch)
    for i in range(n - 1):
        if tofs[i] > HEAVY_TOF:
            heavy.append({
                "leg": i, "src": perm[i], "dst": perm[i + 1],
                "dep_epoch": float(times[i]), "tof": float(tofs[i]),
                "arr_epoch": float(times[i] + tofs[i]),
            })
    heavy_tof_sum = sum(h["tof"] for h in heavy)
    print(f"[E-591] heavy legs (tof>{HEAVY_TOF}d): {len(heavy)}, "
          f"tof-sum={heavy_tof_sum:.2f}d "
          f"({100*heavy_tof_sum/mk:.1f}% of makespan)", flush=True)

    heavy_srcs = sorted({h["src"] for h in heavy})
    # ensure flagged nodes are scanned even if not heavy sources
    scan_nodes = sorted(set(heavy_srcs) | set(FLAG))
    print(f"[E-591] heavy source nodes={len(heavy_srcs)}; "
          f"scanning {len(scan_nodes)} nodes (incl flagged {FLAG})",
          flush=True)

    # representative target sample (deterministic per source), excludes self
    rng = np.random.default_rng(0)
    all_nodes = np.arange(n)
    epochs = np.arange(0.0, kt.max_time - 1.0, EPOCH_STEP)
    targets_by_src = {
        src: rng.choice(all_nodes[all_nodes != src], size=N_TARGETS,
                        replace=False).astype(int).tolist()
        for src in scan_nodes
    }
    print(f"[E-591] scanning {len(scan_nodes)} nodes x {len(epochs)} epochs "
          f"x {N_TARGETS} targets, N_STEPS={N_STEPS}", flush=True)

    # ---- Step 2: epoch-connectivity scan (parallel over source nodes) ----
    args = [(src, targets_by_src[src], epochs) for src in scan_nodes]
    node_results = {}
    done = 0
    with mp.Pool(N_WORKERS, initializer=_init, initargs=(INST,)) as pool:
        for src, counts in pool.imap_unordered(_scan_node, args):
            cc = np.array(counts)
            cheap_epochs = epochs[cc > 0]
            node_results[int(src)] = {
                "n_targets_sampled": N_TARGETS,
                "epochs": epochs.tolist(),
                "cheap_count_per_epoch": cc.tolist(),
                "n_epochs_with_cheap": int((cc > 0).sum()),
                "max_cheap_count": int(cc.max()),
                "first_cheap_epoch": (float(cheap_epochs[0])
                                      if cheap_epochs.size else None),
                "epoch_locked": bool((cc > 0).any()),
            }
            done += 1
            tag = " <FLAG>" if src in FLAG else ""
            print(f"  [{done}/{len(scan_nodes)}] node {src}{tag}: "
                  f"epochs_with_cheap={int((cc>0).sum())}/{len(epochs)} "
                  f"max_cnt={int(cc.max())} first_cheap_ep="
                  f"{float(cheap_epochs[0]) if cheap_epochs.size else None}",
                  flush=True)

    # ---- Step 3: verdict + floor estimate ----
    locked = [s for s, r in node_results.items()
              if r["epoch_locked"] and s in heavy_srcs]
    intrinsic = [s for s, r in node_results.items()
                 if not r["epoch_locked"] and s in heavy_srcs]

    # rough floor: if every heavy leg could be replaced by a min-tof cheap
    # transfer (>= min_tof, count it as ~min_tof for a cheap arc), how much
    # tof would the tour shed? Heavy legs whose SOURCE is epoch-locked could
    # plausibly become cheap (short tof) under a different epoch assignment.
    saved_if_relocated = 0.0
    residual_intrinsic = 0.0
    for h in heavy:
        if node_results[h["src"]]["epoch_locked"]:
            # could shrink to ~a cheap-arc tof; assume ~1 d representative
            saved_if_relocated += max(0.0, h["tof"] - 1.0)
        else:
            residual_intrinsic += h["tof"]
    floor_est = mk - saved_if_relocated

    summary = {
        "bank_makespan_d": float(mk),
        "leader_r1_d": 424.62,
        "max_time_d": float(kt.max_time),
        "heavy_tof_threshold_d": HEAVY_TOF,
        "n_heavy_legs": len(heavy),
        "heavy_tof_sum_d": float(heavy_tof_sum),
        "heavy_legs": heavy,
        "n_heavy_source_nodes": len(heavy_srcs),
        "n_epoch_locked_heavy_sources": len(locked),
        "n_intrinsic_heavy_sources": len(intrinsic),
        "epoch_locked_heavy_sources": locked,
        "intrinsic_heavy_sources": intrinsic,
        "flagged_nodes": {str(s): node_results[s] for s in FLAG
                          if s in node_results},
        "rough_floor_if_heavy_relocated_d": float(floor_est),
        "residual_intrinsic_tof_d": float(residual_intrinsic),
        "epoch_step_d": EPOCH_STEP,
        "n_targets_sampled": N_TARGETS,
        "wall_s": round(time.time() - t0, 1),
        "per_node": node_results,
    }
    json.dump(summary, open(OUT, "w"))
    print(f"\n[E-591] VERDICT: heavy sources epoch-locked={len(locked)} "
          f"intrinsic={len(intrinsic)}", flush=True)
    for s in FLAG:
        if s in node_results:
            r = node_results[s]
            print(f"  node {s}: epoch_locked={r['epoch_locked']} "
                  f"n_epochs_with_cheap={r['n_epochs_with_cheap']} "
                  f"first_cheap_ep={r['first_cheap_epoch']}", flush=True)
    print(f"[E-591] rough floor if heavy relocated ~{floor_est:.1f}d "
          f"(residual intrinsic tof {residual_intrinsic:.1f}d)", flush=True)
    print(f"[E-591] wrote {OUT} ({summary['wall_s']}s)", flush=True)


if __name__ == "__main__":
    main()
