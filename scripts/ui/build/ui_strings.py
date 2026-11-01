#!/usr/bin/env python3
"""UI string table of Mèo Cam (owner: ui) — English + Vietnamese.

Source of truth for every string the UI area shows. Writes data/i18n/requests/ui.csv; then
scripts/ui/build/merge_i18n.py merges all data/i18n/requests/*.csv into data/i18n/strings.csv.
Run:  python3 scripts/ui/build/ui_strings.py && python3 scripts/ui/build/merge_i18n.py
"""
import csv
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
OUT = os.path.join(ROOT, "data", "i18n", "requests", "ui.csv")

S = {}


def s(key, en, vi):
    assert key not in S, key
    S[key] = (en, vi)


# --- title / studio / splash ------------------------------------------------------------------
s("GAME_TITLE", "Orange Cat: Old Quarter", "Mèo Cam: Phố Cũ")
s("TITLE_MAIN", "Mèo Cam", "Mèo Cam")
s("TITLE_SUB", "Old Quarter", "Phố Cũ")
s("MENU_TAGLINE", "A small, warm tale of an orange cat in Hàng Mây.", "Chuyện nhỏ ấm áp của một chú mèo cam ở phố Hàng Mây.")
s("STUDIO_NAME", "Xưởng Mái Ngói", "Xưởng Mái Ngói")
s("STUDIO_TAGLINE", "Roof-Tile Workshop · presents", "Roof-Tile Workshop · giới thiệu")
s("SPLASH_MADE_WITH", "Made with", "Được làm bằng")
s("SPLASH_AND_BLENDER", "and Blender", "và Blender")

# --- main menu ---------------------------------------------------------------------------------
s("MENU_CONTINUE", "Continue", "Tiếp tục")
s("MENU_NEW_GAME", "New game", "Chơi mới")
s("MENU_LOAD", "Load journey", "Tải hành trình")
s("MENU_SETTINGS", "Settings", "Cài đặt")
s("MENU_CREDITS", "Credits", "Đội ngũ")
s("MENU_QUIT", "Quit", "Thoát")
s("UI_NO_GAME_SCENE", "The streets of Hàng Mây are still being built…", "Phố Hàng Mây vẫn đang được dựng…")
s("UI_LOAD_FAILED", "That journey could not be loaded.", "Không tải được hành trình này.")
s("UI_SELECT", "Select", "Chọn")
s("UI_BACK", "Back", "Quay lại")
s("UI_CHANGE", "Change", "Đổi")
s("UI_TABS", "Tabs", "Đổi thẻ")
s("UI_SCROLL", "Scroll", "Cuộn")
s("UI_CLOSE", "Close", "Đóng")
s("UI_TRACK", "Track", "Theo dõi")
s("UI_ZOOM", "Zoom", "Thu phóng")
s("UI_PAN", "Move", "Di chuyển")
s("UI_CENTER", "Centre on Cam", "Về chỗ Cam")
s("UI_SKIP", "Skip", "Bỏ qua")
s("UI_CONTINUE", "Continue", "Tiếp")
s("UI_LOADING", "Loading", "Đang tải")
s("UI_TIP_HEADER", "Did you know", "Mẹo nhỏ")

# --- buttons / confirm -------------------------------------------------------------------------
s("BTN_SAVE", "Save", "Lưu")
s("BTN_LOAD", "Load", "Tải")
s("BTN_DELETE", "Delete", "Xóa")
s("BTN_BACK", "Back", "Quay lại")
s("BTN_CLOSE", "Close", "Đóng")
s("BTN_RESET", "Reset", "Khôi phục")
s("BTN_RESET_ALL", "Reset everything", "Khôi phục tất cả")
s("CONFIRM_YES", "Yes", "Đồng ý")
s("CONFIRM_NO", "Cancel", "Hủy")
s("CONFIRM_QUIT_TITLE", "Leave Hàng Mây?", "Rời phố Hàng Mây?")
s("CONFIRM_QUIT_MENU_BODY", "Cam will keep napping on the rooftop until you return.", "Cam sẽ ngủ tiếp trên mái nhà chờ bạn quay lại.")
s("CONFIRM_QUIT_BODY", "Progress since your last save will be lost.", "Tiến trình kể từ lần lưu gần nhất sẽ mất.")
s("CONFIRM_MAIN_MENU_TITLE", "Return to the main menu?", "Về màn hình chính?")
s("CONFIRM_NEW_GAME_TITLE", "Start a new journey?", "Bắt đầu hành trình mới?")
s("CONFIRM_NEW_GAME_BODY", "Cam wakes up again on the first morning. Your autosave will be replaced as you play; manual saves stay.",
  "Cam sẽ thức dậy lại vào buổi sáng đầu tiên. Bản tự động lưu sẽ bị thay khi chơi; các bản lưu tay vẫn giữ nguyên.")
s("CONFIRM_OVERWRITE_TITLE", "Overwrite this save?", "Ghi đè bản lưu này?")
s("CONFIRM_OVERWRITE_BODY", "The journey stored here will be replaced.", "Hành trình đang lưu ở ô này sẽ bị thay thế.")
s("CONFIRM_DELETE_TITLE", "Delete this save?", "Xóa bản lưu này?")
s("CONFIRM_DELETE_BODY", "This cannot be undone.", "Không thể hoàn tác.")
s("CONFIRM_LOAD_TITLE", "Load this journey?", "Tải hành trình này?")
s("CONFIRM_RESET_TITLE", "Reset all settings?", "Khôi phục mọi cài đặt?")
s("CONFIRM_RESET_BODY", "Graphics, sound, controls and key bindings return to their defaults.",
  "Đồ họa, âm thanh, điều khiển và phím bấm sẽ trở về mặc định.")

# --- save slots --------------------------------------------------------------------------------
s("SAVE_TITLE", "Save journey", "Lưu hành trình")
s("LOAD_TITLE", "Load journey", "Tải hành trình")
s("SLOT_AUTOSAVE", "Autosave", "Tự động lưu")
s("SLOT_MANUAL", "Journal page {n}", "Trang nhật ký {n}")
s("SLOT_EMPTY", "An empty page", "Trang còn trống")
s("SLOT_DAY", "Day {day}", "Ngày {day}")
s("SLOT_PLAYTIME", "Played {time}", "Đã chơi {time}")
s("SAVE_DONE", "Journey saved", "Đã lưu hành trình")
s("QUICK_SAVED", "Quick-saved", "Đã lưu nhanh")
s("QUICK_LOAD_NONE", "No quick-save yet", "Chưa có bản lưu nhanh")

# --- HUD ---------------------------------------------------------------------------------------
s("HUD_LEVEL", "Level {level}", "Cấp {level}")
s("HUD_LV", "Lv", "Cấp")
s("HUD_XP", "{xp} / {next} XP", "{xp} / {next} KN")
s("HUD_XP_GAIN", "+{n} XP", "+{n} KN")
s("HUD_MOUTH", "In mouth", "Đang ngậm")
s("HUD_NEW_QUEST", "New quest", "Nhiệm vụ mới")
s("HUD_QUEST_COMPLETE", "Quest complete", "Hoàn thành nhiệm vụ")
s("HUD_QUEST_FAILED", "Quest failed", "Nhiệm vụ thất bại")
s("HUD_LEVEL_UP", "Level up", "Lên cấp")
s("HUD_LEVEL_UP_SUB", "Level {level} · +{sp} skill point · +1 attribute point", "Cấp {level} · +{sp} điểm kỹ năng · +1 điểm thuộc tính")
s("HUD_LEVEL_UP_HINT", "Open Skills from the pause menu to spend them.", "Mở Kỹ năng trong menu tạm dừng để dùng điểm.")
s("HUD_DISCOVERED", "Discovered", "Khám phá")
s("HUD_DISTANCE", "{m} m", "{m} m")
s("HUD_SAVING", "Saving…", "Đang lưu…")
s("HUD_SAVED", "Saved", "Đã lưu")
s("HUD_CAPS", "{n}", "{n}")
s("HUD_REWARD_XP", "+{n} XP", "+{n} KN")
s("COMPASS_N", "N", "B")
s("COMPASS_E", "E", "Đ")
s("COMPASS_S", "S", "N")
s("COMPASS_W", "W", "T")
s("COMPASS_NE", "NE", "ĐB")
s("COMPASS_SE", "SE", "ĐN")
s("COMPASS_SW", "SW", "TN")
s("COMPASS_NW", "NW", "TB")

# --- dialogue ----------------------------------------------------------------------------------
s("DLG_CONTINUE", "Continue", "Tiếp")
s("DLG_REQUIRES", "Needs: {req}", "Cần: {req}")
s("DLG_HISTORY", "Conversation", "Cuộc trò chuyện")
s("DLG_CAM", "Cam", "Cam")

# --- pause -------------------------------------------------------------------------------------
s("PAUSE_TITLE", "Paused", "Tạm dừng")
s("PAUSE_RESUME", "Resume", "Chơi tiếp")
s("PAUSE_JOURNAL", "Journal", "Nhật ký")
s("PAUSE_MAP", "Map", "Bản đồ")
s("PAUSE_INVENTORY", "Belongings", "Đồ đạc")
s("PAUSE_SKILLS", "Skills", "Kỹ năng")
s("PAUSE_SETTINGS", "Settings", "Cài đặt")
s("PAUSE_SAVE", "Save journey", "Lưu hành trình")
s("PAUSE_LOAD", "Load journey", "Tải hành trình")
s("PAUSE_MAIN_MENU", "Main menu", "Màn hình chính")
s("PAUSE_QUIT", "Quit game", "Thoát game")
s("PAUSE_STATUS", "Day {day} · {time} · {weather}", "Ngày {day} · {time} · {weather}")
s("PAUSE_SKILL_POINTS", "{n} unspent skill points", "Còn {n} điểm kỹ năng")
s("WEATHER_CLEAR", "clear sky", "trời quang")
s("WEATHER_CLOUDY", "cloudy", "nhiều mây")
s("WEATHER_RAIN", "rain", "mưa")
s("WEATHER_STORM", "storm", "giông bão")
s("WEATHER_FOG", "fog", "sương mù")

# --- inventory ---------------------------------------------------------------------------------
s("INV_TITLE", "Belongings", "Đồ đạc")
s("INV_SUBTITLE", "What Cam keeps in his den under the tea counter", "Những thứ Cam cất trong ổ dưới quầy trà")
s("INV_TAB_ALL", "All", "Tất cả")
s("CAT_FOOD", "Food", "Đồ ăn")
s("CAT_QUEST", "Story", "Cốt truyện")
s("CAT_TOY", "Toys", "Đồ chơi")
s("CAT_SHINY", "Shiny things", "Đồ lấp lánh")
s("CAT_TROPHY", "Trophies", "Chiến lợi phẩm")
s("CAT_MEMORY", "Memories", "Kỷ niệm")
s("CAT_COSMETIC", "Collars", "Vòng cổ")
s("CAT_CONSUMABLE", "Remedies", "Thuốc bổ")
s("CAT_CURRENCY", "Caps", "Nắp chai")
s("INV_CARRY", "Carry in mouth", "Ngậm theo")
s("INV_PUT_AWAY", "Put back in the den", "Cất lại vào ổ")
s("INV_EAT", "Eat", "Ăn")
s("INV_USE", "Use", "Dùng")
s("INV_EQUIP", "Wear", "Đeo")
s("INV_UNEQUIP", "Take off", "Tháo ra")
s("INV_IN_MOUTH", "In mouth", "Đang ngậm")
s("INV_EQUIPPED", "Worn", "Đang đeo")
s("INV_EMPTY", "Nothing here yet. Cam's den is waiting for treasures.", "Chưa có gì cả. Ổ của Cam đang chờ báu vật.")
s("INV_CAPS", "{n} bottle caps", "{n} nắp chai")
s("INV_FOOD_VALUE", "Fills {n} hunger", "Thêm {n} no bụng")
s("INV_COUNT", "×{n}", "×{n}")
s("INV_VALUE", "Worth {n} caps to Lão Quạ", "Lão Quạ trả {n} nắp chai")
s("INV_MOUTH_HINT", "A cat carries only one thing in its mouth at a time.", "Mèo chỉ ngậm được một thứ mỗi lúc.")
s("INV_BUFFS", "Feeling", "Trạng thái")
s("INV_BUFF_LEFT", "{min} min left", "còn {min} phút")
s("INV_NO_BUFFS", "Nothing special.", "Không có gì đặc biệt.")
s("INV_USED", "Used: {item}", "Đã dùng: {item}")
s("INV_ATE", "Ate: {item}", "Đã ăn: {item}")

# --- skills ------------------------------------------------------------------------------------
s("SKILLS_TITLE", "Skills", "Kỹ năng")
s("SKILLS_POINTS", "Skill points", "Điểm kỹ năng")
s("SKILLS_ATTR_POINTS", "Attribute points", "Điểm thuộc tính")
s("SKILLS_LEARN", "Learn", "Học")
s("SKILLS_LEARNED", "Learned", "Đã học")
s("SKILLS_LOCKED", "Locked", "Chưa mở")
s("SKILLS_AVAILABLE", "Can learn now", "Có thể học")
s("SKILLS_REQUIRES", "Needs: {req}", "Cần: {req}")
s("SKILLS_COST", "Costs {n} point", "Tốn {n} điểm")
s("SKILLS_EFFECTS", "Effects", "Hiệu quả")
s("SKILLS_RAISE", "Raise", "Tăng")
s("SKILLS_TIER", "Tier {n}", "Bậc {n}")
s("SKILLS_ATTRIBUTES", "Attributes", "Thuộc tính")
s("SKILLS_LEVEL", "Level {level} · {xp} XP to next level", "Cấp {level} · còn {xp} KN để lên cấp")
s("SKILLS_LEVEL_MAX", "Level {level} · highest level", "Cấp {level} · cấp cao nhất")
s("SKILLS_UNLOCKED_TOAST", "Learned {skill}", "Đã học {skill}")
s("SKILLS_ATTR_HINT", "Each point raises an attribute by one (max 10).", "Mỗi điểm tăng một thuộc tính thêm 1 (tối đa 10).")
s("SKILLS_HOLD", "Hold to learn", "Giữ để học")

# modifier labels (skill effects)
MODS = {
    "move_speed": ("Walking speed", "Tốc độ đi"),
    "sprint_speed": ("Running speed", "Tốc độ chạy"),
    "sneak_speed": ("Sneaking speed", "Tốc độ rón rén"),
    "jump_distance": ("Jump distance", "Tầm nhảy xa"),
    "jump_height": ("Jump height", "Độ nhảy cao"),
    "climb_speed": ("Climbing speed", "Tốc độ leo"),
    "wire_speed": ("Speed on wires", "Tốc độ đi trên dây"),
    "balance": ("Balance", "Thăng bằng"),
    "fall_damage_mult": ("Fall damage", "Sát thương khi ngã"),
    "safe_fall_height": ("Safe fall height", "Độ cao rơi an toàn"),
    "wall_jump": ("Wall jump", "Bật tường"),
    "noise_mult": ("Noise you make", "Tiếng động gây ra"),
    "landing_noise_mult": ("Landing noise", "Tiếng động khi tiếp đất"),
    "detection_mult": ("How easily you are noticed", "Mức dễ bị phát hiện"),
    "night_vision": ("Night vision", "Nhìn trong đêm"),
    "charm_bonus": ("Charm", "Duyên"),
    "meow_charm": ("Charm of your meows", "Sức hút của tiếng meo"),
    "food_gift_chance": ("Chance of food gifts", "Cơ hội được cho ăn"),
    "rep_gain_mult": ("Reputation gained", "Danh tiếng nhận được"),
    "price_mult": ("Prices at Lão Quạ's", "Giá ở chỗ Lão Quạ"),
    "catch_chance": ("Catch chance", "Tỉ lệ bắt mồi"),
    "catch_birds": ("Can catch birds", "Bắt được chim"),
    "pounce_distance": ("Pounce distance", "Tầm vồ"),
    "pounce_speed": ("Pounce speed", "Tốc độ vồ"),
    "scent_range": ("Scent range", "Tầm đánh hơi"),
    "hearing_range": ("Hearing range", "Tầm nghe"),
    "cat_sense_cost": ("Cat-sense energy cost", "Năng lượng cho giác quan mèo"),
    "sense_collectibles": ("Sense hidden memories", "Cảm nhận kỷ niệm ẩn"),
    "prey_xp_mult": ("XP from prey", "Kinh nghiệm từ con mồi"),
    "energy_regen": ("Energy regained while resting", "Năng lượng hồi khi nghỉ"),
    "energy_drain": ("Energy used", "Năng lượng tiêu hao"),
    "sprint_energy_mult": ("Energy used running", "Năng lượng khi chạy"),
    "hunger_drain": ("Hunger over time", "Tốc độ đói"),
    "food_value": ("Food value", "Độ no từ thức ăn"),
    "warmth_drain": ("Warmth lost", "Hơi ấm bị mất"),
    "wet_rate": ("How fast fur gets wet", "Tốc độ ướt lông"),
    "health_regen": ("Health regeneration", "Hồi sức khỏe"),
    "purr_heal": ("Purring heals", "Gừ gừ hồi sức"),
    "free_faints_per_day": ("Free faints per day", "Lần ngất miễn phí mỗi ngày"),
    "faint_cap_loss_mult": ("Caps lost when fainting", "Nắp chai mất khi ngất"),
    "max_health": ("Max health", "Sức khỏe tối đa"),
    "max_hunger": ("Max fullness", "No bụng tối đa"),
    "max_energy": ("Max energy", "Năng lượng tối đa"),
    "max_warmth": ("Max warmth", "Hơi ấm tối đa"),
    "xp_mult": ("XP gained", "Kinh nghiệm nhận được"),
}
for k, (en, vi) in MODS.items():
    s("MOD_" + k.upper(), en, vi)
s("MOD_UNLOCKS", "Unlocks: {what}", "Mở khóa: {what}")

# --- journal -----------------------------------------------------------------------------------
s("JOURNAL_TITLE", "Journal", "Nhật ký")
s("JOURNAL_TAB_QUESTS", "Quests", "Nhiệm vụ")
s("JOURNAL_TAB_MEMORIES", "Memories", "Kỷ niệm")
s("JOURNAL_TAB_PLACES", "Places", "Địa điểm")
s("JOURNAL_TAB_CAM", "Cam", "Về Cam")
s("JOURNAL_ACTIVE", "In progress", "Đang làm")
s("JOURNAL_COMPLETED", "Completed", "Đã xong")
s("JOURNAL_FAILED", "Failed", "Thất bại")
s("JOURNAL_TRACK", "Track this quest", "Theo dõi nhiệm vụ này")
s("JOURNAL_TRACKED", "Tracked", "Đang theo dõi")
s("JOURNAL_NO_QUESTS", "No quests yet. Wander, listen, meow at people.", "Chưa có nhiệm vụ nào. Cứ đi dạo, lắng nghe, kêu meo với mọi người.")
s("JOURNAL_SELECT_QUEST", "Choose a quest to read its page.", "Chọn một nhiệm vụ để đọc.")
s("JOURNAL_REWARDS", "Rewards", "Phần thưởng")
s("JOURNAL_GIVER", "From {name}", "Từ {name}")
s("JOURNAL_OPTIONAL", "optional", "không bắt buộc")
s("JOURNAL_MEMORY_LOCKED", "Not found yet", "Chưa tìm thấy")
s("JOURNAL_MEMORY_LOCKED_HINT", "Somewhere in Hàng Mây an old photograph is waiting.", "Đâu đó ở Hàng Mây, một tấm ảnh cũ đang chờ.")
s("JOURNAL_MEMORIES_COUNT", "{n} of 12 memories found", "Đã tìm {n}/12 kỷ niệm")
s("JOURNAL_PLACES_COUNT", "{n} places discovered", "Đã khám phá {n} địa điểm")
s("JOURNAL_NO_PLACES", "Explore the quarter to fill this page.", "Hãy khám phá khu phố để lấp đầy trang này.")
s("JOURNAL_REPUTATION", "Reputation", "Danh tiếng")
s("JOURNAL_ACHIEVEMENTS", "Achievements", "Thành tựu")
s("JOURNAL_STATS", "Little numbers", "Vài con số")
s("JOURNAL_ATTRIBUTES", "Attributes", "Thuộc tính")
s("STAT_DAYS", "Days in Hàng Mây", "Số ngày ở Hàng Mây")
s("STAT_PLAYTIME", "Time played", "Thời gian chơi")
s("STAT_KNOCKED", "Things knocked off ledges", "Đồ bị hất khỏi bờ tường")
s("STAT_NAPS", "Naps taken", "Số giấc ngủ")
s("STAT_TERRITORY", "Territory marked", "Lãnh thổ đã đánh dấu")
s("STAT_PREY", "Prey caught", "Con mồi đã bắt")
s("STAT_CAPS", "Bottle caps", "Nắp chai")
s("STAT_MEMORIES", "Memories found", "Kỷ niệm tìm thấy")
s("ACH_LOCKED", "Not yet", "Chưa đạt")

# --- map ---------------------------------------------------------------------------------------
s("MAP_TITLE", "Hàng Mây", "Hàng Mây")
s("MAP_SUBTITLE", "Map of the old quarter", "Bản đồ phố cũ")
s("MAP_YOU", "Cam", "Cam")
s("MAP_QUEST", "Tracked quest", "Nhiệm vụ đang theo dõi")
s("MAP_PLACE", "Discovered place", "Địa điểm đã khám phá")
s("MAP_NAP", "Nap spot", "Chỗ ngủ")
s("MAP_HOME", "Grandma Tư's tea stall", "Quán trà bà Tư")
s("MAP_LEGEND", "Legend", "Chú thích")
s("MAP_NO_CITY", "The map fills in as Cam explores the city.", "Bản đồ sẽ hiện ra khi Cam đi khám phá phố.")
s("MAP_UNEXPLORED", "Unexplored", "Chưa khám phá")

# --- settings ----------------------------------------------------------------------------------
s("SETTINGS_TITLE", "Settings", "Cài đặt")
s("SET_TAB_GRAPHICS", "Graphics", "Đồ họa")
s("SET_TAB_AUDIO", "Sound", "Âm thanh")
s("SET_TAB_CONTROLS", "Controls", "Điều khiển")
s("SET_TAB_GAMEPLAY", "Gameplay", "Lối chơi")
s("SET_TAB_GRAPHICS_DESC", "Picture quality and performance. Changes apply immediately.", "Chất lượng hình ảnh và hiệu năng. Thay đổi có hiệu lực ngay.")
s("SET_TAB_AUDIO_DESC", "Volumes of the music, the city and the interface.", "Âm lượng nhạc nền, tiếng phố và giao diện.")
s("SET_TAB_CONTROLS_DESC", "Camera feel and every key and button. Select a binding and press the new key.", "Cảm giác camera và mọi phím bấm. Chọn một phím rồi bấm phím mới.")
s("SET_TAB_GAMEPLAY_DESC", "Language, hints and the interface.", "Ngôn ngữ, gợi ý và giao diện.")
s("SET_HDR_DISPLAY", "Display", "Hiển thị")
s("SET_HDR_RESOLUTION", "Resolution & anti-aliasing", "Độ phân giải & khử răng cưa")
s("SET_HDR_LIGHTING", "Light & atmosphere", "Ánh sáng & bầu không khí")
s("SET_HDR_DETAIL", "Detail", "Chi tiết")
s("SET_HDR_VOLUME", "Volume", "Âm lượng")
s("SET_HDR_SUBTITLES", "Subtitles", "Phụ đề")
s("SET_HDR_CAMERA", "Camera", "Camera")
s("SET_HDR_LANGUAGE", "Language", "Ngôn ngữ")
s("SET_HDR_INTERFACE", "Interface", "Giao diện")
s("SET_HDR_RESET", "Defaults", "Mặc định")

SET = [
    ("SET_QUALITY", "Quality preset", "Mức chất lượng",
     "Sets every graphics option at once. Changing a single option below switches to Custom.",
     "Đặt mọi tùy chọn đồ họa cùng lúc. Đổi riêng một tùy chọn bên dưới sẽ chuyển sang Tùy chỉnh."),
    ("SET_FULLSCREEN", "Fullscreen", "Toàn màn hình", "Fill the whole screen.", "Hiển thị kín màn hình."),
    ("SET_VSYNC", "V-Sync", "Đồng bộ dọc (V-Sync)", "Prevents tearing by matching the display's refresh rate.",
     "Chống xé hình bằng cách khớp với tần số quét của màn hình."),
    ("SET_MAX_FPS", "Frame rate limit", "Giới hạn khung hình", "Caps frames per second to save power and heat.",
     "Giới hạn số khung hình mỗi giây để tiết kiệm điện và đỡ nóng máy."),
    ("SET_FOV", "Field of view", "Góc nhìn (FOV)", "How wide the camera sees. First-person adds a little more for cat eyes.",
     "Độ rộng tầm nhìn của camera. Góc nhìn thứ nhất rộng hơn một chút như mắt mèo."),
    ("SET_RENDER_SCALE", "Render scale", "Tỉ lệ kết xuất", "Renders the 3D scene at a lower resolution and upscales it. Lower = faster.",
     "Kết xuất cảnh 3D ở độ phân giải thấp hơn rồi phóng lên. Càng thấp càng nhanh."),
    ("SET_UPSCALER", "Upscaler", "Bộ nâng độ phân giải", "How the image is scaled up when render scale is below 100%. FSR 2 is sharpest.",
     "Cách phóng ảnh khi tỉ lệ kết xuất dưới 100%. FSR 2 sắc nét nhất."),
    ("SET_FSR_SHARPNESS", "Upscaler sharpness", "Độ sắc khi nâng", "Sharpening applied by FSR. 0 is sharpest.",
     "Độ làm nét của FSR. 0 là sắc nhất."),
    ("SET_AA", "Anti-aliasing", "Khử răng cưa", "Smooths jagged edges. TAA is the cleanest for fur and wires.",
     "Làm mượt cạnh răng cưa. TAA mịn nhất cho lông mèo và dây điện."),
    ("SET_SDFGI", "Global illumination", "Chiếu sáng toàn cục", "Light bouncing between walls and streets (SDFGI). Beautiful, expensive.",
     "Ánh sáng dội giữa tường và phố (SDFGI). Rất đẹp nhưng nặng."),
    ("SET_SSAO", "Ambient occlusion", "Che sáng môi trường", "Soft contact shadows in corners and under objects (SSAO).",
     "Bóng mềm ở góc tường và dưới đồ vật (SSAO)."),
    ("SET_SSIL", "Indirect light", "Ánh sáng gián tiếp", "Short-range colour bleeding between nearby surfaces (SSIL).",
     "Màu sắc loang nhẹ giữa các bề mặt gần nhau (SSIL)."),
    ("SET_SSR", "Reflections", "Phản chiếu", "Screen-space reflections on wet streets and puddles (SSR).",
     "Phản chiếu trên mặt đường ướt và vũng nước (SSR)."),
    ("SET_VOLFOG", "Volumetric fog", "Sương khói thể tích", "Light shafts through alleys and humid haze.",
     "Những vệt nắng xuyên qua ngõ và hơi ẩm lơ lửng."),
    ("SET_SHADOWS", "Shadow quality", "Chất lượng bóng đổ", "Resolution and softness of shadows.",
     "Độ phân giải và độ mềm của bóng đổ."),
    ("SET_FUR", "Fur detail", "Chi tiết lông", "Number of fur shell layers on cats. More layers = fluffier.",
     "Số lớp lông trên mèo. Nhiều lớp hơn thì mượt hơn."),
    ("SET_LOD", "Detail distance", "Khoảng cách chi tiết", "How far away models keep their full detail.",
     "Khoảng cách mà mô hình vẫn giữ đủ chi tiết."),
    ("SET_ANISO", "Texture filtering", "Lọc kết cấu", "Keeps streets and roof tiles sharp at grazing angles.",
     "Giữ mặt đường và mái ngói sắc nét khi nhìn xiên."),
    ("SET_MOTION_BLUR", "Motion blur", "Nhòe chuyển động", "Blur during fast camera movement.", "Làm nhòe khi camera chuyển động nhanh."),
    ("SET_FILM_GRAIN", "Film grain", "Hạt phim", "A gentle analogue grain over the image.", "Một lớp hạt phim nhẹ trên hình ảnh."),
    ("SET_RESET_TAB", "Reset this tab", "Khôi phục thẻ này", "Restores the defaults of this tab only.",
     "Chỉ khôi phục mặc định cho thẻ này."),
    ("SET_VOL_MASTER", "Master volume", "Âm lượng tổng", "Everything at once.", "Toàn bộ âm thanh."),
    ("SET_VOL_MUSIC", "Music", "Nhạc nền", "Đàn tranh, đàn bầu and sáo trúc.", "Đàn tranh, đàn bầu và sáo trúc."),
    ("SET_VOL_SFX", "Sound effects", "Hiệu ứng", "Paws, meows, knocks and splashes.", "Tiếng bước chân, tiếng meo, đồ rơi, nước bắn."),
    ("SET_VOL_AMBIENCE", "City ambience", "Âm thanh phố", "Motorbikes, vendors, rain, birds and geckos.",
     "Xe máy, người bán hàng, mưa, chim chóc và thạch sùng."),
    ("SET_VOL_UI", "Interface", "Giao diện", "Menu and notification sounds.", "Âm thanh menu và thông báo."),
    ("SET_SUBTITLES", "Subtitles", "Phụ đề", "Show what people say around Cam.", "Hiện lời mọi người nói quanh Cam."),
    ("SET_SUBTITLE_SIZE", "Subtitle size", "Cỡ phụ đề", "Text size of subtitles and dialogue.", "Cỡ chữ của phụ đề và hội thoại."),
    ("SET_MOUSE_SENS", "Mouse sensitivity", "Độ nhạy chuột", "How fast the camera turns with the mouse.", "Tốc độ xoay camera theo chuột."),
    ("SET_PAD_SENS", "Gamepad sensitivity", "Độ nhạy tay cầm", "How fast the camera turns with the right stick.", "Tốc độ xoay camera bằng cần phải."),
    ("SET_INVERT_Y", "Invert vertical look", "Đảo trục dọc", "Push up to look down.", "Đẩy lên để nhìn xuống."),
    ("SET_INVERT_X", "Invert horizontal look", "Đảo trục ngang", "Push right to look left.", "Đẩy sang phải để nhìn sang trái."),
    ("SET_VIBRATION", "Vibration", "Rung", "Gamepad rumble on landings and purring.", "Tay cầm rung khi tiếp đất và khi gừ gừ."),
    ("SET_CAMERA_DEFAULT", "Default camera", "Góc nhìn mặc định", "The view Cam starts in. Switch any time with the camera button.",
     "Góc nhìn khi bắt đầu. Đổi bất cứ lúc nào bằng nút camera."),
    ("SET_HEAD_BOB", "Head bob", "Rung đầu khi đi", "How much the first-person view sways with Cam's steps.",
     "Mức góc nhìn thứ nhất lắc theo bước chân của Cam."),
    ("SET_AUTO_CENTER", "Auto-centre camera", "Tự căn camera", "The third-person camera drifts behind Cam while walking.",
     "Camera góc nhìn thứ ba tự quay về sau lưng Cam khi đi."),
    ("SET_BINDINGS", "Keys & buttons", "Phím & nút", "", ""),
    ("SET_RESET_BINDINGS", "Reset keys & buttons", "Khôi phục phím bấm", "Restores the original bindings.", "Trả lại các phím bấm ban đầu."),
    ("SET_LANGUAGE", "Language", "Ngôn ngữ", "Language of all text.", "Ngôn ngữ của toàn bộ chữ."),
    ("SET_HINTS", "Hints & prompts", "Gợi ý & nhắc phím", "Button prompts and gentle tips.", "Nhắc phím và các gợi ý nhẹ nhàng."),
    ("SET_COMPASS", "Compass", "La bàn", "The compass strip at the top of the screen.", "Dải la bàn ở đầu màn hình."),
    ("SET_TEXT_SPEED", "Text speed", "Tốc độ chữ", "How fast dialogue text appears.", "Tốc độ hiện chữ trong hội thoại."),
    ("SET_UI_SCALE", "Interface scale", "Cỡ giao diện", "Size of menus and the HUD.", "Kích cỡ menu và HUD."),
    ("SET_HUD_OPACITY", "HUD opacity", "Độ đậm HUD", "How strongly the HUD shows over the city.", "Độ rõ của HUD trên nền phố."),
    ("SET_RESET_ALL", "Reset all settings", "Khôi phục mọi cài đặt", "Every option and binding back to its default.",
     "Mọi tùy chọn và phím bấm trở về mặc định."),
]
for key, en, vi, den, dvi in SET:
    s(key, en, vi)
    if den:
        s(key + "_DESC", den, dvi)
s("SET_BINDINGS_DESC", "Select a binding, then press the new key or button.", "Chọn một phím, rồi bấm phím hoặc nút mới.")
s("SET_REBIND_DESC", "Left: keyboard & mouse. Right: gamepad. Select one and press the new key.",
  "Trái: bàn phím & chuột. Phải: tay cầm. Chọn rồi bấm phím mới.")
s("SET_REBIND_PROMPT", "Press a new key for “{action}”… (Esc cancels)", "Bấm phím mới cho “{action}”… (Esc để hủy)")
s("SET_REBIND_CONFLICT", "Also used by “{action}”.", "Phím này cũng đang dùng cho “{action}”.")
s("SET_QUALITY_CUSTOM_NOTE", "Your own mix of options.", "Kết hợp tùy chọn của riêng bạn.")
s("SET_EFFECTS_ON", "Effects", "Hiệu ứng")
s("SET_SHORT_SDFGI", "GI", "GI")
s("SET_SHORT_SSR", "reflections", "phản chiếu")
s("SET_SHORT_SSAO", "AO", "AO")
s("SET_SHORT_SSIL", "indirect light", "ánh sáng gián tiếp")
s("SET_SHORT_VOLUMETRIC_FOG", "volumetric fog", "sương thể tích")
s("SET_FPS_UNLIMITED", "Unlimited", "Không giới hạn")
s("SET_FUR_OFF", "Off", "Tắt")
s("SET_FUR_N", "{n} layers", "{n} lớp")
s("Q_LOW", "Low", "Thấp")
s("Q_MEDIUM", "Medium", "Trung bình")
s("Q_HIGH", "High", "Cao")
s("Q_ULTRA", "Ultra", "Cực cao")
s("Q_CUSTOM", "Custom", "Tùy chỉnh")
s("UPS_OFF", "Off (bilinear)", "Tắt (song tuyến)")
s("UPS_FSR", "AMD FSR 1", "AMD FSR 1")
s("UPS_FSR2", "AMD FSR 2", "AMD FSR 2")
s("AA_OFF", "Off", "Tắt")
s("AA_FXAA", "FXAA", "FXAA")
s("AA_SMAA", "SMAA", "SMAA")
s("AA_TAA", "TAA", "TAA")
s("LOD_NEAR", "Near", "Gần")
s("LOD_MEDIUM", "Medium", "Vừa")
s("LOD_FAR", "Far", "Xa")
s("LOD_VERY_FAR", "Very far", "Rất xa")
s("SIZE_SMALL", "Small", "Nhỏ")
s("SIZE_MEDIUM", "Medium", "Vừa")
s("SIZE_LARGE", "Large", "Lớn")
s("CAM_TPP", "Third person", "Góc nhìn thứ ba")
s("CAM_FPP", "First person (cat eyes)", "Góc nhìn thứ nhất (mắt mèo)")
s("KEY_MOUSE_LEFT", "Left click", "Chuột trái")
s("KEY_MOUSE_RIGHT", "Right click", "Chuột phải")
s("KEY_MOUSE_MIDDLE", "Middle click", "Chuột giữa")
s("KEY_WHEEL_UP", "Wheel up", "Lăn lên")
s("KEY_WHEEL_DOWN", "Wheel down", "Lăn xuống")

ACTIONS = {
    "move_forward": ("Move forward", "Đi tới"), "move_back": ("Move back", "Lùi lại"),
    "move_left": ("Move left", "Sang trái"), "move_right": ("Move right", "Sang phải"),
    "jump": ("Jump (hold to aim)", "Nhảy (giữ để ngắm)"), "sprint": ("Run", "Chạy"), "sneak": ("Sneak", "Rón rén"),
    "interact": ("Interact", "Tương tác"), "pickup_drop": ("Pick up / drop", "Ngậm / nhả"), "meow": ("Meow", "Kêu meo"),
    "swipe": ("Swipe", "Cào"), "aim_jump": ("Aim jump", "Ngắm nhảy"), "cat_sense": ("Cat sense", "Giác quan mèo"),
    "sit_groom": ("Sit / groom", "Ngồi / liếm lông"), "toggle_camera": ("Switch camera", "Đổi góc nhìn"),
    "inventory": ("Belongings", "Đồ đạc"), "journal": ("Journal", "Nhật ký"), "map": ("Map", "Bản đồ"),
    "pause": ("Pause menu", "Tạm dừng"), "quick_save": ("Quick save", "Lưu nhanh"), "quick_load": ("Quick load", "Tải nhanh"),
    "screenshot": ("Screenshot", "Chụp màn hình"), "look_up": ("Look up", "Nhìn lên"), "look_down": ("Look down", "Nhìn xuống"),
    "look_left": ("Look left", "Nhìn trái"), "look_right": ("Look right", "Nhìn phải"), "zoom_in": ("Zoom in", "Phóng to"),
    "zoom_out": ("Zoom out", "Thu nhỏ"),
}
for k, (en, vi) in ACTIONS.items():
    s("ACTION_" + k.upper(), en, vi)

# --- credits -----------------------------------------------------------------------------------
s("CREDITS_TITLE", "Credits", "Đội ngũ")
s("CREDITS_A_GAME_BY", "a game by", "một trò chơi của")
s("CREDITS_DIRECTION", "Direction", "Chỉ đạo")
s("CREDITS_DIRECTION_BODY", "The Mái Ngói lead team", "Nhóm chỉ đạo Xưởng Mái Ngói")
s("CREDITS_DESIGN", "Game design & story", "Thiết kế & cốt truyện")
s("CREDITS_DESIGN_BODY", "Đêm Trăng Rằm — the Full-Moon Night", "Đêm Trăng Rằm")
s("CREDITS_CAT", "Cam, the cat", "Chú mèo Cam")
s("CREDITS_CAT_BODY", "Sculpt, fur, rig and 33 animations — the cat team", "Tạc hình, lông, khung xương và 33 hoạt ảnh — tổ mèo")
s("CREDITS_CITY", "The old quarter", "Phố cũ")
s("CREDITS_CITY_BODY", "Shophouses, landmarks, street props, vehicles and trees — the city teams",
  "Nhà ống, công trình, đồ vật trên phố, xe cộ và cây xanh — các tổ dựng phố")
s("CREDITS_PLAYER", "Being a cat", "Làm một chú mèo")
s("CREDITS_PLAYER_BODY", "Movement, jumping, climbing, cameras and cat-sense — the player team",
  "Di chuyển, nhảy, leo trèo, camera và giác quan mèo — tổ nhân vật")
s("CREDITS_SYSTEMS", "Systems", "Hệ thống")
s("CREDITS_SYSTEMS_BODY", "Vitals, skills, quests, dialogue and saves — the systems team",
  "Sinh lực, kỹ năng, nhiệm vụ, hội thoại và lưu trữ — tổ hệ thống")
s("CREDITS_LIFE", "A living neighbourhood", "Khu phố sống động")
s("CREDITS_LIFE_BODY", "People, dogs, crows, pigeons and traffic — the world-life team",
  "Con người, chó, quạ, bồ câu và xe cộ — tổ đời sống")
s("CREDITS_AUDIO", "Sound & music", "Âm thanh & âm nhạc")
s("CREDITS_AUDIO_BODY", "Every sound synthesised from scratch — đàn tranh, đàn bầu, sáo trúc and the city itself",
  "Mọi âm thanh đều được tổng hợp từ đầu — đàn tranh, đàn bầu, sáo trúc và chính tiếng phố")
s("CREDITS_UI", "Interface", "Giao diện")
s("CREDITS_UI_BODY", "Menus, HUD, icons and lettering — the interface team", "Menu, HUD, biểu tượng và chữ — tổ giao diện")
s("CREDITS_TOOLS", "Made with", "Công cụ")
s("CREDITS_TOOLS_BODY", "Godot Engine 4.7 (MIT licence) · Blender 5.2 (GPL) · Python, NumPy & Pillow",
  "Godot Engine 4.7 (giấy phép MIT) · Blender 5.2 (GPL) · Python, NumPy & Pillow")
s("CREDITS_FONTS", "Typefaces", "Phông chữ")
s("CREDITS_FONTS_BODY", "Be Vietnam Pro · Playfair Display · Lora — SIL Open Font License 1.1",
  "Be Vietnam Pro · Playfair Display · Lora — SIL Open Font License 1.1")
s("CREDITS_THANKS", "With thanks", "Cảm ơn")
s("CREDITS_THANKS_BODY", "Every orange cat asleep on a warm rooftop, and every grandma who leaves a bowl out for them.",
  "Mọi chú mèo cam đang ngủ trên mái nhà ấm, và mọi bà cụ vẫn để sẵn một bát cơm cho chúng.")
s("CREDITS_ORIGINAL", "Hàng Mây is a fictional place. All characters, brands and signs are invented.",
  "Hàng Mây là một nơi hư cấu. Mọi nhân vật, nhãn hiệu và biển hiệu đều do chúng tôi tưởng tượng.")
s("CREDITS_END", "Thank you for playing.", "Cảm ơn bạn đã chơi.")

# --- loading tips ------------------------------------------------------------------------------
TIPS = [
    ("Hold Jump to crouch and aim, release to leap. The longer you hold, the farther Cam goes.",
     "Giữ nút Nhảy để thu mình ngắm, thả ra để bật. Giữ càng lâu Cam nhảy càng xa."),
    ("Cat sense reveals scents, sounds and hidden memories nearby — at a small cost of energy.",
     "Giác quan mèo làm hiện mùi, âm thanh và kỷ niệm ẩn gần đó — tốn một chút năng lượng."),
    ("Awnings keep your fur dry. A wet cat gets cold fast.", "Mái hiên giữ lông khô. Mèo ướt sẽ lạnh rất nhanh."),
    ("Napping restores energy and passes time. Every new nap spot is worth some experience.",
     "Ngủ giúp hồi năng lượng và cho thời gian trôi. Mỗi chỗ ngủ mới đều cho thêm kinh nghiệm."),
    ("A cat carries only one thing in its mouth. Everything else waits in Cam's den.",
     "Mèo chỉ ngậm được một thứ. Mọi thứ khác nằm chờ trong ổ của Cam."),
    ("The crows of Hàng Mây trade in bottle caps. Keep an eye on gutters and café tables.",
     "Bầy quạ Hàng Mây buôn bán bằng nắp chai. Để mắt tới rãnh nước và bàn quán cà phê."),
    ("Sit and meow politely — charm opens doors (and fish stalls).", "Ngồi xuống và meo thật lễ phép — sự đáng yêu mở được nhiều cánh cửa (và cả sạp cá)."),
    ("Vện the market dog barks a lot but never bites. Still, sneaking is quieter.",
     "Chó Vện ở chợ sủa nhiều nhưng không bao giờ cắn. Dù vậy, rón rén vẫn êm hơn."),
    ("Switch to first person to see the quarter through Cam's eyes — whiskers and all.",
     "Chuyển sang góc nhìn thứ nhất để nhìn phố bằng mắt Cam — có cả ria mép."),
    ("Some things on ledges simply must be knocked off. People will have opinions.",
     "Có những thứ trên bờ tường sinh ra là để bị hất xuống. Người ta sẽ có ý kiến đấy."),
    ("AC units, awnings and balconies are stairs if you are a cat.", "Cục nóng điều hòa, mái hiên và ban công đều là cầu thang nếu bạn là mèo."),
    ("Power lines are walkable. Move slowly and keep your balance.", "Dây điện cũng đi được. Bước chậm và giữ thăng bằng."),
    ("Scratch posts and rubbing spots mark your territory — the rooftop cats notice.",
     "Cột cào và chỗ cọ người giúp đánh dấu lãnh thổ — hội mèo mái nhà để ý cả đấy."),
    ("Twelve old photographs are hidden around town. Each one tells a little of Grandma Tư's life.",
     "Mười hai tấm ảnh cũ nằm rải rác trong phố. Mỗi tấm kể một chút về cuộc đời bà Tư."),
    ("Hungry? Grandma's bowl, Uncle Sáu's bánh mì cart and the fish market all have something for a polite cat.",
     "Đói à? Bát cơm của bà, xe bánh mì chú Sáu và chợ cá đều có gì đó cho một chú mèo lễ phép."),
    ("If Cam faints he wakes up at his last nap spot, minus a few bottle caps.",
     "Nếu Cam ngất, chú sẽ tỉnh dậy ở chỗ ngủ gần nhất, mất vài nắp chai."),
    ("Each level brings a skill point and an attribute point. Spend them in Skills.",
     "Mỗi cấp cho một điểm kỹ năng và một điểm thuộc tính. Dùng chúng trong mục Kỹ năng."),
    ("The journal keeps your quests, memories and every place you have found.",
     "Nhật ký lưu lại nhiệm vụ, kỷ niệm và mọi nơi bạn đã tìm thấy."),
    ("Sneaking makes almost no sound. Running on tin roofs makes a lot.", "Rón rén gần như không gây tiếng động. Chạy trên mái tôn thì ồn lắm."),
    ("The market opens at dawn and packs up at noon — come early for the freshest fish.",
     "Chợ mở lúc rạng sáng và dọn hàng buổi trưa — đến sớm để có cá tươi nhất."),
    ("At night the street lights hum and the geckos sing. Some cats only come out then.",
     "Ban đêm đèn đường rì rầm và thạch sùng tặc lưỡi. Có những chú mèo chỉ ra ngoài lúc ấy."),
    ("Rain makes streets shine and roofs slippery. Look for dry spots under the eaves.",
     "Mưa làm mặt đường bóng loáng và mái nhà trơn trượt. Tìm chỗ khô dưới mái hiên nhé."),
    ("Mid-Autumn is coming: three days until the star lanterns light up the quarter.",
     "Trung thu sắp tới: còn ba ngày nữa là đèn ông sao thắp sáng khắp phố."),
    ("Lost? The map shows discovered places, and the compass points to your tracked quest.",
     "Lạc đường? Bản đồ hiện các nơi đã khám phá, còn la bàn chỉ tới nhiệm vụ đang theo dõi."),
]
for i, (en, vi) in enumerate(TIPS):
    s("TIP_%02d" % (i + 1), en, vi)


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        w.writerow(["keys", "en", "vi"])
        for k, (en, vi) in S.items():
            w.writerow([k, en, vi])
    print("wrote %d ui strings to %s" % (len(S), OUT))


if __name__ == "__main__":
    main()
