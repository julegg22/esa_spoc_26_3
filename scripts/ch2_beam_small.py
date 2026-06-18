"""E-656 lever #2 (E-654 audit): TIME-EXPANDED BEAM SEARCH for Ch2-small.

The loss is epoch-phasing inside the giant cheap-component; greedy-NN is too myopic
(endgame degradation) and local search can't escape. A BEAM over (current city, arrival
epoch) keeps the top-K partial paths instead of 1 — less myopic, epoch-committed by
construction (avoids the time-dependent reordering trap). Fast expansion via the CORRECTED
ultrafine table (epoch-bucketed min cheap/exc tof); final complete tours validated faithfully
via walk_perm_chrono + official kt.fitness. Multi-start (initial beam = all cities).

Beats 112.996? → basin-overarching works; scale beam to large's 601-giant (rank 2→1).
Guard: dumps best <bank to /tmp, banks NOTHING. Usage: python ch2_beam_small.py [K=800] [nvalidate=60]
"""
import sys, json, time, heapq
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/easy.kttsp")
BANK = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
STRICT = dict(tof_window=12.0, n_steps=200, wait_steps=8, wait_dt=0.5)


def main(K=800, nval=60):
    kt = KTTSP(INST); n = kt.n
    d = np.load('/tmp/ch2_small_tcoupled_ultrafine.npz')
    cheap = d['cheap']; exc = d['exc']; t_starts = d['t_starts']
    q = float(t_starts[1] - t_starts[0]); T = len(t_starts)
    bank = float(kt.fitness(json.load(open(BANK))[0]['decisionVector'])[0])
    print(f"[E-656] n={n} bank={bank:.3f} | beam K={K}, table q={q} T={T}", flush=True)

    def bk(ep):
        b = int(round(ep / q));  return b if b < T else T - 1

    # beam state: (makespan_proxy, cur, epoch, visited_bitmask, exc_used, path_tuple)
    full = (1 << n) - 1
    beam = [(0.0, c, 0.0, (1 << c), 0, (c,)) for c in range(n)]
    t0 = time.time()
    for step in range(n - 1):
        cand = []
        for mk, cur, ep, vis, eu, path in beam:
            b = bk(ep)
            crow = cheap[cur, :, b]; erow = exc[cur, :, b]
            for j in range(n):
                if vis >> j & 1:
                    continue
                tof = crow[j]
                if np.isfinite(tof):
                    cand.append((ep + tof, j, ep + tof, vis | (1 << j), eu, path + (j,)))
                elif eu < kt.n_exc:
                    te = erow[j]
                    if np.isfinite(te):
                        cand.append((ep + te, j, ep + te, vis | (1 << j), eu + 1, path + (j,)))
        if not cand:
            print(f"  [step {step}] beam DIED (all paths stranded) — widen K or exc", flush=True)
            break
        # keep top-K by makespan proxy (+ light diversity: dedup by (cur,vis))
        cand.sort(key=lambda x: x[0])
        seen = set(); beam = []
        for c in cand:
            key = (c[1], c[3])
            if key in seen:
                continue
            seen.add(key); beam.append((c[0], c[1], c[2], c[3], c[4], c[5]))
            if len(beam) >= K:
                break
        if step % 8 == 0:
            print(f"  [step {step}/{n-1}] beam={len(beam)} best_proxy={beam[0][0]:.3f} "
                  f"[{time.time()-t0:.0f}s]", flush=True)
    complete = [s for s in beam if s[3] == full and len(set(s[5])) == n]
    print(f"[beam done] {len(complete)} complete tours; validating top {nval} faithfully...", flush=True)
    complete.sort(key=lambda x: x[0])
    best_mk = 1e9; best_x = None; nfeas = 0
    for s in complete[:nval]:
        order = list(s[5])
        times, tofs, dvs, ok, exc_c, leg = walk_perm_chrono(kt, order, **STRICT)
        if not ok:
            continue
        x = list(times) + list(tofs) + [float(p) for p in order]
        f = kt.fitness(x)
        if kt.is_feasible(f):
            nfeas += 1
            if f[0] < best_mk:
                best_mk = float(f[0]); best_x = x
                tag = " *** <BANK" if best_mk < bank else ""
                print(f"    proxy={s[0]:.2f} -> official mk={best_mk:.3f} ({best_mk-bank:+.3f}){tag}", flush=True)
    print(f"\n[DONE] {nfeas}/{min(nval,len(complete))} validated feasible | best official mk={best_mk:.3f} "
          f"vs bank {bank:.3f} | rank4=111.76 rank3=110.88", flush=True)
    if best_x is not None and best_mk < bank - 1e-4:
        json.dump({"makespan": best_mk, "decisionVector": best_x}, open('/tmp/ch2_small_beam_best.json', 'w'))
        v = "BEATS rank4 111.76!" if best_mk < 111.76 else "beats bank"
        print(f"  -> {v}; dumped /tmp/ch2_small_beam_best.json (guard-bank decision to caller)", flush=True)
    else:
        print(f"  -> beam did NOT beat bank. INFO: best beam tour = {best_mk:.3f} "
              f"(proxy ranks by table-epoch; gap to official shows phasing residual).", flush=True)


if __name__ == "__main__":
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 800
    nv = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    main(K, nv)
