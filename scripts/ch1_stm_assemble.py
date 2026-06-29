"""E-738 — assemble STM-fleet per-pair improvements into the Ch1 trajectory bank. For each cache pair with
gain>0, locate the matching bank transfer by (idE,idL,idD), splice the improved trajectory params (positions
3:21, keeping the bank's identity triple 0:2), validate via the OFFICIAL udp.fitness (<0 = valid), and keep it
only if it raises that transfer's mass. Sequential + guarded; writes trajectory.json (+ .bak) only if total mass
strictly improves. NOT a submission.
Usage: python ch1_stm_assemble.py"""
import os, sys, json, glob, shutil
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from ch1_backshoot_ecc import LtlTrajectory
ROOT = "/home/julian/Projects/esa_spoc_26_3"
BANKF = f"{ROOT}/solutions/upload/trajectory.json"


def mass(udp, row):
    f = udp.fitness(row)[0]
    return -f if f < 0 else None                                  # None = invalid (fitness >= 0)


def main():
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    doc = json.load(open(BANKF)); bank = list(doc[0]["decisionVector"])
    N = len(bank) // 21
    # index bank transfers by identity triple
    idx = {}
    base_total = 0.0
    for i in range(N):
        r = bank[i * 21:(i + 1) * 21]
        if r[0] < 0:
            continue
        m = mass(udp, r)
        if m is not None:
            base_total += m
        idx[(int(r[0]), int(r[1]), int(r[2]))] = i
    print(f"[E-738] bank {N} transfers, total mass {base_total:.1f} kg", flush=True)

    # collect gain>0 cache rows
    cands = []
    globs = glob.glob(f"{ROOT}/cache/ch1_*fleet_w*of*.json") + glob.glob(f"{ROOT}/cache/ch1_vinf_resolve_wins*.json")
    for f in sorted(globs):
        for e in json.load(open(f)):
            if e.get("gain", 0) > 0 and "row" in e:
                cands.append(e)
    cands.sort(key=lambda e: -e["gain"])
    print(f"[E-738] {len(cands)} candidate improvements (gain>0)", flush=True)

    new = list(bank); applied = 0; gained = 0.0
    for e in cands:
        key = (int(e["idE"]), int(e["idL"]), int(e["idD"]))
        i = idx.get(key)
        if i is None:
            print(f"[E-738] pair {key} not in bank (skip)", flush=True); continue
        cur = new[i * 21:(i + 1) * 21]
        cur_m = mass(udp, cur) or 0.0
        trial = list(cur)
        trial[3:21] = list(e["row"])[3:21]                        # splice trajectory, keep bank identity 0:2
        tm = mass(udp, trial)
        if tm is None:
            print(f"[E-738] pair {key} improved row INVALID under official fitness (skip)", flush=True); continue
        if tm > cur_m + 0.5:
            new[i * 21:(i + 1) * 21] = trial; applied += 1; gained += (tm - cur_m)
    new_total = base_total + gained
    print(f"[E-738] applied {applied}/{len(cands)}; total {base_total:.1f} -> {new_total:.1f} kg "
          f"(+{gained:.1f}) [+{new_total-base_total:.1f}]", flush=True)

    if applied and gained > 1.0:
        shutil.copy(BANKF, f"{BANKF}.bak_stm_assemble")
        doc[0]["decisionVector"] = [float(x) for x in new]
        json.dump(doc, open(BANKF, "w"))
        # reload + reverify
        rb = json.load(open(BANKF))[0]["decisionVector"]; chk = 0.0
        for i in range(len(rb) // 21):
            r = rb[i * 21:(i + 1) * 21]
            if r[0] >= 0:
                m = mass(udp, r); chk += m if m else 0.0
        print(f"[E-738] GUARD-BANKED trajectory.json -> {chk:.1f} kg (reverified). NOT submitted.", flush=True)
    else:
        print(f"[E-738] no bankable gain", flush=True)


if __name__ == "__main__":
    main()
