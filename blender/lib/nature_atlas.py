"""Leaf / plant atlas layouts shared by the texture painter (pure python, blender/nature/gen_textures.py)
and the Blender plant generators (blender/lib/nature_tree.py, blender/nature/build_*.py).

A cell is a rectangle in image pixels (x, y from the TOP-LEFT, like PIL). Each cell is painted as one
"card": a sprig / frond / flower cluster whose attachment point (pivot) is the bottom-centre of the
cell ("bottom"), the top-centre ("top", hanging strands) or the centre ("center", top-down cards).
`size` is the physical size of the card in metres (width, height) used when the card is placed on
a plant, so leaves come out at their real-world size.
"""
from __future__ import annotations

TEX_DIR = "textures/nature"   # relative to assets/


def _grid(size, cols, rows, names, card, pivot="bottom"):
    cw, ch = size[0] // cols, size[1] // rows
    out = {}
    for i, n in enumerate(names):
        if n is None:
            continue
        c, r = i % cols, i // cols
        out[n] = {"rect": (c * cw, r * ch, cw, ch), "size": card if not isinstance(card, dict) else card[n],
                  "pivot": pivot if not isinstance(pivot, dict) else pivot.get(n, "bottom")}
    return out


ATLASES: dict = {
    # Ficus benghalensis / microcarpa-like: glossy ovate leaves, small figs, hanging aerial-root fringes
    "leaf_banyan": {"size": (2048, 2048), "cells": _grid((2048, 2048), 2, 2,
                    ["sprig_a", "sprig_figs", "sprig_c", "roots"],
                    {"sprig_a": (0.62, 0.62), "sprig_figs": (0.62, 0.62), "sprig_c": (0.55, 0.55),
                     "roots": (0.55, 1.6)}, {"roots": "top"})},
    # Delonix regia: bipinnate feathery fronds + scarlet flower clusters
    "leaf_flame": {"size": (1024, 1024), "cells": _grid((1024, 1024), 2, 2,
                   ["frond_a", "frond_b", "flowers", "frond_flowers"], (0.75, 0.75))},
    # Hopea odorata (sao): small glossy elliptic leaves on fine twigs
    "leaf_sao": {"size": (1024, 1024), "cells": _grid((1024, 1024), 2, 2,
                 ["sprig_a", "sprig_b", "sprig_c", "sprig_d"], (0.5, 0.5))},
    # Plumeria: big oblong leaves in terminal rosettes + white/yellow flowers
    "leaf_frangipani": {"size": (1024, 1024), "cells": _grid((1024, 1024), 2, 2,
                        ["rosette_flowers", "rosette", "flower_cluster", "leaf_side"],
                        {"rosette_flowers": (0.9, 0.9), "rosette": (0.9, 0.9), "flower_cluster": (0.35, 0.35),
                         "leaf_side": (0.6, 0.6)},
                        {"rosette_flowers": "center", "rosette": "center", "flower_cluster": "bottom"})},
    # Palm half-fronds: leaflets grow from the LEFT edge (rachis) to the right; v runs base->tip (bottom->top)
    "leaf_palm": {"size": (1024, 1024), "cells": _grid((1024, 1024), 4, 1,
                  ["coconut", "coconut_dry", "areca", "areca_b"],
                  {"coconut": (0.75, 3.0), "coconut_dry": (0.7, 2.8), "areca": (0.55, 2.0), "areca_b": (0.55, 2.0)})},
    # Salix babylonica: pendulous strands of narrow leaves (pivot at the top)
    "leaf_willow": {"size": (1024, 1024), "cells": _grid((1024, 1024), 4, 1,
                    ["strand_a", "strand_b", "strand_c", "strand_d"], (0.32, 1.3), "top")},
    # Bambusa: lanceolate leaves on thin twigs
    "leaf_bamboo": {"size": (1024, 1024), "cells": _grid((1024, 1024), 2, 2,
                    ["sprig_a", "sprig_b", "sprig_c", "sprig_d"], (0.6, 0.6))},
    # Undergrowth / climbers / aquatic / litter
    "undergrowth": {"size": (2048, 2048), "cells": _grid((2048, 2048), 4, 4, [
        "ixora", "ixora_flowers", "hedge", "bougainvillea_a",
        "bougainvillea_b", "fern_a", "fern_b", "grass_a",
        "grass_b", "weed", "moss", "fallen_leaves",
        "lotus_pad", "lotus_petal", "hyacinth_leaf", "hyacinth_flower"],
        {"ixora": (0.4, 0.4), "ixora_flowers": (0.3, 0.3), "hedge": (0.4, 0.4), "bougainvillea_a": (0.5, 0.5),
         "bougainvillea_b": (0.5, 0.5), "fern_a": (0.25, 0.7), "fern_b": (0.25, 0.7), "grass_a": (0.35, 0.35),
         "grass_b": (0.3, 0.3), "weed": (0.25, 0.25), "moss": (0.4, 0.4), "fallen_leaves": (0.4, 0.4),
         "lotus_pad": (0.5, 0.5), "lotus_petal": (0.1, 0.1), "hyacinth_leaf": (0.12, 0.12),
         "hyacinth_flower": (0.12, 0.2)},
        {"moss": "center", "fallen_leaves": "center", "lotus_pad": "center", "hyacinth_leaf": "bottom"})},
}

# Bark / stem tiling sets: (name, physical tile size in metres (u around, v along))
BARKS = {
    "bark_banyan": (1.0, 1.0),
    "bark_furrowed": (0.8, 0.8),
    "bark_smooth": (0.8, 0.8),
    "bark_palm": (0.8, 0.8),
    "bamboo_culm": (0.4, 1.0),
}


def cell_uv(atlas: str, cell: str, sub: tuple | None = None):
    """UV rectangle (u0, v0, u1, v1) of a cell, Blender convention (v up). `sub` = (cols, rows, i)
    selects a sub-cell (fallen_leaves / lotus_petal grids)."""
    a = ATLASES[atlas]
    W, H = a["size"]
    x, y, w, h = a["cells"][cell]["rect"]
    if sub:
        cols, rows, i = sub
        sw, sh = w / cols, h / rows
        x, y, w, h = x + (i % cols) * sw, y + (i // cols) * sh, sw, sh
    return (x / W, 1.0 - (y + h) / H, (x + w) / W, 1.0 - y / H)


def cell(atlas: str, name: str) -> dict:
    return ATLASES[atlas]["cells"][name]
