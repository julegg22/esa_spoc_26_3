"""E-735 probe #1 — Ch2-LARGE: the medium rank-1 machinery (faithful earliest-arrival walk + or-opt/2-opt order
search restricted to cheap edges, seeded from the COMPLETE existing tour) applied to comp0 (the 601-node giant
that holds ~876d of the 932d makespan). Tests A-FORWARD: is the 932 'reorder trap' a fixed-epoch-matrix artifact?

comp0-only canonical sub-problem: traverse all 601 comp0 cities starting at epoch T0, minimize finish time, using
the FAITHFUL fine-tof windows (cache/ch2_giant_faithful_windows.npz). Earliest-arrival walk is optimal for a fixed
order (waiting allowed + monotone arrival, E-589). Seed = the bank's own comp0 traversal order (already complete).
If or-opt/2-opt descends the finish time -> reorder lever is real (the trap was the method's, not reorder's).
Usage: CH2_T0=0 CH2_SEED=11 CH2_MOVE=oropt python ch2_giant_comp0_ordersearch.py [iters]"""
import os, sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
import ch2_fast_transfer as ft
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST)
OPAR = kt.opar.astype(np.float64); THR = kt.dv_thr; MAXREV = kt.max_revs; MINTOF = kt.min_tof; DAY = 86400.0
T0 = float(os.environ.get("CH2_T0", "0"))
SEED = int(os.environ.get("CH2_SEED", "11"))
MOVE = os.environ.get("CH2_MOVE", "oropt")
TAG = os.environ.get("CH2_TAG", "c0")
TOF_HI = float(os.environ.get("CH2_TOFHI", "8.5"))
ITERS = int(sys.argv[1]) if len(sys.argv) > 1 else 2_000_000
# lazy-build deps grid (matches the full precompute resolution)
_LD = np.arange(0.0, 960.0, 0.5); _LD_SEC = _LD * DAY

EDGE = {}                                                        # (i,j) -> (deps, smin_arr, sdep, stof) suffix-min
# warm cache ONLY from the full-coverage table (full epoch + tof); the old short-tof npz is epoch-incomplete
# (deps<=460) and would block the lazy rebuild -> strand. Missing/uncovered edges are lazily built at full range.
_p = f"{ROOT}/cache/ch2_giant_faithful_full.npz"
if os.path.exists(_p):
    Wd = np.load(_p, allow_pickle=True)["windows"].item()
    for (i, j), (deps, tofs) in Wd.items():
        d = np.asarray(deps, dtype=float); tf = np.asarray(tofs, dtype=float)
        if not len(d):
            continue
        o = np.argsort(d); d = d[o]; tf = tf[o]; arr = d + tf
        sidx = np.empty(len(d), dtype=np.int64); sidx[-1] = len(d) - 1
        for q in range(len(d) - 2, -1, -1):
            sidx[q] = q if arr[q] <= arr[sidx[q + 1]] else sidx[q + 1]
        EDGE[(i, j)] = (d, arr[sidx], d[sidx], tf[sidx])
    print(f"[E-735][{TAG}] warm cache full-table: {len(EDGE)} edges", flush=True)
# cheap candidate adjacency (which (i,j) are cheap at SOME epoch) from the dense 1d table -> legal moves
_dz = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz"); _K = _dz["keys"]; _V = _dz["vals"]; _F = np.isfinite(_V)
ADJ = {}
for r, (i, j) in enumerate(_K):
    if _F[r].any():
        ADJ.setdefault(int(i), set()).add(int(j))
CITIES = sorted(ADJ.keys())
NC = len(CITIES)
_warm = ft.cheap_first_tof(OPAR[0], OPAR[1], _LD_SEC[:4], MINTOF * DAY, TOF_HI * DAY, 0.04 * DAY, THR, MAXREV)
_LAZY = [0]


def _ew(i, j):
    """suffix-min earliest-arrival for edge (i,j); lazily build + cache via cheap_first_tof if absent."""
    e = EDGE.get((i, j))
    if e is not None:
        return e
    tof = ft.cheap_first_tof(OPAR[i], OPAR[j], _LD_SEC, MINTOF * DAY, TOF_HI * DAY, 0.04 * DAY, THR, MAXREV)
    m = tof > 0
    if not m.any():
        EDGE[(i, j)] = None; return None
    d = _LD[m]; tf = tof[m] / DAY; arr = d + tf
    sidx = np.empty(len(d), dtype=np.int64); sidx[-1] = len(d) - 1
    for q in range(len(d) - 2, -1, -1):
        sidx[q] = q if arr[q] <= arr[sidx[q + 1]] else sidx[q + 1]
    out = (d, arr[sidx], d[sidx], tf[sidx]); EDGE[(i, j)] = out; _LAZY[0] += 1
    return out


print(f"[E-735][{TAG}] {len(EDGE)} warm edges, {NC} cheap-candidate cities, T0={T0}, lazy fallback ON", flush=True)


def walk(order, t0=T0):
    """faithful earliest-arrival walk; returns (finish_time, n_legs_done, times, tofs). strands -> n<len-1."""
    t = t0; nl = len(order) - 1
    times = np.empty(nl); tofs = np.empty(nl)
    for k in range(nl):
        e = _ew(order[k], order[k + 1])
        if e is None:
            return float("inf"), k, None, None
        d, smin, sdep, stof = e
        q = np.searchsorted(d, t)
        if q >= len(smin):
            return float("inf"), k, None, None
        times[k] = sdep[q]; tofs[k] = stof[q]; t = float(smin[q])
    return t, nl, times, tofs


def _segments(bank, N=1051):
    """maximal contiguous runs of comp0 cities in the bank tour, with each run's entry departure epoch."""
    times = np.array(bank[:N - 1]); order = [int(c) for c in bank[2 * (N - 1):]]
    cset = set(CITIES); segs = []; k = 0
    while k < N:
        if order[k] in cset:
            s = k
            while k < N and order[k] in cset:
                k += 1
            cities = order[s:k]
            t_entry = float(times[s]) if s < N - 1 else 0.0     # bank departure epoch of first city in the run
            segs.append((cities, t_entry))
        else:
            k += 1
    return segs


def _opt_segment(cities, t_entry, label):
    """faithful or-opt/2-opt on a comp0 segment (endpoints fixed), walked from t_entry. Returns best finish."""
    base, nl, _, _ = walk(cities, t0=t_entry)
    if not np.isfinite(base):
        print(f"[E-735][{TAG}] seg {label} ({len(cities)}c) baseline STRANDS at leg {nl} from t={t_entry:.1f} "
              f"-> skip (table still filling?)", flush=True)
        return None, None
    dur0 = base - t_entry
    print(f"[E-735][{TAG}] seg {label}: {len(cities)}c base finish {base:.2f}d (dur {dur0:.2f}d, "
          f"{dur0/max(len(cities)-1,1):.3f} d/leg) lazy={_LAZY[0]}", flush=True)

    def cheap_ok(*edges):
        return all((a in ADJ and b in ADJ[a]) for (a, b) in edges)
    cur = list(cities); cur_fin = base; best = base; bestord = list(cities); rng = SEED + len(cities); acc = 0; t0 = time.time()
    pbest = f"{ROOT}/cache/ch2_giant_comp0_best_{TAG}_{label}.json"
    L_ = len(cur)
    for it in range(ITERS):
        if L_ < 5:
            break
        cand = None
        for _try in range(40):
            rng = (rng * 1103515245 + 12345) & 0x7fffffff
            if MOVE == "2opt":
                a = 1 + (rng % (L_ - 3)); b = a + 2 + ((rng >> 8) % (L_ - a - 2))
                if b >= L_:
                    continue
                if cheap_ok((cur[a - 1], cur[b - 1]), (cur[a], cur[b])):
                    cand = cur[:a] + cur[a:b][::-1] + cur[b:]; break
            else:
                ln = 1 + (rng % 3); a = 1 + (rng % (L_ - ln - 1))
                seg = cur[a:a + ln]; rest = cur[:a] + cur[a + ln:]
                b = 1 + ((rng >> 8) % (len(rest) - 1))
                if cheap_ok((cur[a - 1], cur[a + ln]), (rest[b - 1], seg[0]), (seg[-1], rest[b])):
                    cand = rest[:b] + seg + rest[b:]; break
        if cand is None:
            continue
        cf, cnl, _, _ = walk(cand, t0=t_entry)
        if cnl < len(cand) - 1:
            continue
        if cf < cur_fin - 1e-9 or (rng % 30 == 0 and cf < cur_fin + 0.5):
            cur, cur_fin = cand, cf; acc += 1
        if cf < best - 1e-9:
            best = cf; bestord = list(cand)
            json.dump({"cities": cand, "finish": cf, "t_entry": t_entry}, open(pbest, "w"))
            print(f"[E-735][{TAG}] seg {label} it{it}: NEW BEST finish {cf:.2f}d (dur {cf-t_entry:.2f}, "
                  f"-{base-cf:.2f}d vs base) [{time.time()-t0:.0f}s]", flush=True)
        if it % 5000 == 0 and it:
            print(f"[E-735][{TAG}] seg {label} it{it}: cur {cur_fin:.2f} best {best:.2f} "
                  f"(base {base:.2f}, -{base-best:.2f}d) acc {acc} [{time.time()-t0:.0f}s]", flush=True)
    return best, bestord


def main():
    bank = json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]["decisionVector"]
    segs = _segments(bank)
    segs_sorted = sorted(enumerate(segs), key=lambda x: -len(x[1][0]))
    print(f"[E-735][{TAG}] bank comp0 segments: {[(len(c),round(t,1)) for c,t in segs]} "
          f"(total {sum(len(c) for c,_ in segs)} cities)", flush=True)
    total_saved = 0.0
    for idx, (cities, t_entry) in segs_sorted:
        if len(cities) < 5:
            continue
        best, _ = _opt_segment(cities, t_entry, f"s{idx}")
        if best is not None:
            base, _, _, _ = walk(cities, t0=t_entry)
            total_saved += (base - best)
            print(f"[E-735][{TAG}] seg s{idx} DONE: saved {base-best:.2f}d (cumulative {total_saved:.2f}d)", flush=True)
    print(f"[E-735][{TAG}] ALL SEGMENTS DONE: total comp0 duration saved {total_saved:.2f}d "
          f"(bank 932.53 -> ~{932.53-total_saved:.1f}d if it cascades; beat r2=682 needs -250d)", flush=True)


if __name__ == "__main__":
    main()
