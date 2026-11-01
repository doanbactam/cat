extends SceneTree
## Generates res://default_bus_layout.tres (audio area). Run:
##   tools/godot_lock.sh godot --headless --path . --script res://tools/audio/make_bus_layout.gd </dev/null
## Buses: Master, Music, SFX, Ambience, UI, Voice (+ reverb send buses Alley, Temple, Interior, Market).
## Buses may only send to buses on their left, so reverb buses come last and send into SFX.

func _init() -> void:
	_run.call_deferred()


func _run() -> void:
	AudioServer.bus_count = 1
	while AudioServer.get_bus_effect_count(0) > 0:
		AudioServer.remove_bus_effect(0, 0)
	AudioServer.set_bus_name(0, &"Master")
	AudioServer.set_bus_volume_db(0, 0.0)
	var glue := AudioEffectCompressor.new()
	glue.resource_name = "Glue"
	glue.threshold = -10.0
	glue.ratio = 2.0
	glue.attack_us = 15000.0
	glue.release_ms = 220.0
	AudioServer.add_bus_effect(0, glue)
	var lim := AudioEffectHardLimiter.new()
	lim.resource_name = "Limiter"
	lim.ceiling_db = -0.8
	lim.release = 0.12
	AudioServer.add_bus_effect(0, lim)

	_bus(&"Music", &"Master", [_duck(), _muffle()])
	var sfx_rev := _reverb("Street", 0.3, 0.6, 0.8, 18.0, 0.2, 0.15, 1.0, 0.07)
	var sfx_comp := AudioEffectCompressor.new()
	sfx_comp.resource_name = "Comp"
	sfx_comp.threshold = -14.0
	sfx_comp.ratio = 3.0
	sfx_comp.attack_us = 5000.0
	sfx_comp.release_ms = 150.0
	_bus(&"SFX", &"Master", [_muffle(), sfx_rev, sfx_comp])
	_bus(&"Ambience", &"Master", [_duck(), _muffle()])
	_bus(&"UI", &"Master", [])
	var vcomp := AudioEffectCompressor.new()
	vcomp.resource_name = "Comp"
	vcomp.threshold = -16.0
	vcomp.ratio = 2.5
	vcomp.attack_us = 3000.0
	vcomp.release_ms = 120.0
	_bus(&"Voice", &"SFX", [vcomp])
	# reverb zones (Area3D.reverb_bus_name) — wet only, returning into SFX
	_bus(&"Alley", &"SFX", [_reverb("Alley", 0.42, 0.35, 1.0, 14.0, 0.35, 0.2, 0.0, 0.9)])
	_bus(&"Temple", &"SFX", [_reverb("Temple", 0.8, 0.3, 1.0, 40.0, 0.25, 0.15, 0.0, 0.8)])
	_bus(&"Interior", &"SFX", [_reverb("Interior", 0.22, 0.65, 0.7, 5.0, 0.1, 0.1, 0.0, 0.8)])
	_bus(&"Market", &"SFX", [_reverb("Market", 0.55, 0.5, 1.0, 22.0, 0.2, 0.15, 0.0, 0.8)])

	var layout := AudioServer.generate_bus_layout()
	var err := ResourceSaver.save(layout, "res://default_bus_layout.tres")
	print("bus layout saved: ", err, " buses=", AudioServer.bus_count)
	quit(0 if err == OK else 1)


func _bus(bus_name: StringName, send: StringName, effects: Array) -> void:
	AudioServer.add_bus()
	var idx := AudioServer.bus_count - 1
	AudioServer.set_bus_name(idx, bus_name)
	AudioServer.set_bus_send(idx, send)
	for e in effects:
		AudioServer.add_bus_effect(idx, e)


func _duck() -> AudioEffectAmplify:
	var a := AudioEffectAmplify.new()
	a.resource_name = "Duck"
	a.volume_db = 0.0
	return a


func _muffle() -> AudioEffectLowPassFilter:
	var f := AudioEffectLowPassFilter.new()
	f.resource_name = "Muffle"
	f.cutoff_hz = 20500.0
	f.resonance = 0.5
	return f


func _reverb(rname: String, room: float, damping: float, spread: float, predelay_ms: float, feedback: float,
		hipass: float, dry: float, wet: float) -> AudioEffectReverb:
	var r := AudioEffectReverb.new()
	r.resource_name = rname
	r.room_size = room
	r.damping = damping
	r.spread = spread
	r.predelay_msec = predelay_ms
	r.predelay_feedback = feedback
	r.hipass = hipass
	r.dry = dry
	r.wet = wet
	return r
