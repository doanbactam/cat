extends SceneTree
## Runs all tests/test_*.gd. Usage: tools/run_tests.sh [name-filter]

func _init() -> void:
	_run.call_deferred()

func _run() -> void:
	await process_frame  # let autoloads enter the tree
	var filter := ""
	if OS.get_cmdline_user_args().size() > 0:
		filter = OS.get_cmdline_user_args()[0]
	var total := 0
	var failed := 0
	var files := []
	var d := DirAccess.open("res://tests")
	for f in d.get_files():
		if f.begins_with("test_") and f.ends_with(".gd") and f != "test_base.gd" and (filter == "" or f.contains(filter)):
			files.append(f)
	files.sort()
	for f in files:
		var script := load("res://tests/" + f) as GDScript
		if script == null:
			print("TEST LOAD FAIL ", f); failed += 1; continue
		for m in script.get_script_method_list():
			var name: String = m["name"]
			if not name.begins_with("test_"):
				continue
			var t = script.new()
			t.tree = self
			t._current = f + "::" + name
			t.before_each()
			await t.call(name)  # supports coroutine tests (await inside test_*)
			t.after_each()
			total += 1
			if t._failures.is_empty():
				print("  PASS ", t._current)
			else:
				failed += 1
				for msg in t._failures:
					print("  FAIL ", msg)
	print("TESTS total=%d failed=%d" % [total, failed])
	quit(1 if failed > 0 else 0)
