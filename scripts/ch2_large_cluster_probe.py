"""E-762 — Ch2-large cluster-structure probe (L3): does comp0 (the 601-node cheap giant) have
exploitable SUB-cluster structure (the HRI 'cluster substructures' hint)? Load the cheap adjacency,
take the largest component, run Louvain community detection on its undirected cheap graph, and report
sub-cluster sizes + intra/inter (coupling) edge ratios. Foundation for decompose->solve->couple.
Diagnostic; banks nothing."""
import sys
import collections
import numpy as np
import networkx as nx
sys.path.insert(0, "scripts")
import _prov
_prov.stamp(__file__)

d = np.load("cache/ch2_e533_large_adj.npz")
cheap = d["cheap"]; labels = d["labels"]
n = cheap.shape[0]

comp_sizes = collections.Counter(labels.tolist())
print(f"[E-762] n={n} cheap-edge components (sizes): {sorted(comp_sizes.values(), reverse=True)}", flush=True)
big = max(comp_sizes, key=comp_sizes.get)
nodes0 = [i for i in range(n) if labels[i] == big]
s0 = set(nodes0)
print(f"[E-762] comp0 (label {big}): {len(nodes0)} nodes", flush=True)

# undirected cheap graph on comp0 (edge if cheap either direction)
und = (cheap | cheap.T)
G = nx.Graph()
G.add_nodes_from(nodes0)
idx = np.array(nodes0)
sub = und[np.ix_(idx, idx)]
iu, ju = np.where(np.triu(sub, 1))
G.add_edges_from((int(idx[a]), int(idx[b])) for a, b in zip(iu, ju))
E = G.number_of_edges()
print(f"[E-762] comp0 cheap graph: {G.number_of_nodes()} nodes, {E} undirected edges, "
      f"avg deg {2*E/max(G.number_of_nodes(),1):.1f}", flush=True)

comms = nx.community.louvain_communities(G, seed=1, resolution=1.0)
sizes = sorted((len(c) for c in comms), reverse=True)
print(f"[E-762] Louvain: {len(comms)} sub-clusters; sizes top-20: {sizes[:20]}", flush=True)

node2c = {}
for ci, c in enumerate(comms):
    for u in c:
        node2c[u] = ci
intra = inter = 0
for u, v in G.edges():
    if node2c[u] == node2c[v]:
        intra += 1
    else:
        inter += 1
tot = intra + inter
print(f"[E-762] edges: intra-cluster={intra} inter-cluster(coupling)={inter} "
      f"intra-ratio={intra/max(tot,1):.2f}", flush=True)
try:
    mod = nx.community.modularity(G, comms)
    print(f"[E-762] modularity={mod:.3f}", flush=True)
except Exception:
    pass
print(f"[E-762] VERDICT: {len(comms)} sub-clusters, intra-ratio {intra/max(tot,1):.2f}. "
      f"Few large clusters + high intra-ratio + few coupling edges => decompose->solve->couple viable "
      f"(HRI hint). Many tiny clusters / low intra-ratio => comp0 is not cleanly decomposable.", flush=True)
