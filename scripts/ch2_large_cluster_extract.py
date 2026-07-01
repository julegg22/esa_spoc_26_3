"""E-763 — extract & persist the Ch2-large cluster decomposition for decompose->solve->couple.
Louvain on comp0's cheap graph (E-762) + the 3 satellites; dump node lists, sizes, and the
inter-cluster (coupling) edges to cache/ch2_large_clusters.json. Generator for that cache."""
import sys
import json
import collections
import numpy as np
import networkx as nx
sys.path.insert(0, "scripts")
import _prov
_prov.stamp(__file__)

d = np.load("cache/ch2_e533_large_adj.npz")
cheap = d["cheap"]; labels = d["labels"]; n = cheap.shape[0]
comp = collections.Counter(labels.tolist())
big = max(comp, key=comp.get)
sats = [lab for lab in comp if lab != big]
nodes0 = [i for i in range(n) if labels[i] == big]

und = (cheap | cheap.T)
idx = np.array(nodes0); sub = und[np.ix_(idx, idx)]
G = nx.Graph(); G.add_nodes_from(nodes0)
iu, ju = np.where(np.triu(sub, 1))
G.add_edges_from((int(idx[a]), int(idx[b])) for a, b in zip(iu, ju))
comms = sorted(nx.community.louvain_communities(G, seed=1), key=len, reverse=True)

clusters = {f"c{k}": sorted(int(x) for x in c) for k, c in enumerate(comms)}
for k, lab in enumerate(sats):
    clusters[f"sat{k}"] = sorted(i for i in range(n) if labels[i] == lab)

node2c = {u: cid for cid, c in clusters.items() for u in c}
coup = [(int(i), int(j)) for i in nodes0 for j in np.where(cheap[i])[0]
        if node2c.get(int(j)) and node2c[int(j)] != node2c[int(i)]]

out = {"clusters": clusters, "coupling_edges_comp0": coup,
       "sizes": {k: len(v) for k, v in clusters.items()}}
json.dump(out, open("cache/ch2_large_clusters.json", "w"))
print(f"[E-763] sizes: {out['sizes']}", flush=True)
print(f"[E-763] comp0 directed coupling edges: {len(coup)}", flush=True)
print("[E-763] saved cache/ch2_large_clusters.json", flush=True)
