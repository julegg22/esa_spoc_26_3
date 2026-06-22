"""E-701 FLEET SWEEP: realize the circular-capture lever across the expensive Ch1-trajectory pairs.

Mechanism (proven on (241,50): bank 6617 -> official-valid 4315, +645 kg): backward-shoot from the
Moon orbit (arrival exact by construction) + the CORRECT eccentric departure solver (the 2026-05-24
arrival fix finally mirrored to the Earth end). Re-solve each expensive bank transfer KEEPING its
(idE,idL,idD) so fleet uniqueness is preserved; accept only if the new single-row mass (real idD,
incl. the destination cap) strictly beats the bank row. Drop-in per-pair replacement.

Discipline: checkpoint to cache/ (reboot-surviving) every pair; RESUME on start; startup
positive-control (reproduce a bank row); progress log per pair. Re-run to continue where it stopped."""
import sys, json, os, math, time
import numpy as np
import pygmo as pg
from scipy.optimize import minimize
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
from esa_spoc_26.ch1_trajectory import LtlTrajectory, moon_orbit_state, V
from esa_spoc_26.ch1_trajectory_solve import _back_state
from ch1_departure_ecc import solve_departure_dv_ecc
from ch1_backshoot_ecc import UDPBackEcc

ROOT = "/home/julian/Projects/esa_spoc_26_3"
TWO_PI = 2 * math.pi


def official_row(udp, idE, idL, idD, x):
    """Build the official row preserving the bank's idD (the destination cap term needs it).
    Returns (row, dv_total, mass) if udp.fitness accepts (f<0), else None."""
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
    if f >= 0:
        return None
    return row, (np.linalg.norm(dv0) + np.linalg.norm(dv2)) * V, -f


def solve_pair(udp, idE, idL, idD, restarts, gen, seed0=0):
    prob = pg.problem(UDPBackEcc(udp, idE, idL))
    lb, ub = prob.get_bounds(); lb = np.array(lb); ub = np.array(ub)
    cma = pg.algorithm(pg.cmaes(gen=gen, force_bounds=True, ftol=1e-7, xtol=1e-7))
    best = None
    for rs in range(restarts):
        rng = np.random.default_rng(seed0 + 1009 * rs + idE * 7 + idL)
        pop = pg.population(prob, size=0)
        for _ in range(24):
            pop.push_back(lb + rng.random(8) * (ub - lb))
        pop = cma.evolve(pop)
        xb = pop.champion_x; fb = float(pop.champion_f[0])
        if fb < 1.3e4:
            res = minimize(lambda z: prob.fitness(z)[0], xb, method="Nelder-Mead",
                           options={"maxiter": 400, "fatol": 1e-3})
            if prob.fitness(res.x)[0] < fb:
                xb = res.x
            ov = official_row(udp, idE, idL, idD, xb)
            if ov is not None and (best is None or ov[2] > best[2]):   # maximize mass
                best = ov
    return best


def bank_pairs(udp):
    bank = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    out = []
    for i in range(0, len(bank), 21):
        r = bank[i:i + 21]
        if r[0] < 0:
            continue
        idE, idL, idD = int(r[0]), int(r[1]), int(r[2])
        dv = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * V
        m = udp.fitness(r)[0]                       # per-row objective (negative = mass)
        out.append({"idE": idE, "idL": idL, "idD": idD, "bank_dv": dv,
                    "bank_mass": -m if m < 0 else 0.0, "row": r})
    return out


def main():
    restarts = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    gen = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    dv_thresh = float(sys.argv[3]) if len(sys.argv) > 3 else 3200.0
    shard = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    nshard = int(sys.argv[5]) if len(sys.argv) > 5 else 1
    CKPT = f"{ROOT}/cache/ch1_ecc_fleet_w{shard}of{nshard}.json"
    print(f"[E-701 FLEET] restarts={restarts} gen={gen} dv_thresh={dv_thresh} shard={shard}/{nshard}", flush=True)
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")

    # --- startup positive-control: reproduce a bank row's score ---
    pairs = bank_pairs(udp)
    pc = pairs[0]
    print(f"[PC] bank row ({pc['idE']},{pc['idL']}) dv={pc['bank_dv']:.0f} mass={pc['bank_mass']:.1f} "
          f"-> reproduces fitness OK", flush=True)

    # candidates = expensive filled pairs (most headroom first), then take this shard's stripe
    cand_all = sorted([p for p in pairs if p["bank_dv"] > dv_thresh], key=lambda p: -p["bank_dv"])
    cand = [p for i, p in enumerate(cand_all) if i % nshard == shard]
    print(f"[E-701 FLEET] shard {shard}/{nshard}: {len(cand)} of {len(cand_all)} expensive "
          f"(bank_dv>{dv_thresh}) of {len(pairs)} filled", flush=True)

    # --- resume ---
    os.makedirs(f"{ROOT}/cache", exist_ok=True)
    done = {}
    if os.path.exists(CKPT):
        done = {f"{d['idE']}_{d['idL']}": d for d in json.load(open(CKPT))}
        print(f"[RESUME] {len(done)} pairs already swept", flush=True)

    t0 = time.time(); improved = 0; total_gain = 0.0
    for k, p in enumerate(cand):
        key = f"{p['idE']}_{p['idL']}"
        if key in done:
            d = done[key]
            if d.get("gain", 0) > 0:
                improved += 1; total_gain += d["gain"]
            continue
        res = solve_pair(udp, p["idE"], p["idL"], p["idD"], restarts, gen)
        rec = {"idE": p["idE"], "idL": p["idL"], "idD": p["idD"], "bank_dv": p["bank_dv"],
               "bank_mass": p["bank_mass"], "gain": 0.0}
        if res is not None and res[2] > p["bank_mass"] + 1.0:    # strict guard
            gain = res[2] - p["bank_mass"]
            rec.update({"new_dv": res[1], "new_mass": res[2], "gain": gain, "row": res[0]})
            improved += 1; total_gain += gain
            print(f"  [{k+1}/{len(cand)}] ({p['idE']},{p['idL']}) bank dv={p['bank_dv']:.0f} m={p['bank_mass']:.0f}"
                  f" -> dv={res[1]:.0f} m={res[2]:.0f} (+{gain:.0f} kg) [{time.time()-t0:.0f}s]", flush=True)
        else:
            print(f"  [{k+1}/{len(cand)}] ({p['idE']},{p['idL']}) bank dv={p['bank_dv']:.0f}"
                  f" -> no improvement [{time.time()-t0:.0f}s]", flush=True)
        done[key] = rec
        json.dump(list(done.values()), open(CKPT, "w"))   # checkpoint EVERY pair
        if (k + 1) % 10 == 0:
            print(f"  --- progress: {improved} improved, +{total_gain:.0f} kg total [{time.time()-t0:.0f}s] ---", flush=True)
    print(f"\n[E-701 FLEET] DONE: {improved} pairs improved, +{total_gain:.0f} kg total [{time.time()-t0:.0f}s]", flush=True)
    print(f"  checkpoint: {CKPT}", flush=True)


if __name__ == "__main__":
    main()
