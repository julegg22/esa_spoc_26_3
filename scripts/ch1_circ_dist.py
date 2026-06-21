import json, math, numpy as np, sys
sys.path.insert(0, 'src')
from esa_spoc_26.ch1_trajectory import LtlTrajectory
udp = LtlTrajectory('reference/SpOC4/Challenge 1 Luna Tomato Logistics/')
eL = udp.moon_data[:, 1]; iL = udp.moon_data[:, 2]; iE = udp.earth_data[:, 2]
Vunit = 3.84405e8 / 3.7567696752e5
bank = json.load(open('solutions/upload/trajectory.json'))[0]['decisionVector']
circ = []
for i in range(0, len(bank), 21):
    if bank[i] < 0:
        continue
    r = bank[i:i + 21]; e, l = int(r[0]), int(r[1])
    if eL[l] >= 0.1:
        continue
    dv = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * Vunit
    circ.append((dv, e, l, math.degrees(abs(iE[e] - iL[l]))))
circ = np.array(circ); d = circ[:, 0]
print('bank CIRCULAR captures n=%d: min %.0f p10 %.0f median %.0f p90 %.0f max %.0f'
      % (len(circ), d.min(), np.percentile(d, 10), np.median(d), np.percentile(d, 90), d.max()))
print('corr(circ dv,|iE-iL|)=%.3f  |iE-iL| median %.1f max %.0f'
      % (np.corrcoef(d, circ[:, 3])[0, 1], np.median(circ[:, 3]), circ[:, 3].max()))
print('circ dv<4200: %d  4200-4800: %d  >=4800: %d' % ((d < 4200).sum(), ((d >= 4200) & (d < 4800)).sum(), (d >= 4800).sum()))
mass = lambda dv: 5000 * math.exp(-dv / 311.0 / 9.80665) - 500
cur = sum(mass(x) for x in d); p10 = np.percentile(d, 10)
print('current circ mass %.0f; if ALL %d circ at p10 (%.0f) -> %.0f (+%.0f kg)'
      % (cur, len(d), p10, len(d) * mass(p10), len(d) * mass(p10) - cur))
