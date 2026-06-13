"""PART 1 — cheap-graph speed limit (parallel, 2-stage).
Deterministic random sample of nodes; over several epochs spanning [0,max_time]
scan ALL targets and record the MIN-TOF cheap (dv<=100) escape per (node,epoch).

Stage A: coarse grid over all 1050 targets to find cheaply-reachable targets +
rough min-tof. Stage B: fine local refine around the best few candidates.
Parallel across nodes (4 workers). Checkpoints to /tmp.
"""
import os, json, time
import numpy as np
from multiprocessing import Pool
from esa_spoc_26.ch2_kttsp import KTTSP
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer

INST = ('reference/SpOC4/Challenge 2 Keplerian Tomato Traveling Salesperson '
        'Problem/problems/hard.kttsp')
DV_THR = 100.0
WIN = 8.0          # tof window (d) -- catches fast + low multi-rev escapes
NS_COARSE = 64     # coarse grid step ~0.12 d
NS_FINE = 48       # fine local refine
N_NODES = 80
N_EPOCHS = 6
CKPT = '/tmp/ch2_large_part1.json'

_kt = None
def _init():
    global _kt
    _kt = KTTSP(INST)

def best_cheap_escape(node, epoch):
    """Min-tof cheap escape from `node` at `epoch` over all targets."""
    kt = _kt
    n = kt.n
    # Stage A: coarse scan all targets, record (tof,target) of cheap hits.
    coarse = []  # (tof, j)
    for j in range(n):
        if j == node:
            continue
        tof, dv = find_earliest_transfer(kt, node, j, epoch, DV_THR, WIN,
                                         NS_COARSE)
        if tof is not None:
            coarse.append((tof, j))
    if not coarse:
        return None, None
    coarse.sort()
    # Stage B: fine refine the few smallest-coarse-tof candidates.
    grid_step = (WIN - max(kt.min_tof, 0.05)) / NS_COARSE
    best_tof, best_j = coarse[0]
    for tof_c, j in coarse[:6]:
        lo = max(kt.min_tof, 0.05, tof_c - 2 * grid_step)
        hi = tof_c + 0.5 * grid_step
        grid = np.linspace(lo, hi, NS_FINE)
        for tof in grid:
            dv = kt.compute_transfer(node, j, float(epoch), float(tof))
            if dv <= DV_THR + 1e-6:
                if tof < best_tof:
                    best_tof, best_j = float(tof), j
                break
    return float(best_tof), int(best_j)

def work(args):
    node, epochs = args
    out = []
    for ep in epochs:
        tof, j = best_cheap_escape(node, ep)
        out.append({'epoch': float(ep), 'min_tof': tof, 'target': j})
    return {'node': int(node), 'epochs': out}

def main():
    kt = KTTSP(INST)
    n = kt.n
    rng = np.random.default_rng(12345)
    sample_nodes = sorted(rng.choice(n, size=N_NODES, replace=False).tolist())
    epochs = np.linspace(0.0, kt.max_time, N_EPOCHS).tolist()
    epochs = [min(e, kt.max_time - WIN - 1) for e in epochs]

    t0 = time.time()
    results = []
    tasks = [(node, epochs) for node in sample_nodes]
    with Pool(4, initializer=_init) as pool:
        for i, rec in enumerate(pool.imap_unordered(work, tasks)):
            results.append(rec)
            if (i + 1) % 4 == 0:
                json.dump({'sample_nodes': sample_nodes, 'epochs': epochs,
                           'results': results, 'done': i + 1,
                           'total': N_NODES}, open(CKPT, 'w'))
                print(f'  {i+1}/{N_NODES} nodes, '
                      f'{time.time()-t0:.0f}s', flush=True)
    json.dump({'sample_nodes': sample_nodes, 'epochs': epochs,
               'results': results, 'done': N_NODES, 'total': N_NODES},
              open(CKPT, 'w'))

    per_node_min, per_ne = [], []
    n_unreach_ne = 0
    n_unreach_node = 0
    for r in results:
        vals = [e['min_tof'] for e in r['epochs'] if e['min_tof'] is not None]
        if vals:
            per_node_min.append(min(vals))
        else:
            n_unreach_node += 1
        for e in r['epochs']:
            if e['min_tof'] is None:
                n_unreach_ne += 1
            else:
                per_ne.append(e['min_tof'])
    arr = np.array(per_node_min)
    arr_ne = np.array(per_ne)
    print('\n=== PART 1 RESULTS ===')
    print(f'nodes={len(results)} epochs={len(epochs)} win={WIN} '
          f'ns_coarse={NS_COARSE} ns_fine={NS_FINE}')
    print(f'fully-unreachable nodes (no cheap escape any epoch): '
          f'{n_unreach_node}')
    print(f'per-NODE best cheap escape tof (min over epochs), n={len(arr)}:')
    for p in [5, 10, 25, 50, 75, 90, 95]:
        print(f'  p{p:>2} = {np.percentile(arr, p):.4f} d')
    print(f'  mean={arr.mean():.4f} max={arr.max():.4f}')
    print(f'per (node,epoch) cheap escape tof, n={len(arr_ne)} '
          f'(unreachable n,e={n_unreach_ne}):')
    for p in [10, 50, 90]:
        print(f'  p{p:>2} = {np.percentile(arr_ne, p):.4f} d')
    print(f'frac nodes best-escape <=0.5d: {(arr<=0.5).mean():.2%}')
    print(f'frac nodes 0.5-1.0d:           {((arr>0.5)&(arr<=1.0)).mean():.2%}')
    print(f'frac nodes >1.0d:              {(arr>1.0).mean():.2%}')
    json.dump({'per_node_min': per_node_min,
               'pctile_node': {p: float(np.percentile(arr, p))
                               for p in [5,10,25,50,75,90,95]},
               'pctile_ne': {p: float(np.percentile(arr_ne, p))
                             for p in [10,50,90]},
               'n_unreach_node': n_unreach_node},
              open('/tmp/ch2_large_part1_summary.json', 'w'))
    print('done', f'{time.time()-t0:.0f}s')

if __name__ == '__main__':
    main()
