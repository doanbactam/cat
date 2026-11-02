"""Dev probe: build one prop function without baking and print per-part bounds (no files written)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
sys.path.insert(0, os.path.join(HERE, ".."))
import common as C
import props_bake as PB
import props_geo as G
import props_nodes as PN
import p_street, p_utility, p_stall, p_home, p_festival, p_clutter, p_items  # noqa
pid = sys.argv[-1]
C.reset_scene(); G.reset_counters(); PN.ensure_mask_image(); PN.ensure_label_image()
res = PB.REG[pid]["fn"](**PB.REG[pid]["args"])
for p in res["parts"]:
    mn, mx = G.bounds([p])
    print(f"PART {p.name:20s} faces={len(p.data.polygons):5d} min={tuple(round(x,3) for x in mn)} max={tuple(round(x,3) for x in mx)}")
