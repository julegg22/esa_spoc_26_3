"""PART 2 (comprehensive) — star-vs-connected verdict from the FULL cheap
shortlist built in Part 3. Classifies every node's cheap (dv<=100) neighbors by
bank segment. seg0/seg2/seg4 are the supposedly mutually-disconnected 150-smalls;
seg1/seg3/seg5 are comp0. If smalls have many cheap edges to OTHER smalls and to
comp0, the 'star / 5 mandatory bridges' topology is self-imposed.

Note: the shortlist is the UNION of cheap targets over 3 probe epochs (a node is
'cheap-connected' to j if reachable at >=1 probe epoch). This is exactly the
relation that defines cheap-graph components.
"""
import json
import numpy as np
from collections import defaultdict

SHORTLIST_PATH = '/tmp/ch2_large_p3_shortlist.json'
BANK = 'solutions/upload/large.json'
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

def main():
    sl = json.load(open(SHORTLIST_PATH))
    sl = {int(k): v for k, v in sl.items()}
    segs, seg_of = segments()
    small_segs = {0, 2, 4}
    comp0_segs = {1, 3, 5}

    # cross-tab: for nodes in each small, count cheap edges by target segment
    cross = defaultdict(lambda: defaultdict(int))   # src_seg -> tgt_seg -> cnt
    nodes_with_cross_small = defaultdict(int)        # src_seg -> #nodes that
                                                     # have >=1 edge to another small
    nodes_with_comp0 = defaultdict(int)
    for i, nbrs in sl.items():
        ss = seg_of[i]
        if ss not in small_segs:
            continue
        has_cross = False; has_comp0 = False
        for j in nbrs:
            ts = seg_of[j]
            cross[ss][ts] += 1
            if ts in small_segs and ts != ss:
                has_cross = True
            if ts in comp0_segs:
                has_comp0 = True
        if has_cross:
            nodes_with_cross_small[ss] += 1
        if has_comp0:
            nodes_with_comp0[ss] += 1

    print('=== PART 2 RESULTS (from full shortlist) ===')
    label = {0: 'smallA', 2: 'smallB', 4: 'smallC'}
    for ss in [0, 2, 4]:
        nseg = len(segs[ss])
        print(f'\nSource {label[ss]} (seg{ss}, {nseg} nodes):')
        for ts in range(6):
            tag = ('COMP0' if ts in comp0_segs else
                   ('SELF' if ts == ss else 'OTHER-SMALL'))
            print(f'  -> seg{ts} [{tag:11s}]: {cross[ss][ts]:5d} cheap edges')
        cs = sum(cross[ss][t] for t in small_segs if t != ss)
        c0 = sum(cross[ss][t] for t in comp0_segs)
        print(f'   nodes (of {nseg}) with >=1 edge to ANOTHER small: '
              f'{nodes_with_cross_small[ss]}')
        print(f'   nodes (of {nseg}) with >=1 edge to comp0: '
              f'{nodes_with_comp0[ss]}')
        print(f'   TOTAL cross-small cheap edges: {cs}; to comp0: {c0}')

    total_cross = sum(sum(cross[ss][t] for t in small_segs if t != ss)
                      for ss in small_segs)
    print(f'\nVERDICT: total cross-small cheap edges = {total_cross}')
    if total_cross == 0:
        print('  -> smalls truly mutually disconnected: STAR topology REAL.')
    else:
        print('  -> cheap edges DO cross between smalls: star is SELF-IMPOSED,'
              ' the 5 exceptions are NOT all mandatory bridges.')

if __name__ == '__main__':
    main()
