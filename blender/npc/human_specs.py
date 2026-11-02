"""Character sheet for every human NPC (owner: creatures). Imported by build_humans.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from npc_human import Spec, GARMENTS, ACCESSORIES, hair

SPECS = {
    # --- named characters ---------------------------------------------------
    "ba_tu": Spec("ba_tu", height=1.49, sex=0.0, mass=-0.1, age=0.92, skin="#b9947c", lips="#9c6662",
                  hair_col="#a9a49c", stoop=0.55, gait=0.75, walk_speed=0.85, seed=11,
                  garments=[("top", dict(label="aobaba", sleeve=0.97, hem=0.70, t=0.012, loose=0.012)),
                            ("bottom", dict(label="trousers", length=0.96, t=0.012, loose=0.022, flare=0.02)),
                            ("footwear", dict(kind="sandal", label="sandals"))],
                  hair=("bun", {}), tris=17000),
    "co_hoa": Spec("co_hoa", height=1.55, sex=0.0, mass=0.2, age=0.45, skin="#c29a7c", lips="#a65f5c",
                   hair_col="#1a1512", walk_speed=1.15, seed=21,
                   garments=[("top", dict(label="blouse", sleeve=0.32, hem=0.74, t=0.010, loose=0.008)),
                             ("bottom", dict(label="trousers", length=0.90, t=0.010, loose=0.012)),
                             ("apron", dict(label="apron", top=1.18, bottom=0.46)),
                             ("footwear", dict(kind="boots", label="boots", boot_height=0.40))],
                   hair=("bun", {}), accessories=["nonla"], tris=18000),
    "chu_sau": Spec("chu_sau", height=1.66, sex=1.0, mass=0.45, age=0.5, skin="#b98c6c", lips="#93605a",
                    hair_col="#18130f", walk_speed=1.2, seed=31, beard=0.35,
                    garments=[("top", dict(label="polo", sleeve=0.30, hem=0.80, t=0.010, loose=0.010, collar="polo")),
                              ("bottom", dict(label="khaki", length=0.97, t=0.010, loose=0.014)),
                              ("footwear", dict(kind="flipflop", label="flipflops"))],
                    hair=("short", {}), accessories=["cap"], tris=17000),
    "bin": Spec("bin", height=1.28, sex=1.0, mass=-0.1, age=0.03, kid=True, head=1.0, skin="#c79f80",
                lips="#b06a64", hair_col="#15110e", walk_speed=1.15, seed=41,
                garments=[("top", dict(label="school_shirt", sleeve=0.30, hem=0.93, t=0.009, loose=0.008,
                                       collar="polo")),
                          ("bottom", dict(label="shorts", length=0.42, t=0.008, loose=0.004, waist=0.99)),
                          ("scarf", dict(label="scarf")),
                          ("footwear", dict(kind="sandal", label="sandals"))],
                hair=("kid", {}), tris=15000),
    # --- pedestrians -----------------------------------------------------------
    "ped_office": Spec("ped_office", height=1.70, sex=1.0, mass=0.0, age=0.3, skin="#c09679", lips="#9a625c",
                       hair_col="#16120f", walk_speed=1.35, seed=51,
                       garments=[("top", dict(label="shirt", sleeve=0.97, hem=0.95, t=0.009, loose=0.008,
                                              collar="polo")),
                                 ("bottom", dict(label="slacks", length=0.98, t=0.010, loose=0.012)),
                                 ("footwear", dict(kind="shoes", label="shoes"))],
                       hair=("side_part", {}), accessories=["phone"], tex_size=2048, tris=15000),
    "ped_student": Spec("ped_student", height=1.58, sex=0.0, mass=-0.35, age=0.12, skin="#c8a084", lips="#b0686a",
                        hair_col="#1d1713", walk_speed=1.3, seed=61,
                        garments=[("top", dict(label="tshirt", sleeve=0.22, hem=0.84, t=0.009, loose=0.008)),
                                  ("bottom", dict(label="jeans", length=0.98, t=0.009, loose=0.006)),
                                  ("backpack", dict(label="backpack")),
                                  ("footwear", dict(kind="shoes", label="sneakers"))],
                        hair=("ponytail", {}), accessories=["phone"], tris=15000),
    "ped_elder_man": Spec("ped_elder_man", height=1.62, sex=1.0, mass=-0.2, age=0.85, skin="#b48a6e",
                          lips="#94605c", hair_col="#bdb8b0", stoop=0.45, gait=0.8, walk_speed=0.9, seed=71,
                          beard=0.2,
                          garments=[("top", dict(label="shirt", sleeve=0.30, hem=0.80, t=0.010, loose=0.012,
                                                 collar="polo")),
                                    ("bottom", dict(label="trousers", length=0.97, t=0.010, loose=0.018)),
                                    ("footwear", dict(kind="sandal", label="sandals"))],
                          hair=("thin", {}), accessories=["cane"], tris=15000),
    "ped_helmet_woman": Spec("ped_helmet_woman", height=1.60, sex=0.0, mass=0.0, age=0.35, skin="#c9a286",
                             lips="#a86466", hair_col="#1c1612", walk_speed=1.25, seed=81,
                             garments=[("top", dict(label="sunjacket", sleeve=1.0, hem=0.74, t=0.012,
                                                    loose=0.016)),
                                       ("bottom", dict(label="jeans", length=0.98, t=0.009, loose=0.008)),
                                       ("skirt", dict(label="sunskirt", top=0.98, bottom=0.28)),
                                       ("mask", dict(label="mask")),
                                       ("footwear", dict(kind="shoes", label="shoes"))],
                             hair=("under_hat", {}), accessories=["helmet"], tris=15000),
    "ped_shopper": Spec("ped_shopper", height=1.52, sex=0.0, mass=0.35, age=0.65, skin="#bf977b", lips="#9e6260",
                        hair_col="#2a2420", stoop=0.2, gait=0.9, walk_speed=1.05, seed=91,
                        garments=[("top", dict(label="blouse", sleeve=0.40, hem=0.76, t=0.011, loose=0.012)),
                                  ("bottom", dict(label="trousers", length=0.95, t=0.011, loose=0.02, flare=0.015)),
                                  ("footwear", dict(kind="sandal", label="sandals"))],
                        hair=("perm", {}), accessories=["basket"], tris=15000),
    "ped_xeom": Spec("ped_xeom", height=1.68, sex=1.0, mass=0.1, age=0.55, skin="#ad8264", lips="#8e5a54",
                     hair_col="#17120e", walk_speed=1.2, seed=101, beard=0.5,
                     garments=[("top", dict(label="jacket", sleeve=0.99, hem=0.80, t=0.014, loose=0.016,
                                            collar="mandarin")),
                               ("bottom", dict(label="trousers", length=0.97, t=0.010, loose=0.014)),
                               ("footwear", dict(kind="sandal", label="sandals"))],
                     hair=("under_hat", {}), accessories=["helmet"], tris=15000),
}


def dress(body):
    sp = body.spec
    # an untucked top hides the trouser waist: start the trousers just above its hem so loose
    # trouser hips can never poke through the shirt
    hems = [kw.get("hem", 0.8) for fn, kw in sp.garments if fn == "top" and kw.get("hem", 0.8) < 0.9]
    for fn, kw in sp.garments:
        if fn == "bottom" and hems:
            kw = dict(kw)
            kw["waist"] = min(kw.get("waist", 0.98), min(hems) + 0.05)
            kw["tight_above"] = min(hems) + 0.015
        GARMENTS[fn](body, **kw)
    style, kw = sp.hair
    if style:
        hair(body, style, **kw)
    for acc in sp.accessories:
        ACCESSORIES[acc](body)


MATS = {
    "ba_tu": {
        "aobaba": dict(color="#b9aec4", color2="#ede6ee", color3="#c98a9a", leaf="#7f8f78", pattern="floral",
                       scale=0.05, rough=0.72),
        "trousers": dict(color="#1c1a1d", pattern="satin", rough=0.36),
        "sandals": dict(color="#5a3a26", sole="#2a2420", strap="#4a2e1e", pattern="plain", rough=0.6),
    },
    "co_hoa": {
        "blouse": dict(color="#3f6aa0", color2="#e8eef2", color3="#f2d36b", leaf="#2f5d4a", pattern="floral",
                       scale=0.04, rough=0.7),
        "trousers": dict(color="#2c2a33", color2="#4a4656", pattern="check", scale=0.03, rough=0.7),
        "apron": dict(color="#7b2433", pattern="plastic", rough=0.28, strap="#5e1a26"),
        "boots": dict(color="#d9d8cc", pattern="rubber", rough=0.45, sole="#9a9a90"),
        "nonla": dict(color="#cdb98a", pattern="straw", rough=0.75, strap="#f0ede6"),
        "nonla_ribbon": dict(color="#e9e4dc", pattern="plain", rough=0.6),
    },
    "chu_sau": {
        "polo": dict(color="#2f5f8a", trim="#e5e2da", pattern="plain", rough=0.78),
        "polo_trim": dict(color="#e5e2da", pattern="plain", rough=0.7),
        "khaki": dict(color="#9c8a68", pattern="plain", rough=0.8),
        "flipflops": dict(color="#2e5d8f", sole="#26323d", strap="#1d4572", pattern="rubber", rough=0.6),
        "cap": dict(color="#a8332d", brim="#9a2e29", pattern="plain", rough=0.75),
    },
    "bin": {
        "school_shirt": dict(color="#e8e6df", pattern="plain", rough=0.75),
        "school_shirt_trim": dict(color="#e3e1da", pattern="plain", rough=0.7),
        "shorts": dict(color="#1f2a4a", pattern="plain", rough=0.78),
        "scarf": dict(color="#b3201f", pattern="plain", rough=0.6),
        "sandals": dict(color="#3b3430", sole="#1f1c1a", strap="#2c2622", pattern="plain", rough=0.6),
    },
    "ped_office": {
        "shirt": dict(color="#b7cbe0", color2="#a6bcd4", pattern="stripes", scale=0.006, rough=0.7),
        "shirt_trim": dict(color="#b7cbe0", pattern="plain", rough=0.7),
        "slacks": dict(color="#33363c", pattern="plain", rough=0.65),
        "shoes": dict(color="#1f1714", pattern="plastic", rough=0.35, sole="#141110"),
        "phone": dict(color="#1a1b1e", pattern="plastic", rough=0.2),
    },
    "ped_student": {
        "tshirt": dict(color="#ece7de", color2="#c95b4a", pattern="stripes", scale=0.05, rough=0.8),
        "jeans": dict(color="#33476b", pattern="denim", rough=0.8),
        "backpack": dict(color="#283a5c", pattern="plain", rough=0.65, strap="#1c2840"),
        "sneakers": dict(color="#e6e4de", pattern="plain", rough=0.6, sole="#d9d6cc"),
        "hair_tie": dict(color="#c43a4a", pattern="plain", rough=0.5),
        "phone": dict(color="#d6c9b8", pattern="plastic", rough=0.25),
    },
    "ped_elder_man": {
        "shirt": dict(color="#8796a6", color2="#5d6b7c", color3="#d9d4c8", pattern="plaid", scale=0.05, rough=0.75),
        "shirt_trim": dict(color="#8796a6", pattern="plain", rough=0.75),
        "trousers": dict(color="#6b6a66", pattern="plain", rough=0.75),
        "sandals": dict(color="#3d2c22", sole="#1f1a17", strap="#3d2c22", pattern="plain", rough=0.6),
        "cane": dict(color="#5a3a22", pattern="plain", rough=0.45),
    },
    "ped_helmet_woman": {
        "sunjacket": dict(color="#e2a0b4", pattern="plain", rough=0.55),
        "jeans": dict(color="#2c3d5e", pattern="denim", rough=0.8),
        "sunskirt": dict(color="#3b3550", color2="#d9c9e0", color3="#e0b84a", leaf="#4a6a50", pattern="floral",
                         scale=0.06, rough=0.6),
        "mask": dict(color="#30343c", pattern="plain", rough=0.85),
        "shoes": dict(color="#e2ddd2", pattern="plain", rough=0.6, sole="#cfc9bc"),
        "helmet": dict(color="#ece8df", pattern="plastic", rough=0.3, visor="#2c2a28", strap="#2a2a2a"),
    },
    "ped_shopper": {
        "blouse": dict(color="#b5643a", color2="#f0d9a8", color3="#7a2e2a", leaf="#6c7a3a", pattern="floral",
                       scale=0.035, rough=0.72),
        "trousers": dict(color="#4f3a56", color2="#cfb6d8", color3="#e8d088", leaf="#5a6a48", pattern="floral",
                         scale=0.05, rough=0.7),
        "sandals": dict(color="#8a2f3a", sole="#3a2a24", strap="#8a2f3a", pattern="plain", rough=0.5),
        "basket": dict(color="#c23a3a", pattern="weave_plastic", rough=0.45),
        "basket_handle": dict(color="#c23a3a", pattern="plastic", rough=0.4),
    },
    "ped_xeom": {
        "jacket": dict(color="#56603f", pattern="plain", rough=0.7),
        "jacket_trim": dict(color="#4a5336", pattern="plain", rough=0.7),
        "trousers": dict(color="#2d2c2a", pattern="plain", rough=0.72),
        "sandals": dict(color="#2e2621", sole="#191513", strap="#2e2621", pattern="plain", rough=0.6),
        "helmet": dict(color="#3e6b3e", pattern="plastic", rough=0.32, visor="#1f2a1f", strap="#222222"),
    },
}
