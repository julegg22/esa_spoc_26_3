"""E-735 probe #1b — Ch2-LARGE faithful reorder with the FINE LOCAL oracle (the dense table was mis-resolutioned;
the fine local cheap_first_tof scan reproduces the bank faithfully, verified on s0: 379.3d vs bank 380.4d).

Optimize ONE comp0 segment's internal order (endpoints fixed) from its bank entry epoch, minimizing finish time,
using a faithful earliest-arrival walk (per leg: cheap_first_tof over [t,t+W] at fine dep resolution, cached by
(i,j,t-bucket)). or-opt/2-opt restricted to cheap edges. Tests A-FORWARD: does faithful reorder beat the bank's
comp0 duration? Substantial cut => reorder lever REAL, rank-2 (beat 682) reachable.
Usage: CH2_SEG=0 CH2_SEED=11 CH2_MOVE=oropt python ch2_giant_comp0_finesearch.py [iters]"""
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
SEGI = int(os.environ.get("CH2_SEG", "0")); SEED = int(os.environ.get("CH2_SEED", "11"))
MOVE = os.environ.get("CH2_MOVE", "oropt"); TAG = os.environ.get("CH2_TAG", "f0")
W = float(os.environ.get("CH2_WAIT", "6.0")); DSTEP = float(os.environ.get("CH2_DSTEP", "0.02"))
ITERS = int(sys.argv[1]) if len(sys.argv) > 1 else 200000

# cheap candidate adjacency (which (i,j) cheap at some epoch) from the dense 1d table -> legal moves
_dz = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz"); _K = _dz["keys"]; _V = _dz["vals"]; _F = np.isfinite(_V)
ADJ = {}
for r, (i, j) in enumerate(_K):
    if _F[r].any():
        ADJ.setdefault(int(i), set()).add(int(j))
ft.cheap_first_tof(OPAR[0], OPAR[1], np.array([0.0, DAY]), MINTOF * DAY, 8.5 * DAY, DSTEP * DAY, THR, MAXREV)
_EC = {}                                                         # cache: (i,j,tbucket) -> (dep,tof,arr) or None


def earliest(i, j, t):
    key = (i, j, int(t * 5))                                     # 0.2d epoch bucket
    v = _EC.get(key, 0)
    if v != 0:
        return v
    deps = np.arange(t, t + W, DSTEP)
    tof = ft.cheap_first_tof(OPAR[i], OPAR[j], deps * DAY, MINTOF * DAY, 8.5 * DAY, DSTEP * DAY, THR, MAXREV)
    m = tof > 0
    if not m.any():
        _EC[key] = None; return None
    arr = deps[m] + tof[m] / DAY; k = int(np.argmin(arr))
    out = (float(deps[m][k]), float(tof[m][k] / DAY), float(arr[k])); _EC[key] = out
    return out


def walk(order, t_entry):
    t = t_entry
    for k in range(len(order) - 1):
        r = earliest(order[k], order[k + 1], t)
        if r is None:
            return None, k
        t = r[2]
    return t, len(order) - 1


def main():
    bank = json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]["decisionVector"]
    N = 1051; times = np.array(bank[:N - 1]); order = [int(c) for c in bank[2 * (N - 1):]]
    cset = set(ADJ.keys())
    # find comp0 contiguous segments
    segs = []; k = 0
    while k < N:
        if order[k] in cset:
            s = k
            while k < N and order[k] in cset:
                k += 1
            segs.append((order[s:k], float(times[s])))
        else:
            k += 1
    segs.sort(key=lambda x: -len(x[0]))
    cities, t_entry = segs[SEGI]
    t0 = time.time()
    base, nl = walk(cities, t_entry)
    if base is None:
        print(f"[E-735b][{TAG}] seg{SEGI} ({len(cities)}c) base STRANDS at leg {nl} from t={t_entry:.1f}", flush=True); return
    print(f"[E-735b][{TAG}] seg{SEGI}: {len(cities)}c base finish {base:.2f}d (dur {base-t_entry:.1f}d, "
          f"{(base-t_entry)/(len(cities)-1):.3f} d/leg) [{time.time()-t0:.0f}s]", flush=True)

    def cheap_ok(*edges):
        return all((a in ADJ and b in ADJ[a]) for (a, b) in edges)
    cur = list(cities); cur_fin = base; best = base; bestord = list(cities); rng = SEED; acc = 0; L_ = len(cur)
    pbest = f"{ROOT}/cache/ch2_giant_comp0_fine_{TAG}_seg{SEGI}.json"
    for it in range(ITERS):
        cand = None
        for _try in range(40):
            rng = (rng * 1103515245 + 12345) & 0x7fffffff
            if MOVE == "2opt":
                a = 1 + (rng % (L_ - 3)); b = a + 2 + ((rng >> 8) % (L_ - a - 2))
                if b < L_ and cheap_ok((cur[a - 1], cur[b - 1]), (cur[a], cur[b])):
                    cand = cur[:a] + cur[a:b][::-1] + cur[b:]; break
            else:
                ln = 1 + (rng % 3); a = 1 + (rng % (L_ - ln - 1))
                seg = cur[a:a + ln]; rest = cur[:a] + cur[a + ln:]
                b = 1 + ((rng >> 8) % (len(rest) - 1))
                if cheap_ok((cur[a - 1], cur[a + ln]), (rest[b - 1], seg[0]), (seg[-1], rest[b])):
                    cand = rest[:b] + seg + rest[b:]; break
        if cand is None:
            continue
        cf, cnl = walk(cand, t_entry)
        if cf is None:
            continue
        if cf < cur_fin - 1e-9 or (rng % 30 == 0 and cf < cur_fin + 0.3):
            cur, cur_fin = cand, cf; acc += 1
        if cf < best - 1e-9:
            best = cf; bestord = list(cand)
            json.dump({"cities": cand, "finish": cf, "t_entry": t_entry, "seg": SEGI}, open(pbest, "w"))
            print(f"[E-735b][{TAG}] seg{SEGI} it{it}: NEW BEST {cf:.2f}d (-{base-cf:.2f}d vs base, "
                  f"{(cf-t_entry)/(L_-1):.3f} d/leg) acc{acc} cache{len(_EC)} [{time.time()-t0:.0f}s]", flush=True)
        if it % 1000 == 0 and it:
            print(f"[E-735b][{TAG}] seg{SEGI} it{it}: cur {cur_fin:.2f} best {best:.2f} (-{base-best:.2f}d) "
                  f"acc{acc} cache{len(_EC)} [{time.time()-t0:.0f}s]", flush=True)
    print(f"[E-735b][{TAG}] seg{SEGI} DONE: base {base:.2f} -> best {best:.2f} (saved {base-best:.2f}d) "
          f"[{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
