"""E-753 — Ch2-small joint order+epoch SA with the OFFICIAL kt.fitness (last open ch2 lever this window).
Small is floored at 112.996 (rank 6) by every prior method (GTSP capped E-746, order-search 114, DP). The
competitor's 101.65 (rank 1, -11d) implies a much better joint sequence+epoch solution. Prior searches optimized
order OR epochs largely separately; this does a basin-overarching SA on BOTH together (segment-reverse / or-opt /
epoch-jitter / tof-jitter), evaluated by the exact official kt.fitness (n=49 -> ~ms/eval, many iters), with
worse-accepting (SA temperature) + restarts to escape the local basin. Guard-banks any feasible <112.996.
Usage: python ch2_small_joint_sa.py [iters=200000]"""
import sys, json, math, time, shutil
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
kt = KTTSP(f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling Salesperson Problem/problems/easy.kttsp")
N = 49


def score(dv):
    f = kt.fitness(dv)
    # CORRECT feasibility (kt.is_feasible): perm==0, all transfers ok (f[2]==0), ALL chronological (f[3]==0),
    # exc within budget (f[4]<=0). NOTE: f[2]/f[3] are EQUALITIES — negative = infeasible (the 0.039 exploit bug).
    feas = (abs(f[1]) <= 1e-6 and abs(f[2]) <= 1e-6 and abs(f[3]) <= 1e-6 and f[4] <= 1e-6)
    return float(f[0]), feas


def main():
    iters = int(sys.argv[1]) if len(sys.argv) > 1 else 200000
    bank = json.load(open(f"{ROOT}/solutions/upload/small.json"))[0]["decisionVector"]
    t = np.array(bank[:N - 1]); tof = np.array(bank[N - 1:2 * (N - 1)]); order = [int(c) for c in bank[2 * (N - 1):]]
    cur_mk, feas = score(list(t) + list(tof) + [float(c) for c in order])
    print(f"[E-753] bank {cur_mk:.3f}d feas={feas} (target <112.996; rank1 101.65)", flush=True)
    best_mk = cur_mk; best = (t.copy(), tof.copy(), list(order))
    rng = np.random.RandomState(7); t0 = time.time(); nacc = 0; T = 2.0
    ct, ctf, corder = t.copy(), tof.copy(), list(order)
    cmk = cur_mk
    for it in range(iters):
        nt, ntf, no = ct.copy(), ctf.copy(), list(corder)
        m = rng.randint(4)
        if m == 0:                                              # segment reverse (interior)
            a, b = sorted(rng.randint(1, N - 1, 2))
            no[a:b + 1] = no[a:b + 1][::-1]
        elif m == 1:                                            # or-opt relocate
            i = rng.randint(1, N - 1); c = no.pop(i); j = rng.randint(1, N - 1); no.insert(j, c)
        elif m == 2:                                            # epoch jitter (a leg's start time)
            k = rng.randint(N - 1); nt[k] = max(0.0, nt[k] + rng.normal(0, 0.5))
        else:                                                  # tof jitter
            k = rng.randint(N - 1); ntf[k] = max(0.01, ntf[k] + rng.normal(0, 0.3))
        mk, fe = score(list(nt) + list(ntf) + [float(c) for c in no])
        if fe and (mk < cmk or rng.random() < math.exp(-(mk - cmk) / max(T, 1e-3))):
            ct, ctf, corder, cmk = nt, ntf, no, mk; nacc += 1
            if mk < best_mk:
                best_mk = mk; best = (nt.copy(), ntf.copy(), list(no))
                if mk < cur_mk - 0.01:
                    print(f"[E-753] it{it}: NEW BEST {mk:.3f}d (acc{nacc}) [{time.time()-t0:.0f}s]", flush=True)
        T *= 0.99998                                            # slow cool
        if it % 20000 == 0:
            print(f"[E-753] it{it}: cur {cmk:.3f} best {best_mk:.3f} T={T:.3f} acc={nacc} [{time.time()-t0:.0f}s]", flush=True)
            if T < 0.05:                                        # reheat (basin-overarching restarts)
                T = 1.5; ct, ctf, corder, cmk = best[0].copy(), best[1].copy(), list(best[2]), best_mk
    print(f"[E-753] DONE best {best_mk:.3f}d (bank 112.996) [{time.time()-t0:.0f}s]", flush=True)
    if best_mk < 112.996 - 0.01:
        bt, btf, bo = best
        dv = list(bt) + list(btf) + [float(c) for c in bo]
        mk, fe = score(dv)
        if fe:
            shutil.copy(f"{ROOT}/solutions/upload/small.json", f"{ROOT}/solutions/upload/small.json.bak_jointsa")
            doc = json.load(open(f"{ROOT}/solutions/upload/small.json")); doc[0]["decisionVector"] = [float(x) for x in dv]
            json.dump(doc, open(f"{ROOT}/solutions/upload/small.json", "w"))
            print(f"[E-753] *** GUARD-BANKED small -> {mk:.3f}d (was 112.996, RANK GAIN) -> ESCALATE. NOT submitted.", flush=True)


if __name__ == "__main__":
    main()
