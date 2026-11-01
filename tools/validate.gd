extends SceneTree
## Loads all project resources to surface parse/load errors headlessly.

var failures := 0
var checked := 0

func _init() -> void:
	_run.call_deferred()

func _run() -> void:
	var filter := ""
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		filter = args[0]
	_scan("res://", filter)
	print("VALIDATE SUMMARY checked=%d failures=%d" % [checked, failures])
	if failures > 0:
		print("VALIDATE FAIL")
	quit(1 if failures > 0 else 0)

func _scan(dir_path: String, filter: String) -> void:
	var d := DirAccess.open(dir_path)
	if d == null:
		return
	d.list_dir_begin()
	var f := d.get_next()
	while f != "":
		if f.begins_with("."):
			f = d.get_next(); continue
		var p := dir_path.path_join(f)
		if d.current_is_dir():
			if f not in ["addons_disabled", "qa", "blender", "docs", "tools"]:
				_scan(p, filter)
		elif filter == "" or p.contains(filter):
			var ext := f.get_extension()
			if ext in ["gd", "tscn", "tres", "glb", "gltf"]:
				_check(p, ext)
		f = d.get_next()

func _check(p: String, ext: String) -> void:
	checked += 1
	if OS.is_stdout_verbose(): print("checking ", p)
	if p == "res://tests/run_tests.gd":
		return
	var res = ResourceLoader.load(p, "", ResourceLoader.CACHE_MODE_REUSE)
	if res == null:
		failures += 1
		print("VALIDATE FAIL load: ", p)
		return
	if ext == "gd":
		var s := res as Script
		# Broken scripts load but cannot instantiate. (Never reload() here: reloading
		# running SceneTree/autoload scripts segfaults.) Abstract classes are allowed.
		if s == null or (not s.can_instantiate() and not s.is_abstract()):
			failures += 1
			print("VALIDATE FAIL script: ", p)
	elif ext == "tscn":
		var ps := res as PackedScene
		if ps == null or not ps.can_instantiate():
			failures += 1
			print("VALIDATE FAIL scene: ", p)
