"""E-757 corrected fleet — moderate-TOF re-solve validated at the REAL delivery idD (fixes the idD=0
artifact in E-754's fleet). For each circular bank pair, force tof∈[35,60]d (UDPModerate), then build
the candidate row with the BANK's actual idD (not 0) and score with the official UDP. Keep only if
mass > bank_mass+1 at the REAL idD. Checkpointed, resumable, 3 shards. Assemble with ch1_stm_assemble.

Only worth running if E-757's correct-idD probe (br9kdqelx) shows moderate TOF lowers ΔV for circular
captures. Usage: python ch1_moderate_fleet_v2.py [restarts=12] [gen=250] [shard=0] [nshard=3]"""
import os, sys, json, time
import numpy as np
import pygmo as pg
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from ch1_moderate_forced_test import UDPModerate
from ch1_backshoot_ecc import UDPBackEcc, solve_departure_dv_ecc
from esa_spoc_26.ch1_trajectory import LtlTrajectory, V
ROOT = "/home/julian/Projects/esa_spoc_26_3"
udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")


def official_row_idD(idE, idL, idD, x):
    """Build the official row with the REAL idD (E-757 fix) and return (row, mass) if valid else None."""
    prob = UDPBackEcc(udp, idE, idL)
    S, dv2, t_arr, tof, D = prob._back(x)
    if D is None:
        return None
    d_state = [[D[0], D[1], D[2]], [D[3], D[4], D[5]]]
    dep = solve_departure_dv_ecc(d_state, prob.aE, prob.eE, prob.iE)
    if dep is None:
        return None
    posvel0, dv0, _ = dep
    row = [idE, idL, idD, float(t_arr - tof), *posvel0[0], *posvel0[1], *np.asarray(dv0).tolist(),
           0.0, 0.0, 0.0, *np.asarray(dv2).tolist(), float(tof), 0.0]
    f = udp.fitness(row)[0]
    return (row, -f) if f < 0 else None


def solve(idE, idL, restarts, gen):
    prob = pg.problem(UDPModerate(udp, idE, idL))
    cma = pg.algorithm(pg.cmaes(gen=gen, force_bounds=True, ftol=1e-7))
    lb, ub = prob.get_bounds(); lb = np.array(lb); ub = np.array(ub)
    rng = np.random.default_rng(idE * 7 + idL); best = None
    for _ in range(restarts):
        pop = pg.population(prob, 0)
        for _i in range(20):
            pop.push_back(lb + rng.random(8) * (ub - lb))
        pop = cma.evolve(pop)
        if best is None or float(pop.champion_f[0]) < best[0]:
            best = (float(pop.champion_f[0]), pop.champion_x)
    return best


def main():
    restarts = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    gen = int(sys.argv[2]) if len(sys.argv) > 2 else 250
    shard = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    nshard = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    CKPT = f"{ROOT}/cache/ch1_moderate_v2_fleet_w{shard}of{nshard}.json"
    md = np.array(udp.moon_data)
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    N = len(bank) // 21
    cand = []
    for i in range(N):
        r = bank[i * 21:(i + 1) * 21]
        if r[0] < 0 or md[int(r[1]), 1] >= 0.05:
            continue
        m = udp.fitness(r)[0]; bm = -m if m < 0 else 0.0
        cand.append({"idE": int(r[0]), "idL": int(r[1]), "idD": int(r[2]), "bank_mass": bm})
    cand.sort(key=lambda p: p["bank_mass"])                        # lowest-mass (most ΔV room) first
    cand = [p for i, p in enumerate(cand) if i % nshard == shard]
    print(f"[E-757v2] shard {shard}/{nshard}: {len(cand)} circular pairs; restarts={restarts} gen={gen} REAL-idD", flush=True)
    done = {}
    if os.path.exists(CKPT):
        done = {f"{d['idE']}_{d['idL']}": d for d in json.load(open(CKPT))}
        print(f"[RESUME] {len(done)} done", flush=True)
    t0 = time.time(); imp = 0; tg = 0.0
    for k, p in enumerate(cand):
        key = f"{p['idE']}_{p['idL']}"
        if key in done:
            if done[key].get("gain", 0) > 0:
                imp += 1; tg += done[key]["gain"]
            continue
        rec = {"idE": p["idE"], "idL": p["idL"], "idD": p["idD"], "bank_mass": p["bank_mass"], "gain": 0.0}
        b = solve(p["idE"], p["idL"], restarts, gen)
        if b is not None and b[0] < 1.3e4:
            res = official_row_idD(p["idE"], p["idL"], p["idD"], b[1])
            if res is not None:
                row, mass = res
                if mass > p["bank_mass"] + 1.0:
                    rec.update({"new_mass": mass, "gain": mass - p["bank_mass"], "row": row})
                    imp += 1; tg += mass - p["bank_mass"]
                    print(f"  [{k+1}/{len(cand)}] ({p['idE']},{p['idL']},{p['idD']}) bank={p['bank_mass']:.0f} -> "
                          f"m={mass:.0f} (+{mass-p['bank_mass']:.0f}) [{time.time()-t0:.0f}s]", flush=True)
        done[key] = rec
        json.dump(list(done.values()), open(CKPT, "w"))
        if (k + 1) % 5 == 0:
            print(f"  --- {imp} improved, +{tg:.0f} kg [{k+1}/{len(cand)}] [{time.time()-t0:.0f}s] ---", flush=True)
    print(f"[E-757v2] DONE shard {shard}: {imp} improved, +{tg:.0f} kg [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
