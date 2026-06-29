"""E-754 fleet — realize the moderate-TOF capture lever across the 250 circular pairs (the rank-3 trajectory
lever, CONFIRMED: forced-moderate pair (125,329) 4799->4179 m/s validated). For each circular Moon-orbit pair
(eL<0.05), solve with UDPModerate (tof FORCED to 35-60d -> slow arrival -> cheap capture), validate via official
udp.fitness<0, keep if mass beats the bank. Checkpointed per pair (resumable), 3 shards. Assemble with
ch1_stm_assemble.py (same row format).
Usage: python ch1_moderate_fleet.py [restarts=6] [gen=250] [shard=0] [nshard=3]"""
import os, sys, json, time
import numpy as np
import pygmo as pg
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from ch1_moderate_forced_test import UDPModerate
from ch1_backshoot_ecc import official_row
from esa_spoc_26.ch1_trajectory import LtlTrajectory, V
ROOT = "/home/julian/Projects/esa_spoc_26_3"
udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")


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
    restarts = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    gen = int(sys.argv[2]) if len(sys.argv) > 2 else 250
    shard = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    nshard = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    CKPT = f"{ROOT}/cache/ch1_moderate_fleet_w{shard}of{nshard}.json"
    md = np.array(udp.moon_data)
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    N = len(bank) // 21
    cand = []
    for i in range(N):
        r = bank[i * 21:(i + 1) * 21]
        if r[0] < 0 or md[int(r[1]), 1] >= 0.05:
            continue
        m = udp.fitness(r)[0]; bm = -m if m < 0 else 0.0
        tot = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * V
        cand.append({"idE": int(r[0]), "idL": int(r[1]), "idD": int(r[2]), "bank_mass": bm, "bank_tot": tot})
    cand.sort(key=lambda p: -p["bank_tot"])                       # worst (highest total dv) circular first
    cand = [p for i, p in enumerate(cand) if i % nshard == shard]
    print(f"[E-754f] shard {shard}/{nshard}: {len(cand)} circular pairs; restarts={restarts} gen={gen}", flush=True)
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
            res = official_row(udp, p["idE"], p["idL"], b[1])     # validates udp.fitness<0
            if isinstance(res, tuple) and len(res) == 3 and res[0] is not None:
                row, total, mass = res
                if mass > p["bank_mass"] + 1.0:
                    rec.update({"new_mass": mass, "gain": mass - p["bank_mass"], "row": row})
                    imp += 1; tg += mass - p["bank_mass"]
                    print(f"  [{k+1}/{len(cand)}] ({p['idE']},{p['idL']}) bank_m={p['bank_mass']:.0f} -> "
                          f"m={mass:.0f} (+{mass-p['bank_mass']:.0f} kg) tot={total:.0f} [{time.time()-t0:.0f}s]", flush=True)
        done[key] = rec
        json.dump(list(done.values()), open(CKPT, "w"))
        if (k + 1) % 5 == 0:
            print(f"  --- {imp} improved, +{tg:.0f} kg [{k+1}/{len(cand)}] [{time.time()-t0:.0f}s] ---", flush=True)
    print(f"[E-754f] DONE shard {shard}: {imp} improved, +{tg:.0f} kg [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
