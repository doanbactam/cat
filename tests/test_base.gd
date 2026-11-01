extends RefCounted
## Minimal test base. Test files: tests/test_*.gd extending this; methods named test_*.
## Access autoloads via `tree.root.get_node("GameState")` or the global names.

var tree: SceneTree
var _failures: Array[String] = []
var _current := ""

func before_each() -> void: pass
func after_each() -> void: pass

func assert_true(cond: bool, msg := "") -> void:
	if not cond: _failures.append("%s: expected true. %s" % [_current, msg])

func assert_false(cond: bool, msg := "") -> void:
	if cond: _failures.append("%s: expected false. %s" % [_current, msg])

func assert_eq(a, b, msg := "") -> void:
	if typeof(a) != typeof(b) and not ((typeof(a) in [TYPE_INT, TYPE_FLOAT]) and (typeof(b) in [TYPE_INT, TYPE_FLOAT])):
		_failures.append("%s: type mismatch %s vs %s. %s" % [_current, str(a), str(b), msg]); return
	if a != b: _failures.append("%s: expected %s == %s. %s" % [_current, str(a), str(b), msg])

func assert_near(a: float, b: float, eps := 0.001, msg := "") -> void:
	if absf(a - b) > eps: _failures.append("%s: expected %f ~= %f. %s" % [_current, a, b, msg])

func assert_not_null(v, msg := "") -> void:
	if v == null: _failures.append("%s: expected non-null. %s" % [_current, msg])
