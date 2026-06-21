"""Positive control for _back_state (user: experiments may have errors). Forward-propagate a state,
then back-propagate the result; it MUST return the start (reversibility). Also: take the BANK's
(241,50) transfer, reconstruct its arrival via the official forward, back-shoot it, and check it
lands on the bank's departure. If either fails -> _back_state / backward-shooting machinery is buggy
-> all backward-shooting FAILs are invalid."""
import json, numpy as np, sys
sys.path.insert(0, "src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory, propagate, L
from esa_spoc_26.ch1_trajectory_solve import _back_state

udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")

# --- Test 1: pure reversibility on a generic Earth-ish state ---
print("=== Test 1: reversibility (forward tof then backward tof == identity) ===")
from esa_spoc_26.ch1_trajectory import earth_orbit_state
aE, eE, iE = udp.earth_data[241]
pv0 = earth_orbit_state(aE, eE, iE, 0.5, 0.3, 1.0)
dv0 = [0.4, 0.6, 0.1]
s_dep = [list(pv0[0]), [pv0[1][0] + dv0[0], pv0[1][1] + dv0[1], pv0[1][2] + dv0[2]]]
tof = 5.0 * 86400 / 3.7567696752e5
fwd = propagate(s_dep, 0.0, [[0, 0, 0], [0, 0, 0], [0, 0, 0]], [tof, 0.0])   # ballistic forward
if len(fwd) == 0:
    print("  forward impacted; pick another state")
else:
    back = _back_state(fwd[0], fwd[1], tof, tof)   # from arrival at t=tof, back by tof -> t=0
    if back is None:
        print("  _back_state returned None (impact backward)")
    else:
        perr = np.linalg.norm(np.array(back[:3]) - np.array(s_dep[0])) * L
        verr = np.linalg.norm(np.array(back[3:6]) - np.array(s_dep[1])) * (L / 3.7567696752e5)
        print(f"  position reconstruction error: {perr:.3e} m   velocity error: {verr:.3e} m/s")
        print(f"  -> {'REVERSIBLE (machinery OK)' if perr < 1000 else 'BROKEN (>1km error = BUG)'}")

# --- Test 2: reconstruct the bank's (241,50) arrival via official forward, then back-shoot it ---
print("\n=== Test 2: bank (241,50) forward-arrival, then back-shoot to departure ===")
bank = json.load(open("solutions/upload/trajectory.json"))[0]["decisionVector"]
for i in range(0, len(bank), 21):
    if int(bank[i]) == 241 and int(bank[i + 1]) == 50:
        r = bank[i:i + 21]; break
pvb = [list(r[4:7]), list(r[7:10])]
dv0b = r[10:13]; dv1b = r[13:16]; dv2b = r[16:19]; t0b, T1b, T2b = r[3], r[19], r[20]
# forward to the pre-dv2 arrival (apply dv0, coast T1, dv1, coast T2)
arr = propagate(pvb, t0b, [list(dv0b), list(dv1b), [0, 0, 0]], [T1b, T2b])
if len(arr) == 0:
    print("  bank forward impacted (unexpected)")
else:
    # back-shoot the arrival by (T1+T2); should land near the post-dv0 departure
    back = _back_state(arr[0], arr[1], t0b + T1b + T2b, T1b + T2b)
    dep_truth = [pvb[0], [pvb[1][0] + dv0b[0], pvb[1][1] + dv0b[1], pvb[1][2] + dv0b[2]]]
    perr = np.linalg.norm(np.array(back[:3]) - np.array(dep_truth[0])) * L
    print(f"  back-shot departure position error: {perr:.3e} m")
    print(f"  (note: a mid-burn dv1 was applied mid-arc, so exact match not expected; large error here")
    print(f"   would only flag a gross bug, not the dv1 discontinuity)")
