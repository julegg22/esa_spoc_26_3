"""PART 2 (deep cross-small probe) — definitively test whether ANY cheap
(dv<=100) edge crosses between the supposedly-disconnected smalls, using a
LONG window + fine grid (so we don't miss long-tof or multi-rev cheap links).

Take a few nodes from smallA(seg0), smallB(seg2), smallC(seg4). For each, at
several epochs, scan ALL nodes in the OTHER two smalls (and a comp0 sample) with
find_earliest_transfer at win=40, ns=240. Report any cheap cross edges found.
"""
import json, time
import numpy as np
from multiprocessing import Pool
from esa_spoc_26.ch2_kttsp import KTTSP
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer

INST = ('reference/SpOC4/Challenge 2 Keplerian Tomato Traveling Salesperson '
        'Problem/problems/hard.kttsp')
BANK = 'solutions/upload/large.json'
DV_THR = 100.0
WIN = 40.0
NS = 240
N = 1051

def segments():
    b = json.load(open(BANK))
    dv = np.array(b[0]['decisionVector'])
    perm = [int(round(v)) for v in dv[2*(N-1):]]
    bounds = [149, 416, 566, 807, 957]
    segs, start = [], 0
    for bk in bounds:
        segs.append(perm[start:bk+1]); start = bk + 1
    segs.append(perm[start:])
    seg_of = {}
    for s, seg in enumerate(segs):
        for node in seg:
            seg_of[node] = s
    return segs, seg_of

_kt = None
def _init():
    global _kt
    _kt = KTTSP(INST)

def probe(args):
    """src node, target list, epoch -> list of cheap (target,tof,dv)."""
    src, targets, epoch = args
    kt = _kt
    hits = []
    for j in targets:
        tof, dv = find_earliest_transfer(kt, src, j, epoch, DV_THR, WIN, NS)
        if tof is not None:
            hits.append((int(j), float(tof), float(dv)))
    return src, epoch, hits

def main():
    segs, seg_of = segments()
    kt = KTTSP(INST)
    small = {0: segs[0], 2: segs[2], 4: segs[4]}
    comp0_sample = list(segs[1][:50]) + list(segs[3][:50])
    rng = np.random.default_rng(99)
    # 3 src nodes from each small
    srcs = []
    for s in [0, 2, 4]:
        for p in rng.choice(small[s], size=3, replace=False):
            srcs.append((int(p), s))
    epochs = [0.0, 750.0, 1500.0, 2200.0]

    tasks = []
    for (src, s) in srcs:
        others = [t for t in (0, 2, 4) if t != s]
        tgt = list(small[others[0]]) + list(small[others[1]]) + comp0_sample
        for ep in epochs:
            tasks.append((src, tgt, ep))

    t0 = time.time()
    # record cross-small and to-comp0 hits per src
    from collections import defaultdict
    cross_small = defaultdict(list)   # src -> [(j, tof, dv, ep)]
    to_comp0 = defaultdict(list)
    src_seg = {s: sg for (s, sg) in srcs}
    comp0_set = set(comp0_sample)
    with Pool(4, initializer=_init) as pool:
        for src, ep, hits in pool.imap_unordered(probe, tasks):
            for (j, tof, dv) in hits:
                if j in comp0_set:
                    to_comp0[src].append((j, tof, dv, ep))
                else:
                    cross_small[src].append((j, tof, dv, ep))

    print('=== PART 2 DEEP CROSS-SMALL PROBE ===')
    print(f'win={WIN} ns={NS}, {len(srcs)} src nodes x {len(epochs)} epochs')
    seglabel = {0: 'smallA', 2: 'smallB', 4: 'smallC'}
    total_cross = 0
    for (src, s) in srcs:
        cs = cross_small[src]
        c0 = to_comp0[src]
        total_cross += len(cs)
        print(f'\nsrc {src} ({seglabel[s]}):')
        print(f'  cheap edges to OTHER smalls: {len(cs)}')
        for (j, tof, dv, ep) in sorted(cs)[:5]:
            print(f'     -> {j} ({seglabel[seg_of[j]]}) tof={tof:.2f} '
                  f'dv={dv:.0f} @ep{ep:.0f}')
        print(f'  cheap edges to comp0 (sample of 100): {len(c0)}')
        for (j, tof, dv, ep) in sorted(c0)[:3]:
            print(f'     -> {j} (comp0) tof={tof:.2f} dv={dv:.0f} @ep{ep:.0f}')
    print(f'\nTOTAL cross-small cheap edges (long window): {total_cross}')
    if total_cross == 0:
        print('VERDICT: even at win=40/ns=240, ZERO cheap edges cross between '
              'smalls -> STAR topology is REAL, 5 bridges structurally required.')
    else:
        print('VERDICT: cheap cross-small edges EXIST at longer tof -> star is '
              'self-imposed; some exceptions are free for makespan shortcuts.')
    json.dump({'total_cross': total_cross,
               'cross': {str(k): v for k, v in cross_small.items()},
               'to_comp0': {str(k): v for k, v in to_comp0.items()}},
              open('/tmp/ch2_large_part2_crossprobe.json', 'w'))
    print('time', f'{time.time()-t0:.0f}s')

if __name__ == '__main__':
    main()
