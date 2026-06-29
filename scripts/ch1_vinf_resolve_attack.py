"""E-758 decisive attack: is the high arrival v_inf (mean 1242, capture-expensive) a BASIN MISS
recoverable by the eccentric backward-shoot (free TOF, heavy restarts), or BCP-coupled-optimal?
Take the highest-v_inf bank transfers, re-solve with UDPBackEcc (minimizes total ΔV, free TOF
2.2-52d), validate at the REAL idD (official udp.fitness<0), compare mass to bank. A win = the bank
had a stale high-v_inf transfer the current best solver beats -> scale a fleet (+tens of thousands kg).
Usage: python ch1_vinf_resolve_attack.py [ntop=8] [restarts=24]"""
import sys, json, time
import numpy as np
import pygmo as pg
from scipy.optimize import minimize
sys.path.insert(0, "scripts"); sys.path.insert(0, "src")
from ch1_backshoot_ecc import UDPBackEcc
from ch1_moderate_fleet_v2 import official_row_idD
from esa_spoc_26.ch1_trajectory import LtlTrajectory, V, MU_MOON
udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")


def main():
    ntop = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    restarts = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    offset = int(sys.argv[3]) if len(sys.argv) > 3 else 0   # shard: start at this rank in the v_inf-sorted list
    bank = json.load(open("solutions/upload/trajectory.json"))[0]["decisionVector"]; N = len(bank) // 21
    md = np.array(udp.moon_data)
    cand = []
    for i in range(N):
        r = bank[i * 21:(i + 1) * 21]
        if r[0] < 0:
            continue
        idE, idL, idD = int(r[0]), int(r[1]), int(r[2])
        a, e, inc = md[idL]; rp = a * (1 - e)
        dv2 = np.linalg.norm(r[16:19]) * V
        vp = dv2 + np.sqrt(MU_MOON / rp); vinf2 = vp ** 2 - 2 * MU_MOON / rp
        vinf = np.sqrt(vinf2) if vinf2 > 0 else 0
        f = udp.fitness(r)[0]; cur = -f if f < 0 else 0
        cand.append((vinf, idE, idL, idD, cur))
    cand.sort(reverse=True)                                   # highest v_inf first
    cand = cand[offset:offset + ntop]
    print(f"[E-758] re-solve v_inf-rank [{offset},{offset+ntop}) transfers, restarts={restarts} (free TOF 2.2-52d)", flush=True)
    t0 = time.time(); wins = 0; tg = 0.0; out = []
    OUTF = f"cache/ch1_vinf_resolve_wins_off{offset}.json"
    for vinf, idE, idL, idD, cur in cand:
        prob = UDPBackEcc(udp, idE, idL); pgp = pg.problem(prob)
        cma = pg.algorithm(pg.cmaes(gen=250, force_bounds=True, ftol=1e-7))
        lb, ub = prob.get_bounds(); lb = np.array(lb); ub = np.array(ub); rng = np.random.default_rng(idE * 13 + idL)
        best = None
        for _ in range(restarts):
            pop = pg.population(pgp, 0)
            for _i in range(20): pop.push_back(lb + rng.random(8) * (ub - lb))
            pop = cma.evolve(pop)
            xb = pop.champion_x; fb = float(pop.champion_f[0])
            if fb < 1.3e4:                                    # feasible regime -> polish
                res = minimize(lambda z: prob.fitness(z)[0], xb, method="Nelder-Mead",
                               options={"maxiter": 400, "fatol": 1e-3})
                if prob.fitness(res.x)[0] < fb: xb, fb = res.x, prob.fitness(res.x)[0]
            if best is None or fb < best[0]: best = (fb, xb)
        res = official_row_idD(idE, idL, idD, best[1])
        if res is not None:
            row, mass = res
            newvinf_dv2 = np.linalg.norm(row[16:19]) * V
            flag = f"<<WIN +{mass-cur:.0f}" if mass > cur + 5 else ""
            if mass > cur + 5:
                wins += 1; tg += mass - cur
                out.append({"idE": idE, "idL": idL, "idD": idD, "bank_mass": cur, "new_mass": mass,
                            "gain": mass - cur, "row": row})
                json.dump(out, open(OUTF, "w"))            # PERSIST after every win (survive kill)
            print(f"  (E={idE},L={idL},D={idD}) v_inf={vinf:.0f} bank_m={cur:.0f} -> resolve VALID mass={mass:.0f} "
                  f"(dv2 {newvinf_dv2:.0f}) {flag} [{time.time()-t0:.0f}s]", flush=True)
        else:
            print(f"  (E={idE},L={idL},D={idD}) v_inf={vinf:.0f} bank_m={cur:.0f} -> resolve INVALID [{time.time()-t0:.0f}s]", flush=True)
    if out:
        json.dump(out, open(OUTF, "w"))
    print(f"[E-758] DONE {wins}/{ntop} wins, +{tg:.0f} kg [{time.time()-t0:.0f}s]. "
          f"{'LEVER REAL -> v_inf was a basin miss; scale fleet' if wins else 'no win -> v_inf BCP-coupled-optimal, capture floored-in-context'}", flush=True)


if __name__ == "__main__":
    main()
