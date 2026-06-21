import sys, json, time, numpy as np
sys.path.insert(0, "src")
import importlib.util
spec = importlib.util.spec_from_file_location("nlp", "scripts/ch1_nlp_pair.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
udp = m.LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
eL = udp.moon_data[:, 1]; L = 3.84405e8; Vunit = L / 3.7567696752e5
bank = json.load(open("solutions/upload/trajectory.json"))[0]["decisionVector"]
br = {}
for i in range(0, len(bank), 21):
    if bank[i] < 0:
        continue
    r = bank[i:i + 21]
    br[(int(r[0]), int(r[1]))] = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * Vunit
ecc = sorted([(v, k) for k, v in br.items() if eL[k[1]] >= 0.4 and v > 3500], reverse=True)[:4]
print("pair       bank     nlp    delta  beats  [t]", flush=True)
t0 = time.time()
for v, (e, l) in ecc:
    r = m.solve_pair(udp, e, l, restarts=3)
    if r is None:
        print(f"({e},{l}) {v:7.0f}    FAIL  [{time.time()-t0:.0f}s]", flush=True)
        continue
    tag = "YES" if v - r[0] > 50 else "no"
    print(f"({e},{l}) {v:7.0f} {r[0]:7.0f} {v-r[0]:+7.0f}  {tag}  [{time.time()-t0:.0f}s]", flush=True)
