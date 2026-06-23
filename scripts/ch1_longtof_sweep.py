"""E-708 — targeted EXTENDED-TOF re-sweep of the worst high-ΔV trajectory transfers.
E-707 showed extended tof (up to ~130d) reduces ΔV most on the WORST (highest-ΔV) transfers
(E125 5135->4566 +191kg, E244 4806->4331 +175kg). Guarded: re-solve each ΔV>thr transfer with the
extended-tof backward-shoot solver; keep the new row ONLY if its ΔV is strictly lower (pure upside).
Sharded, checkpointed (cache/), resumable. After: assemble + re-run idd Hungarian (dt shifts the cap).
Usage: python ch1_longtof_sweep.py [restarts=5] [gen=180] [dv_thr=4400] [shard=0] [nshard=1] [tof_ub=30]"""
import sys, json, os, time
import numpy as np
import pykep as pk
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
from esa_spoc_26.ch1_trajectory import LtlTrajectory, V
from ch1_longtof_probe import solve_long
ROOT = "/home/julian/Projects/esa_spoc_26_3"


def main():
    restarts = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    gen = int(sys.argv[2]) if len(sys.argv) > 2 else 180
    dv_thr = float(sys.argv[3]) if len(sys.argv) > 3 else 4400.0
    shard = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    nshard = int(sys.argv[5]) if len(sys.argv) > 5 else 1
    tof_ub = float(sys.argv[6]) if len(sys.argv) > 6 else 30.0
    CKPT = f"{ROOT}/cache/ch1_longtof_w{shard}of{nshard}.json"
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    dv = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    n = len(dv) // 21
    cands = []
    for i in range(n):
        r = dv[i * 21:i * 21 + 21]
        if r[0] < 0:
            continue
        DV = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * V
        if DV > dv_thr:
            cands.append((DV, int(r[0]), int(r[1]), int(r[2])))
    cands.sort(reverse=True)                                   # worst first
    mine = [c for k, c in enumerate(cands) if k % nshard == shard]
    print(f"[E-708] {len(cands)} transfers ΔV>{dv_thr}; shard {shard}/{nshard} -> {len(mine)}; tof_ub={tof_ub} restarts={restarts}", flush=True)
    os.makedirs(f"{ROOT}/cache", exist_ok=True)
    done = {}
    if os.path.exists(CKPT):
        done = {f"{d['e']}_{d['l']}": d for d in json.load(open(CKPT))}
        print(f"[RESUME] {len(done)} done", flush=True)
    t0 = time.time(); improved = 0; dv_saved = 0.0
    for k, (oldDV, e, l, d) in enumerate(mine):
        key = f"{e}_{l}"
        if key in done:
            if done[key].get("better"):
                improved += 1; dv_saved += done[key]["dDV"]
            continue
        res = solve_long(udp, e, l, d, tof_ub, restarts=restarts, gen=gen)
        rec = {"e": e, "l": l, "d": d, "oldDV": oldDV, "better": False}
        if res is not None and res[1] < oldDV - 20:           # guard: strictly lower ΔV
            rec.update({"row": res[0], "newDV": res[1], "dDV": oldDV - res[1], "better": True})
            improved += 1; dv_saved += oldDV - res[1]
            om = np.exp(-oldDV / 311. / pk.G0) * 5000 - 500.; nm = np.exp(-res[1] / 311. / pk.G0) * 5000 - 500.
            print(f"  [{k+1}/{len(mine)}] E{e},L{l}: ΔV {oldDV:.0f}->{res[1]:.0f} (mass {om:.0f}->{nm:.0f}, +{nm-om:.0f}kg) [{time.time()-t0:.0f}s]", flush=True)
        else:
            nd = res[1] if res is not None else float('nan')
            print(f"  [{k+1}/{len(mine)}] E{e},L{l}: ΔV {oldDV:.0f}-> {nd:.0f} no-improve [{time.time()-t0:.0f}s]", flush=True)
        done[key] = rec
        json.dump(list(done.values()), open(CKPT, "w"))
    print(f"\n[E-708] shard {shard} DONE: {improved} improved, ΣΔV saved {dv_saved:.0f} m/s [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
