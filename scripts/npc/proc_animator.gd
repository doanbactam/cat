extends RefCounted
## Procedural animation for the stand-in rigs built by standin_builder.gd (owner: world-life).
## Same clip vocabulary as the creatures contract so the GLB path and the stand-in path are
## interchangeable: humans idle/walk/run/sit/talk/sell/pet_cat/shoo (+ ride, cycle, umbrella,
## squat, wave, look_down), dog idle/walk/run/bark/sleep/sit, birds idle/peck/walk/fly/takeoff/land,
## mouse idle/run, gecko idle/crawl. Poses blend exponentially; gait phase follows real speed.

var kind := "human"
var rig: Dictionary = {}
var anim: StringName = &"idle"
var speed := 0.0
var phase := 0.0
var t := 0.0
var holding_umbrella := false
var head_yaw := 0.0      # radians, look-at offset (humans, dog)
var head_pitch := 0.0
var stride := 1.3        # metres per full gait cycle
var blend_rate := 14.0
var seed_offset := 0.0

var _rest: Dictionary = {}       # name -> Vector3 rotation
var _rest_pos: Dictionary = {}   # name -> Vector3 position
var _cur: Dictionary = {}
var _cur_pos: Dictionary = {}


func setup(model: Node3D) -> void:
	kind = str(model.get_meta(&"rig_kind", "human"))
	rig = model.get_meta(&"rig", {})
	seed_offset = randf() * 10.0
	for n: String in rig:
		var p := rig[n] as Node3D
		if p == null:
			continue
		_rest[n] = p.rotation
		_rest_pos[n] = p.position
		_cur[n] = Vector3.ZERO
		_cur_pos[n] = Vector3.ZERO
	match kind:
		"human":
			stride = 1.25 * float(model.get_meta(&"height", 1.65)) / 1.65
		"dog":
			stride = 1.0
		"bird":
			stride = 0.16
		"mouse":
			stride = 0.12
		"gecko":
			stride = 0.08


func play(a: StringName) -> void:
	anim = a


func tick(dt: float) -> void:
	t += dt
	var cyc := speed / maxf(stride, 0.01)
	if anim in [&"walk", &"run", &"trot", &"crawl", &"cycle"]:
		phase = fmod(phase + dt * maxf(cyc, 0.6), 1.0)
	var target: Dictionary = {}
	var tpos: Dictionary = {}
	match kind:
		"human":
			_human(target, tpos)
		"dog":
			_dog(target, tpos)
		"bird":
			_bird(target, tpos)
		"mouse":
			_mouse(target, tpos)
		"gecko":
			_gecko(target, tpos)
	var k := 1.0 - exp(-blend_rate * dt)
	for n: String in _cur:
		var p := rig[n] as Node3D
		if p == null or not is_instance_valid(p):
			continue
		var tr: Vector3 = target.get(n, Vector3.ZERO)
		var tp: Vector3 = tpos.get(n, Vector3.ZERO)
		_cur[n] = (_cur[n] as Vector3).lerp(tr, k)
		_cur_pos[n] = (_cur_pos[n] as Vector3).lerp(tp, k)
		p.rotation = (_rest[n] as Vector3) + (_cur[n] as Vector3)
		p.position = (_rest_pos[n] as Vector3) + (_cur_pos[n] as Vector3)


# ------------------------------------------------------------------------------------------

func _human(r: Dictionary, p: Dictionary) -> void:
	var s := sin(phase * TAU)
	var c := cos(phase * TAU)
	var breathe := sin((t + seed_offset) * 1.6) * 0.012
	r["Spine"] = Vector3(breathe, 0, 0)
	r["Head"] = Vector3(head_pitch, head_yaw * 0.7, 0)
	r["Neck"] = Vector3(0, head_yaw * 0.3, 0)
	match anim:
		&"walk", &"run":
			var run := anim == &"run"
			var amp := 0.42 if run else 0.36
			r["HipL"] = Vector3(-s * amp, 0, 0)
			r["HipR"] = Vector3(s * amp, 0, 0)
			r["KneeL"] = Vector3(maxf(0.0, -c) * (1.1 if run else 0.65) + 0.05, 0, 0)
			r["KneeR"] = Vector3(maxf(0.0, c) * (1.1 if run else 0.65) + 0.05, 0, 0)
			r["AnkleL"] = Vector3(-maxf(0.0, s) * 0.25, 0, 0)
			r["AnkleR"] = Vector3(-maxf(0.0, -s) * 0.25, 0, 0)
			r["ShoulderL"] = Vector3(s * (0.5 if run else 0.3), 0, 0)
			r["ShoulderR"] = Vector3(-s * (0.5 if run else 0.3), 0, 0)
			r["ElbowL"] = Vector3(-(0.9 if run else 0.25) - maxf(0.0, s) * 0.2, 0, 0)
			r["ElbowR"] = Vector3(-(0.9 if run else 0.25) - maxf(0.0, -s) * 0.2, 0, 0)
			r["Spine"] = Vector3((0.18 if run else 0.04) + breathe, s * 0.06, 0)
			r["Hips"] = Vector3(0, -s * 0.08, c * 0.03)
			p["Hips"] = Vector3(0, -absf(c) * 0.035 + 0.01, 0)
		&"sit", &"sit_idle":
			# Vietnamese low plastic stool (~0.3–0.45 m): deep knee bend
			r["HipL"] = Vector3(-1.55, 0.12, 0)
			r["HipR"] = Vector3(-1.55, -0.12, 0)
			r["KneeL"] = Vector3(1.9, 0, 0)
			r["KneeR"] = Vector3(1.9, 0, 0)
			r["AnkleL"] = Vector3(-0.3, 0, 0)
			r["AnkleR"] = Vector3(-0.3, 0, 0)
			r["Spine"] = Vector3(0.22 + breathe, 0, 0)
			r["ShoulderL"] = Vector3(-0.55, 0, -0.1)
			r["ShoulderR"] = Vector3(-0.55, 0, 0.1)
			r["ElbowL"] = Vector3(-0.9, 0, 0)
			r["ElbowR"] = Vector3(-0.9, 0, 0)
			p["Hips"] = Vector3(0, -_leg_drop(0.42), 0.12)
			if anim == &"sit_idle":
				r["ElbowR"] = Vector3(-1.6 - maxf(0.0, sin(t * 0.7 + seed_offset)) * 0.6, 0, 0)  # sipping tea
		&"pet_cat", &"squat":
			r["HipL"] = Vector3(-1.7, 0.25, 0)
			r["HipR"] = Vector3(-1.4, -0.25, 0)
			r["KneeL"] = Vector3(2.3, 0, 0)
			r["KneeR"] = Vector3(2.1, 0, 0)
			r["AnkleL"] = Vector3(-0.6, 0, 0)
			r["AnkleR"] = Vector3(-0.5, 0, 0)
			r["Spine"] = Vector3(0.65, 0, 0)
			r["Head"] = Vector3(0.35 + head_pitch, head_yaw * 0.5, 0)
			var pet := sin(t * 5.0) * 0.18 if anim == &"pet_cat" else 0.0
			r["ShoulderR"] = Vector3(-0.9 + pet, 0, 0.15)
			r["ElbowR"] = Vector3(-0.3, 0, 0)
			r["ShoulderL"] = Vector3(-0.4, 0, -0.1)
			r["ElbowL"] = Vector3(-1.2, 0, 0)
			p["Hips"] = Vector3(0, -_leg_drop(0.72), -0.05)
		&"shoo":
			var wave := sin(t * 11.0)
			r["ShoulderR"] = Vector3(-1.2 + wave * 0.35, 0, 0.3)
			r["ElbowR"] = Vector3(-0.5 + wave * 0.4, 0, 0)
			r["ShoulderL"] = Vector3(-0.3, 0, -0.35)
			r["ElbowL"] = Vector3(-1.4, 0, 0)
			r["Spine"] = Vector3(0.12, 0, 0)
			r["Head"] = Vector3(0.2 + head_pitch, head_yaw * 0.7, 0)
		&"talk":
			var g := sin(t * 2.3 + seed_offset)
			r["ShoulderR"] = Vector3(-0.45 + g * 0.2, 0, 0.15)
			r["ElbowR"] = Vector3(-1.1 + g * 0.3, 0, 0)
			r["ShoulderL"] = Vector3(-0.15 - g * 0.1, 0, -0.1)
			r["ElbowL"] = Vector3(-0.5, 0, 0)
			r["Head"] = Vector3(sin(t * 3.1) * 0.06 + head_pitch, head_yaw * 0.7 + sin(t * 1.3) * 0.1, 0)
		&"sell":
			var g2 := sin(t * 1.7 + seed_offset)
			r["ShoulderR"] = Vector3(-0.8 + g2 * 0.25, 0, 0.05)
			r["ElbowR"] = Vector3(-1.3, 0, 0)
			r["ShoulderL"] = Vector3(-0.7, 0, -0.05)
			r["ElbowL"] = Vector3(-1.2 + g2 * 0.2, 0, 0)
			r["Spine"] = Vector3(0.18 + breathe, g2 * 0.08, 0)
			r["Head"] = Vector3(0.25 + head_pitch, head_yaw * 0.7, 0)
		&"wave":
			r["ShoulderR"] = Vector3(-2.6, 0, 0.2 + sin(t * 8.0) * 0.25)
			r["ElbowR"] = Vector3(-0.4, 0, 0)
		&"ride":
			r["HipL"] = Vector3(-1.45, 0.25, 0)
			r["HipR"] = Vector3(-1.45, -0.25, 0)
			r["KneeL"] = Vector3(1.3, 0, 0)
			r["KneeR"] = Vector3(1.3, 0, 0)
			r["Spine"] = Vector3(0.12, 0, 0)
			r["ShoulderL"] = Vector3(-1.05, 0, -0.18)
			r["ShoulderR"] = Vector3(-1.05, 0, 0.18)
			r["ElbowL"] = Vector3(-0.35, 0, 0)
			r["ElbowR"] = Vector3(-0.35, 0, 0)
		&"passenger":
			r["HipL"] = Vector3(-1.45, 0.3, 0)
			r["HipR"] = Vector3(-1.45, -0.3, 0)
			r["KneeL"] = Vector3(1.5, 0, 0)
			r["KneeR"] = Vector3(1.5, 0, 0)
			r["ShoulderL"] = Vector3(-0.3, 0, -0.1)
			r["ShoulderR"] = Vector3(-0.3, 0, 0.1)
			r["ElbowL"] = Vector3(-0.8, 0, 0)
			r["ElbowR"] = Vector3(-0.8, 0, 0)
		&"cycle":
			var a := phase * TAU
			r["HipL"] = Vector3(-1.05 - sin(a) * 0.38, 0, 0)
			r["HipR"] = Vector3(-1.05 + sin(a) * 0.38, 0, 0)
			r["KneeL"] = Vector3(1.0 + cos(a) * 0.45, 0, 0)
			r["KneeR"] = Vector3(1.0 - cos(a) * 0.45, 0, 0)
			r["Spine"] = Vector3(0.38, 0, 0)
			r["ShoulderL"] = Vector3(-1.1, 0, -0.1)
			r["ShoulderR"] = Vector3(-1.1, 0, 0.1)
			r["ElbowL"] = Vector3(-0.2, 0, 0)
			r["ElbowR"] = Vector3(-0.2, 0, 0)
		&"look_down":
			r["Head"] = Vector3(0.55, head_yaw * 0.6, 0)
			r["Spine"] = Vector3(0.2, 0, 0)
		_:
			# idle: weight shift, relaxed arms
			var sway := sin((t + seed_offset) * 0.45)
			r["Hips"] = Vector3(0, 0, sway * 0.03)
			r["HipL"] = Vector3(0, 0, -sway * 0.03)
			r["HipR"] = Vector3(0.05, 0, -sway * 0.03)
			r["KneeR"] = Vector3(0.1, 0, 0)
			r["ElbowL"] = Vector3(-0.12, 0, 0)
			r["ElbowR"] = Vector3(-0.12, 0, 0)
	if holding_umbrella and anim not in [&"ride", &"cycle", &"pet_cat", &"shoo"]:
		r["ShoulderR"] = Vector3(-1.0, 0, 0.35)
		r["ElbowR"] = Vector3(-1.45, 0, 0)


func _leg_drop(frac: float) -> float:
	var hips := rig.get("Hips") as Node3D
	if hips == null:
		return 0.4
	return (_rest_pos["Hips"] as Vector3).y * frac


func _dog(r: Dictionary, p: Dictionary) -> void:
	var s := sin(phase * TAU)
	var c := cos(phase * TAU)
	var wag := sin(t * 14.0)
	r["Head"] = Vector3(head_pitch, head_yaw * 0.6, 0)
	r["Neck"] = Vector3(0, head_yaw * 0.4, 0)
	r["Tail"] = Vector3(-0.3, wag * 0.15, 0)
	r["EarL"] = Vector3(0, 0, 0)
	r["EarR"] = Vector3(0, 0, 0)
	match anim:
		&"walk", &"run", &"trot":
			var run := anim == &"run"
			var amp := 0.75 if run else 0.42
			if run:
				# rotary gallop: front pair and back pair in phase
				r["LegFL"] = Vector3(-s * amp, 0, 0)
				r["LegFR"] = Vector3(-sin(phase * TAU + 0.4) * amp, 0, 0)
				r["LegBL"] = Vector3(sin(phase * TAU + PI * 0.9) * amp, 0, 0)
				r["LegBR"] = Vector3(sin(phase * TAU + PI * 0.9 + 0.4) * amp, 0, 0)
				r["Body"] = Vector3(c * 0.12, 0, 0)
				p["Body"] = Vector3(0, absf(s) * 0.05, 0)
				r["Tail"] = Vector3(-0.1, wag * 0.3, 0)
				r["EarL"] = Vector3(-0.6, 0, 0)
				r["EarR"] = Vector3(-0.6, 0, 0)
			else:
				# diagonal trot
				r["LegFL"] = Vector3(-s * amp, 0, 0)
				r["LegBR"] = Vector3(-s * amp, 0, 0)
				r["LegFR"] = Vector3(s * amp, 0, 0)
				r["LegBL"] = Vector3(s * amp, 0, 0)
				p["Body"] = Vector3(0, absf(c) * 0.012, 0)
			for n: String in ["FL", "FR", "BL", "BR"]:
				var leg: Vector3 = r["Leg" + n]
				var bend := maxf(0.0, -leg.x) * 1.2 if n.begins_with("F") else maxf(0.0, leg.x) * -1.2
				r["Knee" + n] = Vector3(bend, 0, 0)
		&"bark":
			var b := maxf(0.0, sin(t * 9.0))
			r["Jaw"] = Vector3(b * 0.55, 0, 0)
			r["Head"] = Vector3(-0.2 - b * 0.15 + head_pitch, head_yaw * 0.6, 0)
			r["Body"] = Vector3(-0.05 - b * 0.05, 0, 0)
			r["LegFL"] = Vector3(-0.15, 0, 0)
			r["LegFR"] = Vector3(-0.15, 0, 0)
			r["Tail"] = Vector3(-0.7, wag * 0.1, 0)
			r["EarL"] = Vector3(-0.3, 0, 0)
			r["EarR"] = Vector3(-0.3, 0, 0)
		&"sit":
			r["Body"] = Vector3(-0.55, 0, 0)
			p["Body"] = Vector3(0, -0.1, -0.06)
			r["LegBL"] = Vector3(-1.2, 0, 0)
			r["LegBR"] = Vector3(-1.2, 0, 0)
			r["KneeBL"] = Vector3(1.8, 0, 0)
			r["KneeBR"] = Vector3(1.8, 0, 0)
			r["LegFL"] = Vector3(0.55, 0, 0)
			r["LegFR"] = Vector3(0.55, 0, 0)
			r["Head"] = Vector3(0.45 + head_pitch, head_yaw * 0.6, 0)
		&"sleep":
			p["Body"] = Vector3(0, -0.26, 0)
			r["Body"] = Vector3(0, 0, 1.35)
			r["Neck"] = Vector3(0.6, 0.6, 0)
			r["Head"] = Vector3(0.3, 0.2, 0)
			r["LegFL"] = Vector3(-0.8, 0, 0)
			r["LegFR"] = Vector3(-0.7, 0, 0)
			r["LegBL"] = Vector3(0.6, 0, 0)
			r["LegBR"] = Vector3(0.7, 0, 0)
			r["Tail"] = Vector3(0.2, 1.0, 0)
			p["Body"] += Vector3(0, sin(t * 1.2) * 0.006, 0)
		_:
			var pant := sin(t * 6.0) * 0.06
			r["Jaw"] = Vector3(0.18 + pant, 0, 0)
			p["Body"] = Vector3(0, pant * 0.05, 0)
			r["Tail"] = Vector3(-0.25, wag * 0.25, 0)


func _bird(r: Dictionary, p: Dictionary) -> void:
	var bob := sin(phase * TAU)
	match anim:
		&"walk":
			# pigeon head-bob: head thrusts forward then holds
			p["Head"] = Vector3(0, 0, (0.02 if fmod(phase * 2.0, 1.0) < 0.5 else -0.005))
			r["LegL"] = Vector3(bob * 0.6, 0, 0)
			r["LegR"] = Vector3(-bob * 0.6, 0, 0)
			r["Body"] = Vector3(0, 0, bob * 0.06)
			r["WingL"] = Vector3.ZERO
			r["WingR"] = Vector3.ZERO
		&"peck":
			var pk := maxf(0.0, sin(t * 7.0 + seed_offset))
			r["Body"] = Vector3(0.55 * pk, 0, 0)
			r["Head"] = Vector3(0.6 * pk, 0, 0)
			r["Tail"] = Vector3(-0.4 * pk, 0, 0)
		&"fly", &"takeoff", &"land":
			var rate := 15.0 if anim != &"fly" else 10.0
			var f := sin(t * rate + seed_offset)
			r["WingL"] = Vector3(0, 0, f * 1.1 + 0.25)
			r["WingR"] = Vector3(0, 0, -f * 1.1 - 0.25)
			r["Body"] = Vector3(-0.35 if anim == &"takeoff" else (0.3 if anim == &"land" else 0.05), 0, 0)
			r["LegL"] = Vector3(-1.0 if anim == &"fly" else 0.0, 0, 0)
			r["LegR"] = Vector3(-1.0 if anim == &"fly" else 0.0, 0, 0)
			r["Tail"] = Vector3(-0.2 if anim == &"land" else 0.1, 0, 0)
		&"glide":
			r["WingL"] = Vector3(0, 0, 0.15)
			r["WingR"] = Vector3(0, 0, -0.15)
			r["LegL"] = Vector3(-1.0, 0, 0)
			r["LegR"] = Vector3(-1.0, 0, 0)
		&"caw":
			var cw := maxf(0.0, sin(t * 6.0))
			r["Head"] = Vector3(-0.4 * cw, 0, 0)
			r["Body"] = Vector3(-0.2 * cw, 0, 0)
			r["WingL"] = Vector3(0, 0, 0.12 * cw)
			r["WingR"] = Vector3(0, 0, -0.12 * cw)
		_:
			var look := sin(t * 0.9 + seed_offset)
			r["Head"] = Vector3(0, (0.7 if look > 0.6 else (-0.7 if look < -0.6 else 0.0)) + head_yaw, 0)
			r["Body"] = Vector3(0, 0, sin(t * 0.5) * 0.02)


func _mouse(r: Dictionary, p: Dictionary) -> void:
	var s := sin(phase * TAU)
	r["Tail"] = Vector3(0.1, sin(t * 3.0) * 0.3, 0)
	r["Tail2"] = Vector3(0, sin(t * 3.0 + 1.0) * 0.4, 0)
	if anim == &"run":
		r["LegFL"] = Vector3(-s * 0.9, 0, 0)
		r["LegFR"] = Vector3(-s * 0.9, 0, 0)
		r["LegBL"] = Vector3(s * 0.9, 0, 0)
		r["LegBR"] = Vector3(s * 0.9, 0, 0)
		r["Body"] = Vector3(s * 0.12, 0, 0)
		p["Body"] = Vector3(0, absf(s) * 0.006, 0)
	else:
		var sniff := sin(t * 18.0) * 0.06
		r["Head"] = Vector3(sniff - 0.1, sin(t * 0.8 + seed_offset) * 0.4, 0)
		if fmod(t + seed_offset, 5.0) < 1.2:
			r["Body"] = Vector3(-0.6, 0, 0)   # rear up on hind legs
			p["Body"] = Vector3(0, 0.01, -0.01)


func _gecko(r: Dictionary, _p: Dictionary) -> void:
	var s := sin(phase * TAU)
	if anim == &"crawl":
		r["LegFL"] = Vector3(0, s * 0.6, 0)
		r["LegBR"] = Vector3(0, s * 0.6, 0)
		r["LegFR"] = Vector3(0, -s * 0.6, 0)
		r["LegBL"] = Vector3(0, -s * 0.6, 0)
		r["Body"] = Vector3(0, s * 0.18, 0)
		r["Tail"] = Vector3(0, -s * 0.35, 0)
	else:
		r["Tail"] = Vector3(0, sin(t * 0.7 + seed_offset) * 0.15, 0)
