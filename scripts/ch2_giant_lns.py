"""E-668: Ch2-large GIANT global re-interleaving via LNS (user-approved global completer, 2026-06-19).

The wall (E-667): the giant's cheap edges are TIME-ORDERED; greedy corner-paints, 2-opt from bank-913
is BASIN-LOCKED. 913→424 needs GLOBAL RE-INTERLEAVING of the hard-shell cities into early epochs.
LNS does exactly this: DESTROY k cities from the (complete, walkable) bank-913 order, then REPAIR by
re-inserting each at its cheapest TIME-FEASIBLE slot. Insertion slots are restricted to cheap-neighbor
positions (e533 adj) so inserts use cheap edges; this lets a hard-shell city land EARLY (interleaved),
which neither greedy (append-only) nor 2-opt (segment-local) can do. SA acceptance on the FAST faithful
giant retime (~5-15s, minimal-delay). Guard: dump any order whose faithful mk < bank-giant 913.

Validation gate: if LNS descends < 913 meaningfully → global re-interleaving WORKS → scale (more destroy
diversity, then full assembly → official mk vs 932.53/424). If it can't beat 913 → 913 is near-optimal
for this structure / needs the full GLKH. Usage: python ch2_giant_lns.py [wall_s] [nseed]
"""
import sys, json, time, random
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from scipy.sparse.csgraph import connected_components
from scipy.sparse import csr_matrix
from esa_spoc_26.ch2_kttsp import KTTSP
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
TOF_WINDOW = 40.0; N_STEPS = 2400; KREFINE = 4   # faithfully verify top-KREFINE table-scored slots
DELAY = np.array([0.0, 0.5, 1.0, 1.5])           # minimal waiting → fast giant retime
_C = {}


def leg(kt, a, b, t):
    key = (a, b, round(t, 2))
    v = _C.get(key)
    if v is None:
        tof, dv = find_earliest_transfer(kt, a, b, t, kt.dv_thr, TOF_WINDOW, N_STEPS)
        v = tof; _C[key] = v
    return v


def hop(kt, a, b, t):
    """min-arrival a->b departing >= t over DELAY; arrival or None."""
    best = None
    for d in DELAY:
        td = t + float(d)
        if td + 0.05 >= kt.max_time:
            break
        tof = leg(kt, a, b, td)
        if tof is not None and (best is None or td + tof < best):
            best = td + tof
    return best


def retime(kt, order, entry):
    """Faithful giant retime; returns (makespan, epoch_array) or (None, None)."""
    t = entry; ep = [entry]
    for k in range(len(order) - 1):
        arr = hop(kt, order[k], order[k + 1], t)
        if arr is None:
            return None, None
        t = arr; ep.append(t)
    return t - entry, ep


def tarr(tab, epochs, a, b, t):
    """Fast TABLE arrival a->b departing >= t (earliest future cheap bucket); inf if none."""
    row = tab.get((a, b))
    if row is None:
        return np.inf
    ne = len(epochs); bi0 = int(np.searchsorted(epochs, t))
    for bi in range(min(bi0, ne - 1), ne):
        tof = row[bi]
        if np.isfinite(tof):
            return max(t, float(epochs[bi])) + tof
    return np.inf


def repair(kt, order, ep, removed, neigh, rng, tab, epochs):
    """Re-insert each removed city at its cheapest TIME-FEASIBLE slot, SCORED BY THE FAST TABLE (no
    Lambert in the hot loop — the final faithful retime judges the true makespan/acceptance). Candidate
    slots restricted to cheap-neighbor positions (e533 adj) ⇒ cheap interleaving; a hard-shell city
    can thus land EARLY in the order. Approximate departure epochs `ep` corrected by the full retime."""
    rng.shuffle(removed)
    cur = order[:]; cep = ep[:]
    for u in removed:
        nb = neigh[u]
        cand_pos = [p for p in range(1, len(cur)) if cur[p - 1] in nb or cur[p] in nb]
        cand_pos.append(len(cur))
        scored = []  # (table_cost, pos)
        for p in cand_pos:
            a = cur[p - 1]; ea = cep[p - 1] if p - 1 < len(cep) else cep[-1]
            arr_au = tarr(tab, epochs, a, u, ea)
            if not np.isfinite(arr_au):
                continue
            if p < len(cur):
                arr_ub = tarr(tab, epochs, u, cur[p], arr_au)
                if not np.isfinite(arr_ub):
                    continue
                cost = arr_ub - (cep[p] if p < len(cep) else cep[-1])
            else:
                cost = arr_au - cep[-1]
            scored.append((cost, p))
        # FAITHFUL top-k refine: verify the few most-promising table slots with real Lambert
        best = None  # (faithful_cost, pos)
        for _, p in sorted(scored)[:KREFINE]:
            a = cur[p - 1]; ea = cep[p - 1] if p - 1 < len(cep) else cep[-1]
            arr_au = hop(kt, a, u, ea)
            if arr_au is None:
                continue
            if p < len(cur):
                arr_ub = hop(kt, u, cur[p], arr_au)
                if arr_ub is None:
                    continue
                fcost = arr_ub - (cep[p] if p < len(cep) else cep[-1])
            else:
                fcost = arr_au - cep[-1]
            if best is None or fcost < best[0]:
                best = (fcost, p)
        if best is None and scored:                   # faithful all failed → take best table slot
            best = (0.0, min(scored)[1])
        if best is None:                              # no cheap-window slot → append (retime judges)
            cur.append(u); cep = cep + [cep[-1]]
        else:
            p = best[1]; cur.insert(p, u); cep = cep[:p] + [cep[min(p, len(cep) - 1)]] + cep[p:]
    return cur


def main(seed=0, wall_s=20 * 3600, entry=0.0):
    kt = KTTSP(INST); n = kt.n
    adj = np.load('/tmp/ch2_e533_large_adj.npz')['cheap']
    nc, lab = connected_components(csr_matrix(adj), directed=False)
    gi = int(np.argmax(np.bincount(lab)))
    gnodes = [int(x) for x in np.where(lab == gi)[0]]; gset = set(gnodes); m = len(gnodes)
    neigh = {int(c): set(int(j) for j in np.where(adj[c])[0] if int(j) in gset) for c in gnodes}
    d = np.load('/tmp/ch2_large_epoch_table.npz', allow_pickle=True)
    epochs = d['epochs']; tab = {(int(a), int(b)): r for (a, b), r in zip(d['keys'], d['vals'])}
    log = lambda s: print(f"[s{seed}] {s}", flush=True)
    bank = json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]['decisionVector']
    bperm = [int(round(x)) for x in bank[2 * (n - 1):]]
    cur = [c for c in bperm if c in gset]
    cur_mk, ep = retime(kt, cur, entry)
    log(f"LNS seed=bank-giant mk={cur_mk:.1f} ({m} cities, 1.53 d/leg; target ~240 @0.4)")
    best, best_mk, best_ep = cur[:], cur_mk, ep
    rng = random.Random(seed * 91 + 7); T = 6.0; it = 0; t0 = time.time()
    KMAX = [8, 15, 25, 40][seed % 4]                  # destroy size per chain
    while time.time() - t0 < wall_s:
        it += 1
        k = rng.randint(5, KMAX)
        if rng.random() < 0.5:                        # contiguous destroy
            i = rng.randint(1, m - k - 1); rem = cur[i:i + k]; partial = cur[:i] + cur[i + k:]
            pep = ep[:i] + ep[i + k:]
        else:                                          # scattered destroy
            idx = sorted(rng.sample(range(1, m), k))
            remset = set(idx); rem = [cur[i] for i in idx]
            partial = [c for i, c in enumerate(cur) if i not in remset]
            pep = [e for i, e in enumerate(ep) if i not in remset]
        cand = repair(kt, partial, pep, rem, neigh, rng, tab, epochs)
        if len(set(cand)) != m:
            continue
        mk, cep = retime(kt, cand, entry)
        if mk is None:
            continue
        if mk < cur_mk or rng.random() < np.exp(-(mk - cur_mk) / max(T, 1e-3)):
            cur, cur_mk, ep = cand, mk, cep
        if mk < best_mk - 1e-3:
            best, best_mk, best_ep = cand[:], mk, cep
            log(f"NEW BEST giant={best_mk:.1f}d ({best_mk/(m-1):.3f} d/leg) k={k} it={it} [{time.time()-t0:.0f}s]")
            json.dump({'giant_order': best, 'faithful_mk': best_mk}, open(f'/tmp/ch2_lns_giant_s{seed}.json', 'w'))
        T *= 0.99997
        if it % 10 == 0:
            log(f"it={it} cur={cur_mk:.1f} best={best_mk:.1f} T={T:.2f} kmax={KMAX} [{time.time()-t0:.0f}s]")
    log(f"done it={it} best_giant={best_mk:.1f}")


if __name__ == "__main__":
    import multiprocessing as mp
    wall = float(sys.argv[1]) if len(sys.argv) > 1 else 20 * 3600
    ns = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    ps = [mp.Process(target=main, args=(s, wall, 0.0)) for s in range(ns)]
    for p in ps: p.start()
    for p in ps: p.join()
