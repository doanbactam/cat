"""Write data/i18n/requests/street-props.csv (keys,en,vi) for every PROP_* name_key in the props catalog.
python3 blender/props/gen_i18n.py   (ITEM_* keys are owned by `systems` and already exist in strings.csv)."""
import csv
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
NAMES = {
    "traffic_cone": ("Traffic cone", "Cọc tiêu giao thông"),
    "lamp_post_colonial": ("Cast-iron lamp post", "Cột đèn gang cổ"),
    "lamp_post_modern": ("Street light", "Cột đèn đường"),
    "construction_barrier": ("Construction barrier", "Rào chắn công trình"),
    "trash_bin_municipal": ("Green wheelie bin", "Thùng rác xanh"),
    "trash_bin_household": ("Pedal bin", "Thùng rác đạp chân"),
    "drain_grate": ("Drain grate", "Song chắn rác cống"),
    "manhole_cover": ("Manhole cover", "Nắp cống"),
    "fire_hydrant": ("Fire hydrant", "Trụ cứu hỏa"),
    "mailbox": ("Post box", "Hòm thư"),
    "bicycle_rack": ("Bicycle rack", "Giá để xe đạp"),
    "sign_aframe_com": ("Rice-shop sign", "Biển quán cơm tấm"),
    "sign_aframe_cafe": ("Café chalkboard", "Bảng phấn quán cà phê"),
    "sign_lightbox": ("Light-box sign", "Biển hộp đèn"),
    "banner_standing": ("Standing banner", "Băng rôn đứng"),
    "electric_pole_concrete": ("Concrete power pole", "Cột điện bê tông"),
    "cable_coil_small": ("Coil of cable", "Cuộn dây điện"),
    "cable_coil_large": ("Tangle of cables", "Búi dây điện"),
    "cable_drum": ("Cable drum", "Lô cuốn cáp"),
    "ac_unit": ("Air-conditioner unit", "Cục nóng điều hòa"),
    "gas_cylinder": ("Gas cylinder", "Bình ga"),
    "food_cart_xoi": ("Sticky-rice cart", "Xe xôi"),
    "banh_mi_cart": ("Bánh mì cart", "Xe bánh mì"),
    "pho_pot_stove": ("Phở stock pot", "Nồi nước dùng phở"),
    "stool_plastic_red": ("Plastic stool", "Ghế nhựa"),
    "table_plastic_low": ("Low plastic table", "Bàn nhựa thấp"),
    "umbrella_tarp": ("Vendor umbrella", "Ô che hàng"),
    "tea_set": ("Tea set", "Bộ ấm chén"),
    "fruit_basket": ("Fruit basket", "Mẹt hoa quả"),
    "flower_bucket": ("Flower bucket", "Xô hoa"),
    "fish_basin": ("Fish basin", "Chậu cá"),
    "rice_sack": ("Rice sack", "Bao gạo"),
    "bottle_crate": ("Bottle crate", "Két chai"),
    "cardboard_box_open": ("Open cardboard box", "Hộp các-tông mở"),
    "cardboard_box_closed": ("Cardboard box", "Thùng các-tông"),
    "cardboard_flat_pile": ("Pile of flattened boxes", "Chồng bìa các-tông"),
    "styrofoam_box": ("Foam cool box", "Thùng xốp"),
    "plastic_crate_blue": ("Plastic crate", "Sọt nhựa"),
    "plastic_crate_red": ("Plastic crate", "Sọt nhựa"),
    "wooden_crate": ("Wooden crate", "Thùng gỗ"),
    "recycling_sack": ("Recycling sack", "Bao ve chai"),
    "bucket_plastic": ("Plastic bucket", "Xô nhựa"),
    "basin_plastic": ("Plastic basin", "Chậu nhựa"),
    "broom_soft": ("Soft broom", "Chổi chít"),
    "broom_bamboo": ("Bamboo broom", "Chổi tre"),
    "pot_snake_plant": ("Snake plant", "Chậu lưỡi hổ"),
    "pot_chili": ("Chili plant", "Chậu ớt"),
    "pot_bonsai": ("Bonsai", "Chậu cây cảnh"),
    "pot_aloe": ("Aloe", "Chậu nha đam"),
    "bird_cage": ("Bird cage", "Lồng chim"),
    "wind_chime": ("Wind chime", "Chuông gió"),
    "altar_box": ("Earth-god altar", "Bàn thờ ông Địa"),
    "laundry_rack": ("Laundry rack", "Giá phơi đồ"),
    "slippers_pair": ("Flip-flops", "Dép tổ ong"),
    "sandals_honeycomb": ("Plastic sandals", "Dép nhựa"),
    "shoes_canvas_pair": ("Canvas shoes", "Giày vải"),
    "food_bowl": ("Food bowl", "Bát cơm mèo"),
    "water_bowl": ("Water bowl", "Bát nước"),
    "star_lantern_red": ("Star lantern", "Đèn ông sao"),
    "silk_lantern_round": ("Silk lantern", "Đèn lồng lụa"),
    "silk_lantern_oval": ("Silk lantern", "Đèn lồng lụa"),
    "carp_lantern": ("Carp lantern", "Đèn cá chép"),
    "lantern_string": ("String of lanterns", "Dây đèn lồng"),
    "cup_ceramic": ("Porcelain cup", "Tách sứ"),
    "mug_enamel": ("Enamel mug", "Ca tráng men"),
    "glass_tra_da": ("Glass of iced tea", "Cốc trà đá"),
    "vase_flower": ("Flower vase", "Lọ hoa"),
    "cactus_pot": ("Little cactus", "Chậu xương rồng"),
    "bottle_fish_sauce": ("Fish-sauce bottle", "Chai nước mắm"),
    "bottle_soy": ("Soy-sauce bottle", "Chai xì dầu"),
    "bottle_water": ("Water bottle", "Chai nước suối"),
    "phone": ("Phone", "Điện thoại"),
    "tv_remote": ("TV remote", "Điều khiển TV"),
    "book_single": ("Book", "Cuốn sách"),
    "book_stack": ("Stack of books", "Chồng sách"),
    "can_condensed_milk": ("Tin of condensed milk", "Lon sữa đặc"),
}
SHARED = {"PROP_STOOL_PLASTIC": ("Plastic stool", "Ghế nhựa"), "PROP_STAR_LANTERN": ("Star lantern", "Đèn ông sao")}


def main():
    cat = json.load(open(os.path.join(ROOT, "assets/models/props/catalog.json")))
    rows = {}
    for e in cat:
        k = e["name_key"]
        if not k.startswith("PROP_"):
            continue
        if k in SHARED:
            rows[k] = SHARED[k]
        elif e["id"] in NAMES:
            rows[k] = NAMES[e["id"]]
        else:
            print("MISSING NAME", e["id"])
            rows[k] = (e["id"].replace("_", " ").capitalize(), e["id"].replace("_", " "))
    out = os.path.join(ROOT, "data/i18n/requests/street-props.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["keys", "en", "vi"])
        for k in sorted(rows):
            w.writerow([k, *rows[k]])
    print("WROTE", out, len(rows))


main()
