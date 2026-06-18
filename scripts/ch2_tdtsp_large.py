"""E-661: TD-TSP SA search for Ch2-LARGE on the epoch-resolved table (user-approved build).

The table-walk evaluator is FAITHFUL for large (L1: offset≈0) and ~1000× faster than kt.fitness —
the unlock prior slow-Lambert searches lacked. SA over large orders evaluated by the fast wait-
allowing table-walk (cheap legs via /tmp/ch2_large_epoch_table.npz; ≤5 exc legs via live
compute_transfer). Cheap-edge-guided relocate + segment-reverse + LARGE ruin-and-recreate to escape
the 932 basin. Guard-bank if official kt.fitness <932.53; <424 = RANK 1 (escalate).

MANDATORY positive control: table-walk(large bank order) must ≈ 932.53 (else table too coarse/off → abort).
Usage: python ch2_tdtsp_large.py [seed=0] [wall_s=...]
"""
import sys, json, time, random, shutil
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
BANK = f"{ROOT}/solutions/upload/large.json"
# 120-epoch table proved too coarse (8d buckets miss <8d cheap windows). Use the FAITHFUL live walk
# (walk_perm_chrono) — ~0.2-1s per large order; control reproduces 932.53. Slower than a table but correct.
STRICT = dict(tof_window=40.0, n_steps=300, wait_steps=8, wait_dt=1.0)
_G = {}


def _load():
    kt = KTTSP(INST); n = kt.n
    adj = np.load('/tmp/ch2_e533_large_adj.npz')['cheap']
    neigh = [list(np.where(adj[i])[0]) for i in range(n)]
    _G.update(kt=kt, n=n, neigh=neigh)


def walk(order):
    """Faithful live walk: returns (makespan or None). Feasibility via official kt.fitness."""
    kt = _G['kt']
    times, tofs, dvs, ok, exc, leg = walk_perm_chrono(kt, order, **STRICT)
    if not ok:
        return None
    x = list(times) + list(tofs) + [float(p) for p in order]
    f = kt.fitness(x)
    if not kt.is_feasible(f):
        return None
    _G['_lastx'] = x
    return float(f[0])


def perturb(order, rng):
    n = _G['n']; neigh = _G['neigh']; o = order[:]; r = rng.random()
    if r < 0.45 and neigh:
        x = rng.randrange(n); nb = [j for j in neigh[x]]
        if nb:
            o.remove(x); tgt = nb[rng.randrange(len(nb))]; j = o.index(tgt)
            o.insert(j + (1 if rng.random() < 0.5 else 0), x); return o
    if r < 0.75:
        a, b = sorted(rng.sample(range(n), 2)); o[a:b + 1] = o[a:b + 1][::-1]
    else:
        L = rng.randint(3, 30); i = rng.randint(0, n - L); seg = o[i:i + L]; del o[i:i + L]
        j = rng.randint(0, len(o)); o[j:j] = seg
    return o


def official_mk(order):
    """Build a dv from the table-walk schedule and score officially."""
    kt = _G['kt']; table = _G['table']; epochs = _G['epochs']; ne = _G['ne']; n = _G['n']
    ep = 0.0; times = []; tofs = []; eu = 0
    for i in range(len(order) - 1):
        a, c = order[i], order[i + 1]; chosen = None; row = table.get((a, c))
        if row is not None:
            ei0 = int(np.searchsorted(epochs, ep))
            for ei in range(ei0, min(ei0 + 80, ne)):
                if np.isfinite(row[ei]): chosen = (epochs[ei], row[ei]); break
        if chosen is None and eu < kt.n_exc:
            for tof in TOFS:
                try:
                    if kt.compute_transfer(a, c, float(ep), float(tof)) <= kt.dv_exc + 1e-6:
                        chosen = (ep, tof); eu += 1; break
                except Exception:
                    continue
        if chosen is None:
            chosen = (ep, 0.025)
        dep, tof = chosen; times.append(dep); tofs.append(tof); ep = dep + tof
    dv = [float(x) for x in (times + tofs + [float(p) for p in order])]
    f = kt.fitness(dv); return float(f[0]), kt.is_feasible(f), dv


def main(seed=0, wall_s=36 * 3600):
    _load(); kt = _G['kt']; n = _G['n']; rng = random.Random(seed * 13 + 1)
    log = lambda m: print(f"[s{seed}] {m}", flush=True)
    dv0 = json.load(open(BANK))[0]['decisionVector']
    border = [int(round(x)) for x in dv0[2 * (n - 1):]]
    obank = float(kt.fitness(dv0)[0])
    ctrl = walk(border)
    log(f"control: table-walk(bank)={ctrl if ctrl is None else f'{ctrl:.2f}'} vs official {obank:.2f} "
        f"(must be close ~932.53 for faithful eval)")
    if ctrl is None or abs(ctrl - obank) > 0.10 * obank:
        log("ABORT: table-walk evaluator off for large (table too coarse?) — refine epochs."); return
    cur = border; cur_mk = walk(cur); best_mk = cur_mk; T = 8.0; it = 0; t0 = time.time()
    while time.time() - t0 < wall_s:
        it += 1
        cand = perturb(cur, rng)
        if len(set(cand)) != n: continue
        mk = walk(cand)
        if mk is None: continue
        if mk < cur_mk or rng.random() < np.exp(-(mk - cur_mk) / max(T, 1e-3)):
            cur, cur_mk = cand, mk
        if mk < best_mk - 1e-6:
            best_mk = mk; dv = _G['_lastx']           # walk() already gave the OFFICIAL mk + dv
            log(f"NEW BEST official mk={best_mk:.2f} (bank {obank:.2f}, {best_mk-obank:+.2f}) it={it}")
            if best_mk < obank - 1e-3:
                shutil.copy(BANK, BANK + ".bak.tdtsp")
                json.dump([{"decisionVector": dv, "problem": "large"}], open(BANK, 'w'))
                rc = float(kt.fitness(json.load(open(BANK))[0]['decisionVector'])[0])
                log(f"BANKED large {rc:.2f} (was {obank:.2f}){' *** <424 RANK1 — ESCALATE' if rc<424 else ''}")
        T *= 0.99998
        if it % 5000 == 0:
            log(f"it={it} cur={cur_mk:.2f} best={best_mk:.2f} T={T:.2f} [{time.time()-t0:.0f}s]")
    log(f"done it={it} best_tablewalk={best_mk:.2f}")


if __name__ == "__main__":
    s = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    w = float(sys.argv[2]) if len(sys.argv) > 2 else 36 * 3600
    main(s, w)
