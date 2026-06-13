"""PART 2 — test the star-topology assumption.
The bank treats the cheap graph as: comp0 (seg1+seg3+seg5) + three mutually
DISCONNECTED 150-smalls (seg0, seg2, seg4), each small reachable from comp0
ONLY via an exception bridge. Test: do cheap (dv<=100) edges actually exist
BETWEEN the supposedly-disconnected smalls, or between a small and many comp0
nodes? If yes, the star is self-imposed -> 5 exceptions free for shortcuts.

For ~10 nodes drawn from the smalls, scan ALL 1050 targets at multiple epochs;
classify each cheap edge target by which segment it lands in.
Parallel across (node,epoch). Checkpoint to /tmp.
"""
import json, time
import numpy as np
from multiprocessing import Pool
from esa_spoc_26.ch2_kttsp import KTTSP
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer

INST = ('reference/SpOC4/Challenge 2 Keplerian Tomato Traveling Salesperson '
        'Problem/problems/hard.kttsp')
DV_THR = 100.0
WIN = 8.0
NS = 80           # ~0.10 d grid; enough to detect existence of a cheap edge
N_EPOCHS = 5
CKPT = '/tmp/ch2_large_part2.json'

# segment map from bank exception legs (see analysis)
BANK = 'solutions/upload/large.json'

_kt = None
_seg_of = None
def _init():
    global _kt
    _kt = KTTSP(INST)

def build_segments():
    b = json.load(open(BANK)); n = 1051
    dv = np.array(b[0]['decisionVector'])
    perm = [int(round(v)) for v in dv[2*(n-1):]]
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

def scan(args):
    """For one (node, epoch): return list of cheap targets with their tof+seg."""
    node, epoch, seg_of = args
    kt = _kt
    n = kt.n
    edges = []  # (target, tof, dv, seg)
    for j in range(n):
        if j == node:
            continue
        tof, dv = find_earliest_transfer(kt, node, j, epoch, DV_THR, WIN, NS)
        if tof is not None:
            edges.append((int(j), float(tof), float(dv), seg_of[j]))
    return {'node': int(node), 'epoch': float(epoch), 'edges': edges}

def main():
    segs, seg_of = build_segments()
    kt = KTTSP(INST)
    small_segs = [0, 2, 4]  # the three 150-node smalls
    rng = np.random.default_rng(777)
    # pick ~4 nodes from each small (12 total)
    test_nodes = []
    for s in small_segs:
        picks = rng.choice(segs[s], size=4, replace=False).tolist()
        test_nodes += [(int(p), s) for p in picks]
    epochs = np.linspace(0.0, kt.max_time, N_EPOCHS).tolist()
    epochs = [min(e, kt.max_time - WIN - 1) for e in epochs]

    tasks = [(node, ep, seg_of) for (node, _) in test_nodes for ep in epochs]
    t0 = time.time()
    results = []
    with Pool(4, initializer=_init) as pool:
        for i, rec in enumerate(pool.imap_unordered(scan, tasks)):
            rec['src_seg'] = seg_of[rec['node']]
            results.append(rec)
            if (i + 1) % 5 == 0:
                json.dump({'test_nodes': test_nodes, 'epochs': epochs,
                           'results': results}, open(CKPT, 'w'))
                print(f'  {i+1}/{len(tasks)} scans, {time.time()-t0:.0f}s',
                      flush=True)
    json.dump({'test_nodes': test_nodes, 'epochs': epochs,
               'results': results}, open(CKPT, 'w'))

    # --- analysis: for each src small, count cheap edges into each seg ---
    print('\n=== PART 2 RESULTS ===')
    small_label = {0: 'smallA(seg0)', 2: 'smallB(seg2)', 4: 'smallC(seg4)'}
    comp0_segs = {1, 3, 5}
    # aggregate per source small
    from collections import defaultdict
    agg = defaultdict(lambda: defaultdict(int))   # src_seg -> tgt_seg -> count
    agg_fast = defaultdict(lambda: defaultdict(int))  # tof<=1d cheap edges
    n_scans = defaultdict(int)
    for r in results:
        ss = r['src_seg']
        n_scans[ss] += 1
        for (j, tof, dv, ts) in r['edges']:
            agg[ss][ts] += 1
            if tof <= 1.0:
                agg_fast[ss][ts] += 1
    for ss in [0, 2, 4]:
        print(f'\nSource {small_label[ss]} ({n_scans[ss]} node-epoch scans):')
        for ts in range(6):
            cnt = agg[ss][ts]
            fast = agg_fast[ss][ts]
            tag = ('COMP0' if ts in comp0_segs else
                   ('SELF' if ts == ss else 'OTHER-SMALL'))
            print(f'  -> seg{ts} [{tag:11s}]: {cnt:5d} cheap edges '
                  f'({fast} with tof<=1d)')
        # decisive: cross-small + comp0 edges
        cross_small = sum(agg[ss][t] for t in small_segs if t != ss)
        to_comp0 = sum(agg[ss][t] for t in comp0_segs)
        print(f'   ==> cheap edges to OTHER smalls: {cross_small}; '
              f'to comp0: {to_comp0}')
    json.dump({'agg': {str(k): dict(v) for k, v in agg.items()},
               'agg_fast': {str(k): dict(v) for k, v in agg_fast.items()},
               'n_scans': dict(n_scans)},
              open('/tmp/ch2_large_part2_summary.json', 'w'))
    print('\ndone', f'{time.time()-t0:.0f}s')

if __name__ == '__main__':
    main()
