extends SceneTree
## Renders the SVG icon sources (assets/ui/icons/src/<group>/*.svg, written by gen_icons.py) to
## PNG with Godot's SVG rasteriser, and writes .import files that enable mipmaps so the icons
## stay crisp when the UI shows them small. Also writes a contact sheet to qa/out/ui/icons_<group>.png.
## Run: tools/godot_lock.sh godot --headless --path . --script res://scripts/ui/build/rasterize_icons.gd </dev/null

const SRC := "res://assets/ui/icons/src/"
const DST := "res://assets/ui/icons/"
## group -> output pixel size
const SIZES := {"glyphs": 128, "actions": 128, "skills": 128, "items": 256}

const IMPORT_TEMPLATE := """[remap]

importer="texture"
type="CompressedTexture2D"

[deps]

source_file="%s"

[params]

compress/mode=0
compress/high_quality=false
compress/lossy_quality=0.7
compress/hdr_compression=1
compress/normal_map=0
compress/channel_pack=0
mipmaps/generate=true
mipmaps/limit=-1
roughness/mode=0
roughness/src_normal=""
process/fix_alpha_border=true
process/premult_alpha=false
process/normal_map_invert_y=false
process/hdr_as_srgb=false
process/hdr_clamp_exposure=false
process/size_limit=0
detect_3d/compress_to=0
"""


func _init() -> void:
	_run.call_deferred()


func _run() -> void:
	var total := 0
	for group: String in SIZES:
		var size: int = SIZES[group]
		var dir := DirAccess.open(SRC + group)
		if dir == null:
			continue
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(DST + group))
		var files := dir.get_files()
		var sheet_imgs: Array[Image] = []
		for f in files:
			if not f.ends_with(".svg"):
				continue
			var svg := FileAccess.get_file_as_string(SRC + group + "/" + f)
			var native := _svg_size(svg)
			var img := Image.new()
			var err := img.load_svg_from_string(svg, float(size) / native)
			if err != OK:
				printerr("ICON FAIL ", group, "/", f, " ", error_string(err))
				continue
			if img.get_width() != size:
				img.resize(size, size, Image.INTERPOLATE_LANCZOS)
			var out := DST + group + "/" + f.get_basename() + ".png"
			img.save_png(ProjectSettings.globalize_path(out))
			var imp := ProjectSettings.globalize_path(out + ".import")
			if not FileAccess.file_exists(imp):
				var fi := FileAccess.open(imp, FileAccess.WRITE)
				fi.store_string(IMPORT_TEMPLATE % out)
				fi.close()
			sheet_imgs.append(img)
			total += 1
		_contact_sheet(group, sheet_imgs, files)
	print("ICONS rasterised: ", total)
	quit(0)


func _svg_size(svg: String) -> float:
	var i := svg.find("viewBox=\"")
	if i < 0:
		return 64.0
	var parts := svg.substr(i + 9, 40).split("\"")[0].split(" ")
	return float(parts[2]) if parts.size() >= 4 else 64.0


func _contact_sheet(group: String, imgs: Array[Image], _names: PackedStringArray) -> void:
	if imgs.is_empty():
		return
	var cell := 96
	var cols := 12
	var rows := int(ceil(float(imgs.size()) / cols))
	var sheet := Image.create(cols * cell, rows * cell, false, Image.FORMAT_RGBA8)
	sheet.fill(Color(0.16, 0.12, 0.1, 1.0) if group == "items" else Color(0.11, 0.09, 0.08, 1.0))
	for i in imgs.size():
		var im := imgs[i].duplicate() as Image
		im.resize(cell - 16, cell - 16, Image.INTERPOLATE_LANCZOS)
		var x := (i % cols) * cell + 8
		var y := (i / cols) * cell + 8
		sheet.blend_rect(im, Rect2i(0, 0, im.get_width(), im.get_height()), Vector2i(x, y))
	var qa := ProjectSettings.globalize_path("res://qa/out/ui/")
	DirAccess.make_dir_recursive_absolute(qa)
	sheet.save_png(qa + "icons_%s.png" % group)
