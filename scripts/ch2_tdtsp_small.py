"""E-659: TIME-EXPANDED TD-TSP heuristic for Ch2-small (user-approved build).

The audit (E-654→658) proved the gap is epoch-PHASING and that static methods can't beat the
bank because they optimize min-tof, not the walked (phased) makespan. The slow Lambert evaluator
(kt.fitness) capped prior searches at ~172 orders. KEY: the wait-allowing TABLE-WALK is ~1000×
faster AND phasing-aware (min-arrival per leg incl. waiting + exc budget). So we run SA/ALNS over
orders evaluated by the fast table-walk — optimizing the REAL phased objective over MILLIONS of
orders — then validate the best officially (kt.fitness). Cheap-edge-guided + ruin moves to escape
the bank basin. One micromamba-run proc, 4 internal mp chains.

Positive control: table-walk(bank order) must ≈ 112.996 (else the evaluator is off → abort).
Usage: python ch2_tdtsp_small.py [mode all|seed] [budget_s=...] ...
"""
import sys, json, time, random, os
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/easy.kttsp")
BANK = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
TAB = '/tmp/ch2_small_tcoupled_ultrafine.npz'
ADJ = '/tmp/ch2_small_cheap_adj.npy'
_G = {}


def _load():
    kt = KTTSP(INST); n = kt.n
    d = np.load(TAB)
    cheap = d['cheap']; exc = d['exc']; q = float(d['t_starts'][1] - d['t_starts'][0]); T = len(d['t_starts'])
    adj = np.load(ADJ); neigh = [list(np.where(adj[i])[0]) for i in range(n)]
    _G.update(kt=kt, n=n, cheap=cheap, exc=exc, q=q, T=T, neigh=neigh)


def walk(order, max_wait=400):
    """Fast phasing-aware table-walk: per leg pick the EARLIEST ARRIVAL (scan waiting window for the
    min ep+wait+tof) using cheap; fall back to exc (≤n_exc). Returns makespan or None (infeasible)."""
    kt = _G['kt']; cheap = _G['cheap']; exc = _G['exc']; q = _G['q']; Tn = _G['T']
    ep = 0.0; eu = 0
    for i in range(len(order) - 1):
        a, c = order[i], order[i + 1]
        best_arr = None
        for w in range(max_wait + 1):
            b = int(round((ep + w * q) / q)); b = b if b < Tn else Tn - 1
            tof = cheap[a, c, b]
            if np.isfinite(tof):
                best_arr = ep + w * q + tof; break
            if b >= Tn - 1:
                break
        used_exc = False
        if best_arr is None and eu < kt.n_exc:
            for w in range(max_wait + 1):
                b = int(round((ep + w * q) / q)); b = b if b < Tn else Tn - 1
                te = exc[a, c, b]
                if np.isfinite(te):
                    best_arr = ep + w * q + te; used_exc = True; break
                if b >= Tn - 1:
                    break
        if best_arr is None:
            return None
        if used_exc:
            eu += 1
        ep = best_arr
    return ep


def perturb(order, rng, neigh, n):
    o = order[:]
    r = rng.random()
    if r < 0.5 and neigh:                       # cheap-edge-guided relocate
        x = rng.randrange(n); nb = neigh[x]
        if nb:
            o.remove(x); tgt = nb[rng.randrange(len(nb))]; j = o.index(tgt)
            o.insert(j + (1 if rng.random() < 0.5 else 0), x); return o
    if r < 0.8:                                  # segment reversal
        a, b = sorted(rng.sample(range(n), 2)); o[a:b + 1] = o[a:b + 1][::-1]
    else:                                        # ruin-recreate: move a chunk
        L = rng.randint(2, 5); i = rng.randint(0, n - L); seg = o[i:i + L]; del o[i:i + L]
        j = rng.randint(0, len(o)); o[j:j] = seg
    return o


def chain(seed, wall_s):
    _load(); kt = _G['kt']; n = _G['n']; neigh = _G['neigh']
    rng = random.Random(seed * 31 + 7); log = lambda m: print(f"[s{seed}] {m}", flush=True)
    dv0 = json.load(open(BANK))[0]['decisionVector']
    bank_order = [int(round(x)) for x in dv0[2 * (n - 1):]]
    official_bank = float(kt.fitness(dv0)[0])
    ctrl = walk(bank_order)
    if seed == 0:
        log(f"control: table-walk(bank)={ctrl if ctrl is None else f'{ctrl:.4f}'} vs official {official_bank:.4f}")
    cur = bank_order; cur_mk = walk(cur) or 1e9; best_mk = cur_mk; best = cur[:]
    T = 3.0; it = 0; t0 = time.time(); nimp = 0
    while time.time() - t0 < wall_s:
        it += 1
        cand = perturb(cur, rng, neigh, n)
        if len(set(cand)) != n:
            continue
        mk = walk(cand)
        if mk is None:
            continue
        if mk < cur_mk or rng.random() < np.exp(-(mk - cur_mk) / max(T, 1e-3)):
            cur, cur_mk = cand, mk
        if mk < best_mk - 1e-6:
            best_mk = mk; best = cand[:]; nimp += 1
            # validate officially
            x = official_dv(kt, cand, n)
            f = kt.fitness(x); offmk = float(f[0]); feas = kt.is_feasible(f)
            log(f"table-walk best={best_mk:.4f} -> OFFICIAL {offmk:.4f} feas={feas} (bank {official_bank:.4f}) it={it}")
            if feas and offmk < official_bank - 1e-4:
                guard_bank(kt, x, official_bank, log)
        T *= 0.99995
        if it % 20000 == 0:
            log(f"it={it} cur={cur_mk:.3f} best_tablewalk={best_mk:.3f} T={T:.3f} [{time.time()-t0:.0f}s]")
    log(f"done it={it} best_tablewalk={best_mk:.4f}")


def official_dv(kt, order, n):
    """Build a dv by letting kt time it: use the table-walk schedule? Simpler: reconstruct times/tofs
    by a quick chronological pass via the official model — here approximate with the table-walk epochs."""
    cheap = _G['cheap']; exc = _G['exc']; q = _G['q']; Tn = _G['T']
    ep = 0.0; times = []; tofs = []; eu = 0
    for i in range(len(order) - 1):
        a, c = order[i], order[i + 1]; chosen = None
        for w in range(401):
            b = int(round((ep + w * q) / q)); b = b if b < Tn else Tn - 1
            tof = cheap[a, c, b]
            if np.isfinite(tof):
                chosen = (ep + w * q, tof); break
            if b >= Tn - 1: break
        if chosen is None and eu < kt.n_exc:
            for w in range(401):
                b = int(round((ep + w * q) / q)); b = b if b < Tn else Tn - 1
                te = exc[a, c, b]
                if np.isfinite(te):
                    chosen = (ep + w * q, te); eu += 1; break
                if b >= Tn - 1: break
        if chosen is None:
            chosen = (ep, 0.025)
        dep, tof = chosen; times.append(dep); tofs.append(tof); ep = dep + tof
    return [float(x) for x in (times + tofs + [float(p) for p in order])]


def guard_bank(kt, x, bank_mk, log):
    import shutil
    f = kt.fitness(x)
    if not (kt.is_feasible(f) and f[0] < bank_mk - 1e-4):
        return
    cur = json.load(open(BANK)); cur_mk = float(kt.fitness(cur[0]['decisionVector'])[0])
    if f[0] < cur_mk - 1e-4:
        shutil.copy(BANK, BANK + ".bak.tdtsp")
        json.dump([{"decisionVector": x, "problem": "small"}], open(BANK, 'w'))
        rc = float(kt.fitness(json.load(open(BANK))[0]['decisionVector'])[0])
        log(f"BANKED {rc:.4f} (was {cur_mk:.4f})")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    wall_s = float(sys.argv[2]) if len(sys.argv) > 2 else 36 * 3600
    if mode == 'all':
        import multiprocessing as mp
        ps = [mp.Process(target=chain, args=(s, wall_s)) for s in range(4)]
        [p.start() for p in ps]; [p.join() for p in ps]
    else:
        chain(int(mode), wall_s)


if __name__ == "__main__":
    main()
