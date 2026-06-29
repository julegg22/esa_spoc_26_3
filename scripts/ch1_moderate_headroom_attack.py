"""ATTACK on the false 'moderate-TOF feasibility wall' (E-757 reframed). Closure probe proved moderate
rows DO close (<<1e-6). The v2 fleet found 0 wins ONLY because it sorted lowest-bank-mass (small-cld,
cargo-limited at long dt). The real lever = HIGH-CARGO-HEADROOM circular pairs (large cld): moderate
TOF lowers capture ΔV and the long-dt cargo penalty (200-dt)*cld does NOT bind. Sort circular pairs by
cargo headroom @dt=40 DESC, run UDPModerate + REAL-idD official validation, report mass wins.
Usage: python ch1_moderate_headroom_attack.py [ntop=8] [restarts=8]"""
import sys, json, time
import numpy as np
import pygmo as pg
sys.path.insert(0, "scripts"); sys.path.insert(0, "src")
from ch1_moderate_forced_test import UDPModerate
from ch1_moderate_fleet_v2 import official_row_idD
from esa_spoc_26.ch1_trajectory import LtlTrajectory, V, HORIZON_DAYS
udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")


def main():
    ntop = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    restarts = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    bank = json.load(open("solutions/upload/trajectory.json"))[0]["decisionVector"]; N = len(bank) // 21
    md = np.array(udp.moon_data); ld = udp.ltl_dict
    cand = []
    for i in range(N):
        r = bank[i * 21:(i + 1) * 21]
        if r[0] < 0 or md[int(r[1]), 1] >= 0.05:
            continue
        idE, idL, idD = int(r[0]), int(r[1]), int(r[2])
        f = udp.fitness(r)[0]; cur = -f if f < 0 else 0
        cap40 = (HORIZON_DAYS - 40) * ld[(idL, idD)]
        cand.append((cap40 - cur, idE, idL, idD, cur))
    cand.sort(reverse=True)                                   # highest cargo headroom first
    print(f"[attack] {len(cand)} circular pairs; testing top {ntop} by cargo headroom, restarts={restarts}", flush=True)
    t0 = time.time(); wins = 0; tg = 0.0
    out = []
    for head, idE, idL, idD, cur in cand[:ntop]:
        prob = pg.problem(UDPModerate(udp, idE, idL))
        cma = pg.algorithm(pg.cmaes(gen=250, force_bounds=True, ftol=1e-7))
        lb, ub = prob.get_bounds(); lb = np.array(lb); ub = np.array(ub); rng = np.random.default_rng(idE * 7 + idL)
        best = None
        for _ in range(restarts):
            pop = pg.population(prob, 0)
            for _i in range(18): pop.push_back(lb + rng.random(8) * (ub - lb))
            pop = cma.evolve(pop)
            if best is None or float(pop.champion_f[0]) < best[0]: best = (float(pop.champion_f[0]), pop.champion_x)
        res = official_row_idD(idE, idL, idD, best[1])         # REAL-idD official validation (closes <1e-6)
        if res is not None:
            row, mass = res
            dtd = (row[19] + row[20]) * 4.348
            flag = ""
            if mass > cur + 5:
                wins += 1; tg += mass - cur; flag = f"<<MASS WIN +{mass-cur:.0f}"
                out.append({"idE": idE, "idL": idL, "idD": idD, "bank_mass": cur, "new_mass": mass,
                            "gain": mass - cur, "row": row})
            print(f"  (E={idE},L={idL},D={idD}) head={head:.0f} bank={cur:.0f} -> moderate VALID mass={mass:.0f} "
                  f"dt={dtd:.0f}d {flag} [{time.time()-t0:.0f}s]", flush=True)
        else:
            print(f"  (E={idE},L={idL},D={idD}) head={head:.0f} bank={cur:.0f} -> moderate row INVALID (didn't close) [{time.time()-t0:.0f}s]", flush=True)
    if out:
        json.dump(out, open("cache/ch1_moderate_headroom_wins.json", "w"))
    print(f"[attack] DONE {wins}/{ntop} MASS WINS, +{tg:.0f} kg [{time.time()-t0:.0f}s]. "
          f"{'LEVER REAL -> scale to all high-headroom pairs' if wins else 'no win even on top-headroom -> reconsider'}", flush=True)


if __name__ == "__main__":
    main()
