"""E-721 — merge the recovered focus edges (dense1d_v2) into the original table -> dense1d_aug.

The original dense1d (950 epochs, 0-950) inherited the 8-probe false negatives for the focus (stranded)
cities. dense1d_v2 has the PROPERLY-rescanned focus in/out edges (230 epochs, 0-460). Produce a unified
augmented table on the v2 grid (0-460, the rank-1 window): every original edge resampled to the 0-460 grid
by nearest-epoch lookup, then v2's focus edges overlaid (they win where both exist). Output schema matches
the beam's loader (epochs/keys/vals). Usage: python ch2_giant_merge_aug.py"""
import numpy as np
ROOT = "/home/julian/Projects/esa_spoc_26_3"
o = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
v2 = np.load(f"{ROOT}/cache/ch2_giant_dense1d_v2.npz")
OEP = o["epochs"]; OKEYS = o["keys"]; OVALS = o["vals"]
NEP = v2["epochs"]; VKEYS = v2["keys"]; VVALS = v2["vals"]
print(f"original: {len(OKEYS)} edges x{len(OEP)}ep(0-{OEP.max():.0f}) | v2 focus: {len(VKEYS)} edges x{len(NEP)}ep(0-{NEP.max():.0f})")
# map each new-grid epoch to nearest original epoch index (for resampling original edges to 0-460 grid)
idx = np.searchsorted(OEP, NEP).clip(0, len(OEP) - 1)
table = {}
for r, (i, j) in enumerate(OKEYS):
    table[(int(i), int(j))] = OVALS[r, idx]                      # resample original to 0-460 grid
n_new = 0
for r, (i, j) in enumerate(VKEYS):
    k = (int(i), int(j))
    if k not in table:
        n_new += 1
    table[k] = VVALS[r]                                          # v2 (focus) wins (properly rescanned)
# overlay the near-miss graph-wide recovery if present
import os
NM = f"{ROOT}/cache/ch2_giant_dense1d_nm.npz"
if os.path.exists(NM):
    nm = np.load(NM); NMK = nm["keys"]; NMV = nm["vals"]
    for r, (i, j) in enumerate(NMK):
        k = (int(i), int(j))
        if k not in table:
            n_new += 1
        table[k] = NMV[r]
    print(f"overlaid near-miss recovery: {len(NMK)} edges")
keys = np.array(list(table.keys()))
vals = np.array(list(table.values()), dtype=np.float32)
np.savez_compressed(f"{ROOT}/cache/ch2_giant_dense1d_aug.npz", epochs=NEP, keys=keys, vals=vals)
fin_o = np.isfinite(OVALS).any(1).sum()
fin_a = np.isfinite(vals).any(1).sum()
print(f"AUG: {len(keys)} edges ({n_new} NEW from recovery) on 0-{NEP.max():.0f}/{len(NEP)}ep -> cache/ch2_giant_dense1d_aug.npz")
print(f"finite-window edges: original {fin_o} -> aug {fin_a} (+{fin_a-fin_o})")
