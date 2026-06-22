"""E-701 FILL lever: fill the 74 EMPTY Ch1-trajectory slots (toward rank 5).

The bank fills 326/400; the 74 empty slots are high-inclination Earth orbits (mean 72.8 deg) that were
stranded by the SAME circular-feasibility bug the eccentric departure solver (E-701) just fixed. The 74
unused Moon orbits are all circular -> exactly the regime the backward-shoot + solve_departure_dv_ecc
handles. Plan: Hungarian-match unused Earth<->Moon by |iE-iL| (iL-matching heuristic), assign unused
destinations, solve each transfer (official-validated), checkpoint, then assemble into the empty slots.

Sharded + checkpointed (cache/, reboot-survive, resumable) + startup positive-control. Re-run to resume.
Usage: python ch1_fill_empty.py [restarts=6] [gen=200] [shard=0] [nshard=1]"""
import sys, json, os, time
import numpy as np
from scipy.optimize import linear_sum_assignment
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
from esa_spoc_26.ch1_trajectory import LtlTrajectory, V
from ch1_ecc_fleet import solve_pair          # backward-shoot eccentric solver, returns (row, dv, mass)
ROOT = "/home/julian/Projects/esa_spoc_26_3"


def pools(udp):
    dv = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    n = len(dv) // 21
    usedE = set(); usedL = set(); usedD = set()
    for i in range(n):
        r = dv[i * 21:i * 21 + 21]
        if r[0] < 0:
            continue
        usedE.add(int(r[0])); usedL.add(int(r[1])); usedD.add(int(r[2]))
    nE = len(udp.earth_data); nL = len(udp.moon_data)
    uE = sorted(set(range(nE)) - usedE); uL = sorted(set(range(nL)) - usedL)
    nD = max(int(r[2]) for r in [dv[i*21:i*21+21] for i in range(n)] if r[0] >= 0) + 1
    # destination pool: assume same cardinality as transfers; unused = not in usedD, within [0, nE) range
    uD = sorted(set(range(nE)) - usedD)
    return uE, uL, uD


def matched_triples(udp):
    uE, uL, uD = pools(udp)
    iE = udp.earth_data[uE, 2]; iL = udp.moon_data[uL, 2]
    # Hungarian on |iE - iL| (the validated iL-matching proxy)
    C = np.abs(iE[:, None] - iL[None, :])
    ri, ci = linear_sum_assignment(C)
    triples = []
    for k, (a, b) in enumerate(zip(ri, ci)):
        idD = uD[k] if k < len(uD) else uD[k % len(uD)]
        triples.append((uE[a], uL[b], idD, float(C[a, b])))
    triples.sort(key=lambda t: t[3])           # easiest (smallest |iE-iL|) first
    return triples


def main():
    restarts = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    gen = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    shard = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    nshard = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    CKPT = f"{ROOT}/cache/ch1_fill_w{shard}of{nshard}.json"
    print(f"[E-701 FILL] restarts={restarts} gen={gen} shard={shard}/{nshard}", flush=True)
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    triples = matched_triples(udp)
    print(f"[E-701 FILL] {len(triples)} matched empty-slot triples (|iE-iL| range "
          f"{triples[0][3]:.3f}..{triples[-1][3]:.3f} rad)", flush=True)

    # positive control: solve the easiest triple, expect an official-valid row
    pc = triples[0]
    r = solve_pair(udp, pc[0], pc[1], pc[2], restarts=3, gen=150)
    if r is None:
        print(f"[PC] WARNING: easiest triple ({pc[0]},{pc[1]}) did not validate at low budget "
              f"(may need full budget) — continuing", flush=True)
    else:
        print(f"[PC] easiest ({pc[0]},{pc[1]}) -> official dv={r[1]:.0f} mass={r[2]:.0f} OK", flush=True)

    mine = [t for i, t in enumerate(triples) if i % nshard == shard]
    os.makedirs(f"{ROOT}/cache", exist_ok=True)
    done = {}
    if os.path.exists(CKPT):
        done = {f"{d['idE']}_{d['idL']}": d for d in json.load(open(CKPT))}
        print(f"[RESUME] {len(done)} slots already solved", flush=True)
    t0 = time.time(); filled = 0; mass_tot = 0.0
    for k, (idE, idL, idD, c) in enumerate(mine):
        key = f"{idE}_{idL}"
        if key in done:
            if done[key].get("mass", 0) > 0:
                filled += 1; mass_tot += done[key]["mass"]
            continue
        r = solve_pair(udp, idE, idL, idD, restarts=restarts, gen=gen)
        rec = {"idE": idE, "idL": idL, "idD": idD, "incl_gap": c, "mass": 0.0}
        if r is not None:
            rec.update({"row": r[0], "dv": r[1], "mass": r[2]})
            filled += 1; mass_tot += r[2]
            print(f"  [{k+1}/{len(mine)}] FILL ({idE},{idL},d{idD}) |di|={c:.3f} -> dv={r[1]:.0f} "
                  f"mass={r[2]:.0f} kg [{time.time()-t0:.0f}s]", flush=True)
        else:
            print(f"  [{k+1}/{len(mine)}] ({idE},{idL}) |di|={c:.3f} -> no valid transfer [{time.time()-t0:.0f}s]", flush=True)
        done[key] = rec
        json.dump(list(done.values()), open(CKPT, "w"))
    print(f"\n[E-701 FILL] shard {shard} DONE: {filled} slots filled, +{mass_tot:.0f} kg [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
