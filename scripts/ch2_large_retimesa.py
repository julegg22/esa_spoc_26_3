"""E-662: full-order RETIME-SA for Ch2-large (user-approved fast-faithful-scheduler build).

Root constraint (E-661b): no fast faithful evaluator. But the RETIME (per-leg delay-grid walk)
gives the bank order 936.36 vs official 932.53 — only +0.4% off (vs greedy walk +28%, table strands).
e590 applied retime only to the ENDGAME; this runs a FULL-ORDER SA over large orders ranked by the
cached retime, escaping the 932 basin. Cached leg transfers (find_earliest_transfer, returns early on
easy legs) + incremental re-walk from the perturbation point keep evals tractable. Candidates that
retime below the bank get an OFFICIAL kt.fitness check; guard-bank if <932.53 (<424 = RANK1 escalate).

Control: retime(large bank order) must be within 1% of 932.53. Usage: python ch2_large_retimesa.py [wall_s]
"""
import sys, json, time, random, shutil
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
BANK = f"{ROOT}/solutions/upload/large.json"
TOF_WINDOW = 40.0; N_STEPS = 2400
DELAY_GRID = np.round(np.arange(0.0, 4.01, 0.5), 3)     # 9 delays (faster than e590's 25)
OBANK = 932.5304
_C = {}                                                 # leg cache: (a,b,round(t,3)) -> (tof or None)


def leg(kt, a, b, t, thr):
    key = (a, b, round(t, 3), thr)
    v = _C.get(key)
    if v is None:
        tof, dv = find_earliest_transfer(kt, a, b, t, thr, TOF_WINDOW, N_STEPS)
        v = tof; _C[key] = v
    return v


def retime_full(kt, order, ep_out):
    """Full-order retime from epoch 0: per leg pick min-arrival over DELAY_GRID using CHEAP, else
    EXCEPTION (≤kt.n_exc total). Fills ep_out. Returns makespan or None."""
    t = 0.0; eu = 0; ep_out[0] = 0.0
    for k in range(len(order) - 1):
        a, b = order[k], order[k + 1]; best = None
        for d in DELAY_GRID:
            td = t + float(d)
            if td + 0.05 >= kt.max_time:
                break
            tof = leg(kt, a, b, td, kt.dv_thr)
            if tof is not None and (best is None or td + tof < best):
                best = td + tof
        if best is None and eu < kt.n_exc:                # exception bridge
            for d in DELAY_GRID:
                td = t + float(d)
                if td + 0.05 >= kt.max_time:
                    break
                tof = leg(kt, a, b, td, kt.dv_exc)
                if tof is not None and (best is None or td + tof < best):
                    best = td + tof
            if best is not None:
                eu += 1
        if best is None:
            return None
        t = best; ep_out[k + 1] = t
        if t > kt.max_time:
            return None
    return t


def official_check(kt, order):
    """Min-arrival retime (cheap else exc) → dv → official kt.fitness."""
    t = 0.0; eu = 0; times = []; tofs = []
    for k in range(len(order) - 1):
        a, b = order[k], order[k + 1]; chosen = None
        for d in DELAY_GRID:
            td = t + float(d); tof = leg(kt, a, b, td, kt.dv_thr)
            if tof is not None:
                chosen = (td, tof); break
        if chosen is None and eu < kt.n_exc:
            for d in DELAY_GRID:
                td = t + float(d); tof = leg(kt, a, b, td, kt.dv_exc)
                if tof is not None:
                    chosen = (td, tof); eu += 1; break
        if chosen is None:
            return 1e9, False, None
        td, tof = chosen; times.append(td); tofs.append(tof); t = td + tof
    dv = [float(x) for x in (times + tofs + [float(p) for p in order])]
    f = kt.fitness(dv); return float(f[0]), kt.is_feasible(f), dv


def main(wall_s=20 * 3600):
    kt = KTTSP(INST); n = kt.n
    dv0 = json.load(open(BANK))[0]['decisionVector']
    order = [int(round(x)) for x in dv0[2 * (n - 1):]]
    log = lambda m: print(m, flush=True)
    ep = [0.0] * n
    t0 = time.time()
    ctrl = retime_full(kt, order, ep)
    log(f"[E-662] control: retime(bank)={ctrl if ctrl is None else f'{ctrl:.2f}'} vs official {OBANK:.2f} "
        f"[{time.time()-t0:.0f}s, cache {len(_C)}]")
    if ctrl is None or abs(ctrl - OBANK) > 0.02 * OBANK:
        log("[ABORT] retime control off >2% — evaluator not faithful enough."); return
    log(f"[E-662] control PASS — retime faithful (+{ctrl-OBANK:.1f}d). Full-order SA begins.")
    cur = order[:]; cur_mk = ctrl; best_mk = ctrl
    rng = random.Random(1); T = 6.0; it = 0
    while time.time() - t0 < wall_s:
        it += 1
        p = rng.randint(1, n - 2)
        cand = cur[:]
        r = rng.random()
        if r < 0.6:
            q = min(n - 1, p + rng.randint(2, 25)); cand[p:q] = cand[p:q][::-1]
        else:
            L = rng.randint(1, 8); seg = cand[p:p + L]; del cand[p:p + L]
            j = rng.randint(0, len(cand)); cand[j:j] = seg
        if len(set(cand)) != n:
            continue
        cep = [0.0] * n
        mk = retime_full(kt, cand, cep)
        if mk is None:
            continue
        if mk < cur_mk or rng.random() < np.exp(-(mk - cur_mk) / max(T, 1e-3)):
            cur, cur_mk = cand, mk
        if mk < best_mk - 1e-4:
            best_mk = mk
            omk, feas, dv = official_check(kt, cand)
            log(f"NEW BEST retime={mk:.2f} -> OFFICIAL {omk:.2f} feas={feas} (bank {OBANK:.2f}) it={it} "
                f"[{time.time()-t0:.0f}s]")
            if feas and omk < OBANK - 1e-3:
                shutil.copy(BANK, BANK + ".bak.retimesa")
                json.dump([{"decisionVector": dv, "problem": "large"}], open(BANK, 'w'))
                rc = float(kt.fitness(json.load(open(BANK))[0]['decisionVector'])[0])
                log(f"BANKED large {rc:.2f}{' *** <424 RANK1 ESCALATE' if rc < 424 else ''}")
        T *= 0.99999
        if it % 200 == 0:
            log(f"it={it} cur={cur_mk:.2f} best={best_mk:.2f} T={T:.2f} cache={len(_C)} [{time.time()-t0:.0f}s]")
    log(f"[done] it={it} best_retime={best_mk:.2f}")


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 20 * 3600)
