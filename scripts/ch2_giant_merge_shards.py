"""E-735 — merge the sharded faithful-window precompute outputs into cache/ch2_giant_faithful_full.npz."""
import glob, numpy as np
ROOT = "/home/julian/Projects/esa_spoc_26_3"
merged = {}
files = sorted(glob.glob(f"{ROOT}/cache/ch2_giant_faithful_full_shard*.npz"))
for f in files:
    w = np.load(f, allow_pickle=True)["windows"].item()
    merged.update(w)
    print(f"merged {f}: +{len(w)} -> {len(merged)}")
np.savez(f"{ROOT}/cache/ch2_giant_faithful_full.npz", windows=np.array(merged, dtype=object))
print(f"DONE merged {len(merged)} edges -> cache/ch2_giant_faithful_full.npz")
