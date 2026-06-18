"""E-576b: Ch2 LARGE — CONSTRAINT-AWARE time-dependent greedy (basin escape).

e576 (pure shortest-tof greedy NN) plateaued >=932 because it is MYOPIC: it leaves
low-degree (hard-to-reach) nodes unvisited until late -> endgame degradation forces
long hops near the comp0 giant (0.887 d/leg vs r1's 0.404, vs 0.150 available).

NEW lever (targets that specific gap): bias each hop toward nodes ABOUT TO BE STRANDED.
score[j] = tof[j] / (1 + lam/(rem_cheap_degree[j]+1)); low remaining degree -> smaller
score -> visited sooner even if tof slightly longer. lam=0 reproduces e576. Multi-start
over (start, lam) via internal mp.Pool(4) (ONE micromamba-run process => no env-lock).
Faithful realized-walk eval (walk_perm_chrono + official kt.fitness). Guarded: dumps best
to /tmp only, banks nothing. Instrumented per [[feedback-instrument-experiments]].
Usage: python ch2_e576b_large_constrained_greedy.py [nworkers=4]
"""
import json, os, sys, time
import numpy as np
import multiprocessing as mp
ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
BANK = f"{ROOT}/solutions/upload/large.json"
ADJ = "/tmp/ch2_e533_large_adj.npz"
OUT = "/tmp/ch2_large_constrained_greedy_best.json"
BANK_MK = 932.53; R1 = 424.62
WIN = 4.0; STEPS = 80; WAIT_DT = 0.5; WAIT_MAX = 10; WIDEN_CAP = 120
STRICT = dict(tof_window=40.0, n_steps=300, wait_steps=8, wait_dt=1.0)
_G = {}


def _init():
    kt = KTTSP(INST); n = kt.n
    cheap = np.load(ADJ)["cheap"]
    _G['kt'] = kt; _G['n'] = n
    _G['neigh'] = [list(np.where(cheap[i])[0]) for i in range(n)]
    _G['deg0'] = cheap.sum(axis=1).astype(int)


def constrained_walk(start, lam):
    kt = _G['kt']; n = _G['n']; neigh = _G['neigh']
    visited = np.zeros(n, dtype=bool); visited[start] = True
    rem_deg = _G['deg0'].copy()                      # remaining cheap-degree (unvisited)
    for j in neigh[start]:
        rem_deg[j] -= 1
    order = [start]; cur, t = start, 0.0; exc_used = 0
    for _ in range(n - 1):
        cands = [j for j in neigh[cur] if not visited[j]]
        best_j, best_score, best_tof = None, None, None
        for j in cands:                              # constraint-aware cheap hop
            tof, dv = find_earliest_transfer(kt, cur, int(j), t, kt.dv_thr, WIN, STEPS)
            if tof is None:
                continue
            score = tof / (1.0 + lam / (rem_deg[j] + 1.0))
            if best_score is None or score < best_score:
                best_j, best_score, best_tof = int(j), score, tof
        j, tof = best_j, best_tof
        if j is None and exc_used < kt.n_exc:        # exc hop among cheap neighbors
            for jj in cands:
                tf, dv = find_earliest_transfer(kt, cur, int(jj), t, kt.dv_exc, WIN, STEPS)
                if tf is not None and (tof is None or tf < tof):
                    j, tof = int(jj), tf
            if j is not None:
                exc_used += 1
        if j is None:                                # wait then retry cheap
            for w in range(1, WAIT_MAX + 1):
                tt = t + w * WAIT_DT
                if tt >= kt.max_time:
                    break
                for jj in cands:
                    tf, dv = find_earliest_transfer(kt, cur, int(jj), tt, kt.dv_thr, WIN, STEPS)
                    if tf is not None and (tof is None or tf < tof):
                        j, tof = int(jj), tf
                if j is not None:
                    t = tt; break
        if j is None and exc_used < kt.n_exc:        # widen to all unvisited (capped)
            rest = list(np.where(~visited)[0])[:WIDEN_CAP]
            for jj in rest:
                tf, dv = find_earliest_transfer(kt, cur, int(jj), t, kt.dv_exc, WIN, STEPS)
                if tf is not None and (tof is None or tf < tof):
                    j, tof = int(jj), tf
            if j is not None:
                exc_used += 1
        if j is None:
            return None
        order.append(j); visited[j] = True; t += tof; cur = j
        for k in neigh[j]:
            rem_deg[k] -= 1
    return order


def run_combo(args):
    start, lam = args; kt = _G['kt']; n = _G['n']; t0 = time.time()
    order = constrained_walk(start, lam)
    if order is None or len(set(order)) != n:
        return dict(start=start, lam=lam, mk=None, note="stuck", s=time.time() - t0)
    times, tofs, dvs, ok, exc, leg = walk_perm_chrono(kt, order, **STRICT)
    if not ok:
        return dict(start=start, lam=lam, mk=None, note="strict-reject", s=time.time() - t0)
    x = list(times) + list(tofs) + [float(p) for p in order]
    fit = kt.fitness(x)
    return dict(start=start, lam=lam, mk=float(fit[0]), feas=bool(kt.is_feasible(fit)),
                exc=exc, x=x, s=time.time() - t0)


def main(nw=4):
    kt = KTTSP(INST); n = kt.n
    cheap = np.load(ADJ)["cheap"]; deg = cheap.sum(axis=1).astype(int)
    perm0 = [int(round(v)) for v in json.load(open(BANK))[0]["decisionVector"][2 * (n - 1):]]
    # control: lam=0 from bank start must reproduce e576-like pure-greedy makespan
    lowdeg = list(np.argsort(deg)[:8])
    rng = np.random.default_rng(1)
    starts = [perm0[0]] + [int(x) for x in lowdeg] + [int(x) for x in rng.integers(0, n, 5)]
    seen = set(); starts = [s for s in starts if not (s in seen or seen.add(s))]
    lams = [0.0, 0.5, 1.0, 2.0]
    combos = [(s, l) for s in starts for l in lams]
    print(f"[E-576b] n={n} bank={BANK_MK} r1={R1} | {len(starts)} starts x {len(lams)} lam "
          f"= {len(combos)} combos, {nw} workers", flush=True)
    best = None; done = 0
    with mp.Pool(nw, initializer=_init) as p:
        for r in p.imap_unordered(run_combo, combos):
            done += 1
            if r['mk'] is not None:
                tag = ""
                if r.get('feas') and (best is None or r['mk'] < best['mk']):
                    best = r; tag = " *** NEW BEST"
                print(f"  [{done}/{len(combos)}] start={r['start']} lam={r['lam']} "
                      f"mk={r['mk']:.2f} feas={r.get('feas')} exc={r['exc']} "
                      f"[{r['s']:.0f}s]{tag}", flush=True)
            else:
                print(f"  [{done}/{len(combos)}] start={r['start']} lam={r['lam']} "
                      f"{r['note']} [{r['s']:.0f}s]", flush=True)
    if best is None:
        print("[FINAL] no feasible constrained tour.", flush=True); return
    json.dump([{"decisionVector": best['x'], "problem": "large", "challenge": CHALLENGE}],
              open(OUT, "w"))
    verdict = ("*** BEATS r1=424 -> RANK 1 ***" if best['mk'] < R1
               else "beats bank (still r2)" if best['mk'] < BANK_MK else "no gain vs bank")
    print(f"\n[FINAL] best constrained-greedy mk={best['mk']:.2f} (lam={best['lam']} "
          f"start={best['start']}) vs bank {BANK_MK}/r1 {R1} -> {verdict}\n[OUT] {OUT}", flush=True)


if __name__ == "__main__":
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    main(nw)
