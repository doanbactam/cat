"""Decal atlas layout (veh_decals_albedo.png, 1024x1024): rects (x, y, w, h) in px from the top-left.
Shared by blender/vehicles/gen_textures.py (painter) and blender/lib/vehicles_lib.py (UVs)."""

DECALS = {
    "plate_moto_a": (0, 0, 256, 192),      # 2-line moto plate  (real 190 x 140 mm)
    "plate_moto_b": (256, 0, 256, 192),
    "plate_moto_c": (512, 0, 256, 192),
    "plate_moto_d": (768, 0, 256, 192),
    "plate_car_a": (0, 192, 512, 112),     # 1-line car plate (520 x 110 mm)
    "plate_car_b": (512, 192, 512, 112),
    "taxi_door": (0, 304, 1024, 208),      # "TAXI HÀNG MÂY" door livery + phone
    "taxi_roof": (0, 512, 512, 160),       # roof sign face
    "van_side": (0, 672, 1024, 224),       # "GIAO NHANH PHỐ CŨ" van livery
    "brand_saola": (512, 512, 256, 80),    # fictional bike maker
    "brand_soc": (768, 512, 256, 80),
    "brand_hac": (512, 592, 256, 80),
    "sticker_a": (768, 592, 128, 80),      # parking / repair shop stickers
    "sticker_b": (896, 592, 128, 80),
    "stripe": (0, 896, 1024, 64),          # pin stripe
    "grille_mesh": (0, 960, 256, 64),
}
