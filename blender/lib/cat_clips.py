"""All contract animation clips for Cam, authored on top of cat_anim.Solver.

Conventions: in-place (root never moves), Blender -Y forward, 30 fps.
Locomotion: stance paws move backwards at exactly the gait speed (no sliding):
  walk 0.70 m/s (lateral sequence LH-LF-RH-RF), trot 1.60 (diagonal pairs),
  run 4.50 (rotary gallop LH-RH-RF-LF, gathered + extended suspension, big spine flex),
  sneak 0.45 (low, deliberate, high duty), balance_walk 0.40 (single track, tail balancing).
Turns: the controller yaws the model 90 deg LINEARLY over the clip (0.667 s); planted
paws counter-rotate so they stay fixed in the world.
Climb: wall plane at Blender y = -0.075 (Godot local z = +0.075), climbing speed 0.5 m/s.
Scratch: vertical surface at Blender y = -0.12 (Godot z = +0.12).
"""
from __future__ import annotations

import math

from mathutils import Quaternion, Vector

import cat_anatomy as A
from cat_anim import (DEFAULT, FPS, REST_PAW, P, bump, ease, ease5, keyed, mix, qa, write_action, Fv)

TAU = 2 * math.pi


def rp(leg, df=0.0, dx=0.0, dz=0.0):
    """Rest paw position shifted (df forward, dx outward, dz up)."""
    p = REST_PAW[leg].copy()
    s = 1 if leg[1] == "L" else -1
    return Vector((p.x + s * dx, p.y - df, p.z + dz))


def blink_at(frame, starts, close=2.5, hold=1.5, opn=4.0):
    v = 0.0
    for s in starts:
        u = frame - s
        if 0 <= u < close:
            v = max(v, ease(u / close))
        elif close <= u < close + hold:
            v = 1.0
        elif close + hold <= u < close + hold + opn:
            v = max(v, 1 - ease((u - close - hold) / opn))
    return v


def flick(frame, at, dur=6.0):
    u = (frame - at) / dur
    if u <= 0 or u >= 1:
        return 0.0
    return math.sin(math.pi * u) * math.exp(-2.5 * u) * 2.2


def breathe(t, cycles, amp=0.9):
    return amp * math.sin(TAU * cycles * t)


def with_overlays(p, frame, t, nframes, breaths=0, blinks=(), flicks=(), tail_sway=0.0, tail_cycles=1):
    p = mix(p, p, 0)
    if breaths:
        sp = list(p["spine"])
        sp[0] += breathe(t, breaths, 0.9)
        p["spine"] = tuple(sp)
        p["neck_lift"] += breathe(t, breaths, 0.3)
    if blinks:
        b = blink_at(frame, blinks)
        bl = p["blink"]
        p["blink"] = (max(bl[0], b), max(bl[1], b))
    for at, side in flicks:
        k = "ear" + side
        e = list(p[k])
        v = flick(frame, at)
        e[0] += 22 * v
        e[1] += 30 * v
        p[k] = tuple(e)
    if tail_sway:
        p["tail"]["amp"] = max(p["tail"]["amp"], tail_sway)
        p["tail"]["phase"] = t * tail_cycles
    return p


# ---------------------------------------------------------------------------
# key poses
# ---------------------------------------------------------------------------
STAND = P(head=(-7.0, 0.0, 0.0), tail={"lift": 8.0, "curve": 10.0})

_MT = Vector(A.TOE_L) - Vector(A.FOOT_L)
HIND_REST_DIR = tuple(_MT.normalized())


def dirmode(p):
    """Copy of a pose whose hind legs use explicit metatarsus directions (rest direction when
    the pose had none) so it blends smoothly with sitting/lying poses."""
    q = mix(p, p, 0)
    for leg in ("HL", "HR"):
        if q[leg].get("mode", "panto") != "dir" or q[leg].get("dir") is None:
            d = HIND_REST_DIR
            q[leg]["dir"] = (d[0] if leg == "HL" else -d[0], d[1], d[2])
            q[leg]["mode"] = "dir"
    return q


CROUCH = P(pel=(0.0, 0.010, -0.050), pel_rot=(-4.0, 0.0, 0.0), spine=(2.0, 0, 0), neck_lift=-6.0,
           head=(6.0, 0.0, 0.0), earL=(-8.0, -10.0, 0.0), earR=(-8.0, -10.0, 0.0), whisk=8.0,
           tail={"lift": -6.0, "curve": -6.0},
           HL={"p": rp("HL", df=0.012), "a": 0.0}, HR={"p": rp("HR", df=0.012), "a": 0.0},
           FL={"p": rp("FL", df=-0.004)}, FR={"p": rp("FR", df=-0.004)})


def sit_pose():
    return P(pel=(0.0, -0.022, -0.122), pel_rot=(46.0, 0.0, 0.0), spine=(-27.0, 0.0, 0.0), neck_lift=10.0,
             head=(-2.0, 0.0, 0.0),
             tail={"lift": 34.0, "curve": -4.0, "side": 140.0, "tip": 26.0},
             FL={"p": rp("FL", df=-0.030, dx=-0.004), "a": 4.0},
             FR={"p": rp("FR", df=-0.030, dx=-0.004), "a": 4.0},
             HL={"p": Fv(0.040, -0.088, 0.012), "mode": "dir", "dir": (0.0, -1.0, -0.03), "toe": 4.0},
             HR={"p": Fv(-0.040, -0.088, 0.012), "mode": "dir", "dir": (0.0, -1.0, -0.03), "toe": 4.0})


SIT = sit_pose()


def lie_pose(head_down=True):
    return P(pel=(0.0, 0.010, -0.106), pel_rot=(-2.0, 0.0, 4.0), spine=(4.0, 0.0, -4.0), neck_lift=(-44.0 if head_down else 6.0),
             head=((-26.0 if head_down else 0.0), 0.0, (8.0 if head_down else 0.0)),
             earL=(6.0, 18.0, 6.0) if head_down else (0, 0, 0), earR=(6.0, 18.0, 6.0) if head_down else (0, 0, 0),
             tail={"lift": -24.0, "curve": -10.0, "side": 95.0, "tip": 10.0},
             FL={"p": Fv(0.026, 0.165, 0.011), "a": -55.0, "toe": -10.0},
             FR={"p": Fv(-0.026, 0.160, 0.011), "a": -55.0, "toe": -10.0},
             HL={"p": Fv(0.058, -0.105, 0.011), "mode": "dir", "dir": (0.15, -1.0, -0.02), "toe": 0.0},
             HR={"p": Fv(-0.058, -0.105, 0.011), "mode": "dir", "dir": (-0.15, -1.0, -0.02), "toe": 0.0})


LIE_UP = lie_pose(False)
LIE = lie_pose(True)


# ---------------------------------------------------------------------------
# locomotion generator
# ---------------------------------------------------------------------------
def gait(stride_frames, v, duty, phases, *, strides=2, track=(0.024, 0.024), centre=(0.0, 0.0),
         lift=(0.030, 0.034), body_dz=0.0, bob=0.004, bob_phase=0.0, roll=2.5, yaw=3.0, spine_yaw=4.0,
         spine_pitch_amp=0.0, spine_phase=0.0, pel_pitch_amp=0.0, head=(-6.0, 0.0, 0.0), neck_lift=0.0,
         tail=None, tail_amp=6.0, tail_pitch_amp=0.0, ears=(0.0, 0.0, 0.0), fore_flex=80.0, hind_flex=22.0,
         chest_dz=0.0, chest_bob=0.0, chest_phase=0.0, extra=None):
    T = stride_frames
    L = v * T / FPS
    nf = T * strides

    def leg_state(leg, tt):
        ph = (tt - phases[leg]) % 1.0
        b = duty[leg[0]] if isinstance(duty, dict) else duty
        fore = leg[0] == "F"
        s = 1 if leg[1] == "L" else -1
        base = REST_PAW[leg]
        x = s * (track[0] if fore else track[1])
        f0 = -base.y + (centre[0] if fore else centre[1])
        z0 = base.z
        travel = b * L
        if ph < b:
            u = ph / b
            f = f0 + travel * 0.5 - travel * u
            z = z0
            a = (-6.0 + 22.0 * ease((u - 0.55) / 0.45)) if fore else 0.0
            toe = 0.0
        else:
            u = (ph - b) / (1 - b)
            f = f0 - travel * 0.5 + travel * ease5(u)
            hgt = (lift[0] if fore else lift[1]) * math.sin(math.pi * min(1.0, u ** 0.85))
            z = z0 + hgt
            a = (fore_flex if fore else hind_flex) * math.sin(math.pi * min(1.0, u ** 0.7)) ** 1.2
            toe = 25.0 * math.sin(math.pi * u)
        out = {"p": Vector((x, -f, z)), "a": a, "toe": toe}
        if not fore:
            out["mode"] = "panto"
        return out

    def fn(frame, t):
        tt = frame / T
        p = P(head=head, neck_lift=neck_lift, earL=ears, earR=ears)
        for leg in ("FL", "FR", "HL", "HR"):
            p[leg].update(leg_state(leg, tt))
        w = TAU * tt
        dz = body_dz + bob * math.cos(2 * w + bob_phase)
        p["pel"] = (0.0, 0.0, dz)
        p["pel_rot"] = (pel_pitch_amp * math.cos(w - spine_phase), yaw * math.sin(w), roll * math.sin(w + 0.6))
        p["spine"] = (spine_pitch_amp * math.cos(w - spine_phase) + chest_bob * math.cos(2 * w + chest_phase),
                      -spine_yaw * math.sin(w), -roll * 0.6 * math.sin(w + 0.6))
        tl = dict(tail or {"lift": 12.0, "curve": 6.0})
        tl.setdefault("amp", tail_amp)
        tl["phase"] = t
        tl["pamp"] = tail_pitch_amp
        tl["wl"] = tl.get("wl", 1.2)
        p["tail"].update(tl)
        # head: stabilised in pitch/roll; slight counter-yaw
        hp, hy, hr = head
        p["head"] = (hp + 1.0 * math.sin(2 * w), hy + 1.5 * math.sin(w), hr)
        if chest_dz:
            p["spine"] = (p["spine"][0] - chest_dz, p["spine"][1], p["spine"][2])
        if extra:
            extra(p, frame, t, tt)
        return p
    return nf, fn


# ---------------------------------------------------------------------------
# clip definitions
# ---------------------------------------------------------------------------
def clip_defs():
    C = {}

    # --- idle / looks ---------------------------------------------------------
    def idle(fr, t):
        p = mix(STAND, STAND, 0)
        p["pel"] = (0.0015 * math.sin(TAU * t), 0.0, 0.0)
        p["pel_rot"] = (0.0, 0.0, 1.2 * math.sin(TAU * t))
        p["head"] = (-7.0 + 2.0 * math.sin(TAU * t + 1.0), 4.0 * math.sin(TAU * t), 1.5 * math.sin(TAU * 2 * t))
        p["eyes"] = (6.0 * math.sin(TAU * 2 * t + 0.5), 0.0)
        p["tail"].update({"lift": 8.0 + 2.0 * math.sin(TAU * t), "curve": 10.0})
        return with_overlays(p, fr, t, 120, breaths=2, blinks=(68,), flicks=((30, "L"), (96, "R")), tail_sway=5.0)
    C["idle"] = (120, idle, True)

    look_keys = [(0, (0, 0)), (20, (0, 0)), (34, (6, 42)), (62, (4, 40)), (80, (-2, -38)), (110, (-4, -36)), (132, (0, 0)), (150, (0, 0))]

    def idle_look(fr, t):
        hp, hy = _interp_pairs(look_keys, fr)
        p = mix(STAND, STAND, 0)
        p["head"] = (-7.0 + hp, hy, -hy * 0.12)
        p["spine"] = (0.0, hy * 0.18, 0.0)
        p["eyes"] = (max(-15, min(15, _lead(look_keys, fr) * 0.4)), 0.0)
        p["earL"] = (0.0, max(0.0, -hy) * 0.5, 0.0)
        p["earR"] = (0.0, max(0.0, hy) * 0.5, 0.0)
        p["tail"].update({"lift": 10.0, "curve": 10.0, "tip": 20.0 * bump(t, 0.45, 0.6)})
        return with_overlays(p, fr, t, 150, breaths=2, blinks=(28, 76, 128), flicks=((52, "L"),), tail_sway=6.0)
    C["idle_look"] = (150, idle_look, True)

    # --- locomotion -----------------------------------------------------------
    walk_ph = {"HL": 0.0, "FL": 0.25, "HR": 0.5, "FR": 0.75}
    C["walk"] = (*gait(15, 0.70, 0.60, walk_ph, track=(0.022, 0.024), centre=(0.004, -0.004), lift=(0.026, 0.030),
                       body_dz=-0.006, bob=0.0035, roll=2.0, yaw=3.5, spine_yaw=4.0, head=(-17.0, 0.0, 0.0),
                       neck_lift=-4.0, tail={"lift": 18.0, "curve": 4.0, "tip": 18.0}, tail_amp=7.0), True)
    trot_ph = {"HL": 0.0, "FR": 0.0, "HR": 0.5, "FL": 0.5}
    C["trot"] = (*gait(10, 1.60, 0.42, trot_ph, track=(0.020, 0.022), centre=(0.012, -0.010), lift=(0.034, 0.036),
                       body_dz=-0.012, bob=0.005, roll=1.5, yaw=2.0, spine_yaw=2.5, head=(-15.0, 0.0, 0.0),
                       neck_lift=-6.0, tail={"lift": 10.0, "curve": 2.0, "tip": 10.0}, tail_amp=5.0,
                       ears=(6.0, 0.0, 0.0), fore_flex=95.0, hind_flex=28.0), True)
    gal_ph = {"HL": 0.0, "HR": 0.10, "FR": 0.42, "FL": 0.52}
    C["run"] = (*gait(8, 4.50, 0.21, gal_ph, track=(0.018, 0.022), centre=(0.030, -0.030), lift=(0.050, 0.055),
                      body_dz=-0.014, bob=0.006, bob_phase=1.0, roll=1.0, yaw=2.0, spine_yaw=2.0,
                      spine_pitch_amp=-26.0, spine_phase=TAU * 0.92, pel_pitch_amp=14.0,
                      head=(-12.0, 0.0, 0.0), neck_lift=-10.0, tail={"lift": 4.0, "curve": 12.0, "tip": 0.0},
                      tail_amp=3.0, tail_pitch_amp=8.0, ears=(22.0, 10.0, 0.0), fore_flex=110.0, hind_flex=40.0),
                True)
    sneak_ph = {"HL": 0.0, "FL": 0.25, "HR": 0.5, "FR": 0.75}

    def sneak_extra(p, fr, t, tt):
        p["tail"]["tip"] = 25.0 + 12.0 * math.sin(TAU * 4 * t)
        p["whisk"] = 10.0
    C["sneak"] = (*gait(20, 0.45, 0.72, sneak_ph, track=(0.026, 0.028), centre=(0.0, 0.006), lift=(0.022, 0.024),
                        body_dz=-0.052, bob=0.002, roll=1.2, yaw=2.0, spine_yaw=3.0, spine_pitch_amp=0.0,
                        head=(-2.0, 0.0, 0.0), neck_lift=-24.0, chest_dz=-4.0,
                        tail={"lift": -14.0, "curve": -6.0, "tip": 25.0}, tail_amp=4.0,
                        ears=(-10.0, -12.0, 0.0), fore_flex=70.0, hind_flex=20.0, extra=sneak_extra), True)
    bal_ph = {"HL": 0.0, "FL": 0.25, "HR": 0.5, "FR": 0.75}

    def bal_extra(p, fr, t, tt):
        p["tail"]["amp"] = 18.0
        p["tail"]["wl"] = 2.2
        p["tail"]["yaw"] = 14.0 * math.sin(TAU * t)
        p["head"] = (-14.0, 2.0 * math.sin(TAU * t), 0.0)
    C["balance_walk"] = (*gait(20, 0.40, 0.66, bal_ph, track=(0.005, 0.006), centre=(0.0, 0.0), lift=(0.022, 0.026),
                               body_dz=-0.022, bob=0.0025, roll=3.0, yaw=2.0, spine_yaw=2.0, head=(-14.0, 0, 0),
                               neck_lift=-12.0, tail={"lift": 4.0, "curve": 0.0, "tip": 6.0},
                               ears=(0.0, -6.0, 0.0), extra=bal_extra), True)

    # --- sneak idle ------------------------------------------------------------
    sneak_base = mix(STAND, STAND, 0)
    sneak_base.update(P(pel=(0.0, 0.0, -0.052), spine=(-4.0, 0, 0), neck_lift=-24.0, head=(-2.0, 0, 0),
                        earL=(-10.0, -12.0, 0.0), earR=(-10.0, -12.0, 0.0), whisk=10.0,
                        tail={"lift": -14.0, "curve": -6.0, "tip": 25.0},
                        FL={"p": rp("FL", df=0.010, dx=-0.004)}, FR={"p": rp("FR", df=0.002, dx=-0.004)},
                        HL={"p": rp("HL", df=0.004)}, HR={"p": rp("HR", df=0.006)}))

    def sneak_idle(fr, t):
        p = mix(sneak_base, sneak_base, 0)
        w = 0.6 * bump(t, 0.55, 0.9)
        p["pel_rot"] = (0.0, 5.0 * w * math.sin(TAU * 12 * t), 2.0 * w * math.sin(TAU * 12 * t))   # butt wiggle
        p["tail"]["tip"] = 25.0 + 18.0 * math.sin(TAU * 6 * t)
        p["tail"]["amp"] = 3.0
        p["tail"]["phase"] = 3 * t
        p["head"] = (-2.0, 3.0 * math.sin(TAU * t), 0.0)
        return with_overlays(p, fr, t, 90, breaths=2, blinks=(40,))
    C["sneak_idle"] = (90, sneak_idle, True)

    # --- jumping / falling -----------------------------------------------------
    C["jump_crouch"] = (12, lambda fr, t: keyed([(0, STAND), (10, CROUCH), (12, CROUCH)], fr), False)
    LAUNCH = P(pel=(0.0, -0.010, -0.010), pel_rot=(18.0, 0, 0), spine=(14.0, 0, 0), neck_lift=6.0, head=(10.0, 0, 0),
               earL=(10.0, 0, 0), earR=(10.0, 0, 0), tail={"lift": -4.0, "curve": 4.0},
               FL={"p": rp("FL", df=0.050, dz=0.070), "a": 70.0, "toe": 20.0},
               FR={"p": rp("FR", df=0.040, dz=0.060), "a": 70.0, "toe": 20.0},
               HL={"p": rp("HL", df=-0.040, dz=-0.015), "a": -10.0, "toe": 30.0},
               HR={"p": rp("HR", df=-0.040, dz=-0.015), "a": -10.0, "toe": 30.0})
    AIR = P(pel=(0.0, 0.0, 0.004), pel_rot=(8.0, 0, 0), spine=(6.0, 0, 0), neck_lift=0.0, head=(0.0, 0, 0),
            earL=(14.0, 6.0, 0), earR=(14.0, 6.0, 0), tail={"lift": 6.0, "curve": 2.0},
            FL={"p": rp("FL", df=0.060, dz=0.030), "a": 20.0, "toe": 10.0},
            FR={"p": rp("FR", df=0.055, dz=0.028), "a": 20.0, "toe": 10.0},
            HL={"p": rp("HL", df=-0.050, dz=0.010), "a": -8.0, "toe": 20.0},
            HR={"p": rp("HR", df=-0.050, dz=0.010), "a": -8.0, "toe": 20.0})
    C["jump_up"] = (10, lambda fr, t: keyed([(0, CROUCH), (4, LAUNCH), (10, AIR)], fr), False)
    FALL = P(pel=(0.0, 0.0, 0.0), pel_rot=(-4.0, 0, 0), spine=(-2.0, 0, 0), neck_lift=-6.0, head=(-16.0, 0, 0),
             earL=(18.0, 10.0, 6.0), earR=(18.0, 10.0, 6.0), whisk=12.0, tail={"lift": 10.0, "curve": 8.0},
             FL={"p": rp("FL", df=0.022, dz=-0.012), "a": -10.0, "toe": -10.0},
             FR={"p": rp("FR", df=0.022, dz=-0.012), "a": -10.0, "toe": -10.0},
             HL={"p": rp("HL", df=0.006, dz=-0.014), "a": 0.0, "toe": -6.0},
             HR={"p": rp("HR", df=0.006, dz=-0.014), "a": 0.0, "toe": -6.0})

    def fall(fr, t):
        p = mix(FALL, FALL, 0)
        p["tail"]["yaw"] = 18.0 * math.sin(TAU * t)
        p["tail"]["pamp"] = 6.0
        p["tail"]["phase"] = t
        p["tail"]["lift"] = 10.0 + 10.0 * math.cos(TAU * t)
        for leg, ph in (("FL", 0.0), ("FR", 0.5), ("HL", 0.25), ("HR", 0.75)):
            q = p[leg]["p"].copy()
            q.z += 0.004 * math.sin(TAU * (2 * t + ph))
            p[leg]["p"] = q
        p["head"] = (-16.0 + 2.0 * math.sin(TAU * t), 0.0, 0.0)
        return p
    C["fall"] = (20, fall, True)
    TOUCH = P(pel=(0.0, 0.0, 0.006), pel_rot=(-8.0, 0, 0), spine=(-6.0, 0, 0), head=(-14.0, 0, 0), neck_lift=-4.0,
              earL=(14.0, 8.0, 0), earR=(14.0, 8.0, 0), tail={"lift": 18.0, "curve": 6.0},
              FL={"p": rp("FL", df=0.012)}, FR={"p": rp("FR", df=0.010)},
              HL={"p": rp("HL", df=-0.006, dz=0.020), "a": 0, "toe": 10}, HR={"p": rp("HR", df=-0.006, dz=0.018), "a": 0, "toe": 10})
    ABSORB = P(pel=(0.0, 0.004, -0.040), pel_rot=(-4.0, 0, 0), spine=(-8.0, 0, 0), neck_lift=-10.0, head=(-8.0, 0, 0),
               earL=(10.0, 4.0, 0), earR=(10.0, 4.0, 0), tail={"lift": 22.0, "curve": 4.0},
               FL={"p": rp("FL", df=0.012)}, FR={"p": rp("FR", df=0.010)},
               HL={"p": rp("HL", df=0.010)}, HR={"p": rp("HR", df=0.010)})
    C["land"] = (12, lambda fr, t: keyed([(0, TOUCH), (4, ABSORB), (12, STAND)], fr), False)
    ABSORB_HARD = P(pel=(0.0, 0.010, -0.070), pel_rot=(-6.0, 0, 0), spine=(-14.0, 0, 0), neck_lift=-20.0,
                    head=(-20.0, 0, 0), earL=(20.0, 14.0, 8.0), earR=(20.0, 14.0, 8.0), blink=(0.6, 0.6),
                    tail={"lift": 26.0, "curve": 0.0},
                    FL={"p": rp("FL", df=0.016, dx=0.006)}, FR={"p": rp("FR", df=0.014, dx=0.006)},
                    HL={"p": rp("HL", df=0.018, dx=0.004)}, HR={"p": rp("HR", df=0.018, dx=0.004)})
    C["land_hard"] = (24, lambda fr, t: keyed([(0, TOUCH), (5, ABSORB_HARD), (11, ABSORB_HARD), (24, STAND)], fr), False)

    # --- sitting --------------------------------------------------------------
    MID_SIT = mix(STAND, SIT, 0.45)
    MID_SIT["FL"]["p"] = rp("FL", df=-0.010, dx=-0.002)
    MID_SIT["FR"]["p"] = rp("FR", df=-0.010, dx=-0.002)
    STAND_D = dirmode(STAND)
    MID_SIT = dirmode(MID_SIT)
    C["sit_down"] = (30, lambda fr, t: keyed([(0, STAND_D), (14, MID_SIT), (30, SIT)], fr), False)

    def sit_idle(fr, t):
        p = mix(SIT, SIT, 0)
        p["head"] = (2.0 * math.sin(TAU * t), 6.0 * math.sin(TAU * t + 0.4), 0.0)
        p["tail"]["tip"] = 30.0 + 22.0 * bump(t, 0.30, 0.42) - 18.0 * bump(t, 0.72, 0.8)
        return with_overlays(p, fr, t, 120, breaths=2, blinks=(50, 104), flicks=((20, "R"), (84, "L")))
    C["sit_idle"] = (120, sit_idle, True)
    C["stand_up"] = (24, lambda fr, t: keyed([(0, SIT), (10, MID_SIT), (24, STAND_D)], fr), False)

    # --- lying / sleeping -----------------------------------------------------
    C["lie_down"] = (45, lambda fr, t: keyed([(0, STAND_D), (14, MID_SIT), (26, mix(SIT, LIE_UP, 0.5)), (36, LIE_UP),
                                              (45, LIE)], fr), False)

    def sleep(fr, t):
        p = mix(LIE, LIE, 0)
        p["blink"] = (1.0, 1.0)
        p["lower_lid"] = 1.0
        p["tail"]["tip"] = 10.0 + 14.0 * bump(t, 0.6, 0.7)
        p["whisk"] = -6.0
        return with_overlays(p, fr, t, 150, breaths=2, flicks=((40, "L"),))
    C["sleep"] = (150, sleep, True)

    # --- grooming / mouth ------------------------------------------------------
    C["groom"] = (96, groom_fn(), True)
    MEOW = mix(STAND, STAND, 0)
    MEOW.update(P(head=(14.0, 0.0, 0.0), neck_lift=6.0, jaw=24.0, earL=(8.0, 8.0, 0), earR=(8.0, 8.0, 0),
                  blink=(0.35, 0.35), whisk=6.0, tail={"lift": 20.0, "curve": 10.0, "tip": 20.0}))
    C["meow"] = (24, lambda fr, t: keyed([(0, STAND), (6, mix(STAND, MEOW, 0.7)), (11, MEOW), (16, MEOW),
                                          (24, STAND)], fr), False)
    HISS = P(pel=(0.0, 0.020, -0.006), pel_rot=(-8.0, 0, 0), spine=(-22.0, 0, 0), spine_w=(0.15, 0.45, 0.35, 0.05),
             neck_lift=-18.0, head=(4.0, 0, 0), jaw=34.0, earL=(55.0, 50.0, 40.0), earR=(55.0, 50.0, 40.0),
             whisk=-14.0, tail={"lift": -10.0, "curve": -30.0, "tip": -10.0},
             FL={"p": rp("FL", df=0.010, dx=0.004)}, FR={"p": rp("FR", df=0.010, dx=0.004)},
             HL={"p": rp("HL", df=0.006)}, HR={"p": rp("HR", df=0.006)})

    def hiss(fr, t):
        p = keyed([(0, STAND), (6, mix(STAND, HISS, 0.8)), (10, HISS), (26, HISS), (36, STAND)], fr)
        p["jaw"] += 3.0 * math.sin(TAU * 6 * t) * bump(t, 0.25, 0.75)
        return p
    C["hiss"] = (36, hiss, False)

    # --- paws -----------------------------------------------------------------
    SW_UP = mix(STAND, STAND, 0)
    SW_UP.update(P(pel=(0.0, 0.010, -0.010), spine=(6.0, 0, 0), head=(4.0, 0, 0), earL=(10.0, 20.0, 0), earR=(10, 20, 0),
                   FL={"p": rp("FL", df=0.040, dz=0.075, dx=-0.004), "a": 85.0, "toe": 30.0},
                   FR={"p": rp("FR", df=-0.004)}))
    SW_HIT = mix(SW_UP, SW_UP, 0)
    SW_HIT["FL"] = {"p": rp("FL", df=0.120, dz=0.020, dx=-0.012), "a": -15.0, "toe": -20.0, "scap": 0.0}
    SW_HIT["spine"] = (-4.0, 0, 0)
    C["swipe"] = (15, lambda fr, t: keyed([(0, STAND), (5, SW_UP), (8, SW_HIT), (15, STAND)], fr), False)
    C["knock"] = (24, knock_fn(), False)
    C["scratch"] = (30, scratch_fn(), True)
    C["climb"] = (18, climb_fn(), True)
    C["knead"] = (32, knead_fn(), True)
    C["stretch"] = (64, stretch_fn(), False)

    # --- turns ----------------------------------------------------------------
    C["turn_left_90"] = (20, turn_fn(+1), False)
    C["turn_right_90"] = (20, turn_fn(-1), False)

    # --- eating / drinking / pickup ------------------------------------------
    C["drink"] = (40, drink_fn(lap=True), True)
    C["eat"] = (40, drink_fn(lap=False), True)
    C["pickup"] = (22, pickup_fn(), False)
    return C


def _interp_pairs(keys, fr):
    if fr <= keys[0][0]:
        return keys[0][1]
    for (f0, a), (f1, b) in zip(keys[:-1], keys[1:]):
        if fr <= f1:
            u = ease((fr - f0) / (f1 - f0))
            return tuple(x + (y - x) * u for x, y in zip(a, b))
    return keys[-1][1]


def _lead(keys, fr):
    """eyes lead the head: look a few frames ahead."""
    a = _interp_pairs(keys, fr + 5)[1]
    b = _interp_pairs(keys, fr)[1]
    return (a - b) * 3.0 + b * 0.25


def crouch_low():
    return P(pel=(0.0, 0.004, -0.060), pel_rot=(-2.0, 0, 0), spine=(-6.0, 0, 0), neck_lift=-34.0, head=(-48.0, 0, 0),
             earL=(-4.0, 10.0, 0), earR=(-4.0, 10.0, 0), whisk=6.0, tail={"lift": -20.0, "curve": -10.0, "side": 40.0},
             FL={"p": rp("FL", df=-0.004, dx=0.004)}, FR={"p": rp("FR", df=-0.004, dx=0.004)},
             HL={"p": Fv(0.040, -0.120, 0.012), "mode": "dir", "dir": (0.0, -1.0, -0.25), "toe": 4.0},
             HR={"p": Fv(-0.040, -0.120, 0.012), "mode": "dir", "dir": (0.0, -1.0, -0.25), "toe": 4.0})


def drink_fn(lap: bool):
    base = crouch_low()

    def fn(fr, t):
        p = mix(base, base, 0)
        if lap:
            k = 5   # 5 laps in 40 frames (~3.75 Hz)
            ph = (t * k) % 1.0
            p["jaw"] = 9.0 * math.sin(math.pi * ph) ** 2
            p["tongue"] = 0.8 * math.sin(math.pi * ph) ** 3
            p["tongue_curl"] = 40.0 * math.sin(math.pi * ph)
            p["head"] = (-48.0 + 3.0 * math.sin(TAU * k * t), 0.0, 0.0)
            p["blink"] = (0.35, 0.35)
        else:
            k = 3
            ph = (t * k) % 1.0
            p["jaw"] = 13.0 * math.sin(math.pi * ph) ** 2
            p["head"] = (-46.0 + 4.0 * math.sin(TAU * k * t), 4.0 * math.sin(TAU * t), 14.0 + 6.0 * math.sin(TAU * k * t))
            p["earL"] = (6.0 + 6.0 * math.sin(TAU * k * t), 14.0, 0.0)
            p["earR"] = (6.0 + 6.0 * math.sin(TAU * k * t), 14.0, 0.0)
            p["blink"] = (0.3, 0.3)
        p["tail"]["tip"] = 10.0 * math.sin(TAU * 2 * t)
        return with_overlays(p, fr, t, 40, breaths=1)
    return fn


def pickup_fn():
    down = crouch_low()
    down["HL"] = {"p": rp("HL", df=0.004), "a": 0.0, "toe": 0.0, "mode": "panto", "dir": None}
    down["HR"] = {"p": rp("HR", df=0.004), "a": 0.0, "toe": 0.0, "mode": "panto", "dir": None}
    down["pel"] = (0.0, -0.006, -0.026)
    down["head"] = (-58.0, 0.0, 0.0)
    down["tail"] = dict(STAND["tail"])
    bite = mix(down, down, 0)
    bite["jaw"] = 22.0
    hold = mix(STAND, STAND, 0)
    hold["jaw"] = 3.0
    hold["head"] = (2.0, 0.0, 0.0)
    return lambda fr, t: keyed([(0, STAND), (7, down), (10, bite), (13, mix(down, down, 0)), (22, hold)], fr)


def knock_fn():
    reach = mix(STAND, STAND, 0)
    reach.update(P(pel=(0.0, 0.004, -0.006), spine=(4.0, 0.0, 0.0), head=(-12.0, 6.0, 0.0), earL=(0, -10, 0), earR=(0, -10, 0),
                   FL={"p": rp("FL", df=0.090, dz=0.085, dx=0.012), "a": 40.0, "toe": -10.0},
                   FR={"p": rp("FR", df=0.004)}))
    push = mix(reach, reach, 0)
    push["FL"] = {"p": rp("FL", df=0.105, dz=0.080, dx=-0.030), "a": 25.0, "toe": -20.0, "scap": 0.0}
    push["head"] = (-14.0, -4.0, 0.0)
    return lambda fr, t: keyed([(0, STAND), (6, reach), (10, reach), (15, push), (24, STAND)], fr)


SCRATCH_WALL_Y = -0.120


def scratch_fn():
    up = P(pel=(0.0, -0.050, -0.020), pel_rot=(58.0, 0, 0), spine=(10.0, 0, 0), neck_lift=4.0, head=(14.0, 0, 0),
           earL=(4.0, 10.0, 0), earR=(4.0, 10.0, 0), tail={"lift": 44.0, "curve": 10.0, "tip": 14.0, "side": 30.0},
           HL={"p": rp("HL", df=0.035), "mode": "panto"}, HR={"p": rp("HR", df=0.035), "mode": "panto"})

    def fn(fr, t):
        p = mix(up, up, 0)
        for leg, ph in (("FL", 0.0), ("FR", 0.5)):
            u = (t * 2 + ph) % 1.0
            s = 1 if leg[1] == "L" else -1
            if u < 0.6:      # pull down (claws hooked in the surface)
                z = 0.405 - 0.060 * ease(u / 0.6)
                a = -25.0 + 45.0 * (u / 0.6)
                toe = 35.0
                y = SCRATCH_WALL_Y + 0.004
            else:            # reach back up, paw off the surface
                v = (u - 0.6) / 0.4
                z = 0.345 + 0.060 * ease(v)
                a = 20.0 - 45.0 * v
                toe = 10.0
                y = SCRATCH_WALL_Y + 0.004 + 0.014 * math.sin(math.pi * v)
            p[leg] = {"p": Vector((s * 0.024, y, z)), "a": a, "toe": toe, "scap": 0.0}
        p["pel"] = (0.0, -0.050, -0.020 - 0.004 * math.sin(TAU * 2 * t))
        p["spine"] = (10.0 + 2.0 * math.sin(TAU * 2 * t), 0.0, 3.0 * math.sin(TAU * 2 * t))
        p["blink"] = (0.4, 0.4)
        return p
    return fn


CLIMB_WALL_Y = -0.075
CLIMB_SPEED = 0.5


def climb_fn():
    nf = 18
    travel_cycle = CLIMB_SPEED * nf / FPS        # 0.30 m per cycle

    def fn(fr, t):
        p = P(pel_rot=(80.0, 0, 0), neck_lift=-8.0, head=(26.0, 0, 0),
              earL=(10.0, 4.0, 0), earR=(10.0, 4.0, 0), tail={"lift": 62.0, "curve": 14.0, "side": 20.0})
        flex = math.cos(TAU * (t - 0.85))
        p["spine"] = (8.0 * flex, 0, 0)
        p["pel"] = (0.0, -0.172, -0.060 + 0.018 * math.cos(TAU * (t - 0.2)))
        for leg, ph, base_z, fore in (("FL", 0.00, 0.430, True), ("FR", 0.06, 0.420, True),
                                      ("HL", 0.50, 0.105, False), ("HR", 0.56, 0.100, False)):
            u = (t - ph) % 1.0
            duty = 0.55
            s = 1 if leg[1] == "L" else -1
            st = duty * travel_cycle
            if u < duty:
                z = base_z + st * 0.5 - st * (u / duty)
                lift = 0.0
                a, toe = (-10.0, 30.0) if fore else (0.0, 20.0)
            else:
                v = (u - duty) / (1 - duty)
                z = base_z - st * 0.5 + st * ease5(v)
                lift = 0.025 * math.sin(math.pi * v)
                a, toe = (70.0 * math.sin(math.pi * v), 20.0) if fore else (15.0 * math.sin(math.pi * v), 10.0)
            y = CLIMB_WALL_Y + 0.004 + lift
            x = s * (0.030 if fore else 0.036)
            d = {"p": Vector((x, y, z)), "a": a, "toe": toe}
            if not fore:
                d["mode"] = "panto"
            p[leg].update(d)
        p["tail"]["yaw"] = 10.0 * math.sin(TAU * t)
        return p
    return fn


def knead_fn():
    base = P(pel=(0.0, 0.006, -0.016), pel_rot=(-3.0, 0, 0), spine=(2.0, 0, 0), head=(-6.0, 0, 0),
             earL=(4.0, 22.0, 6.0), earR=(4.0, 22.0, 6.0), blink=(0.55, 0.55), whisk=-6.0,
             tail={"lift": 62.0, "curve": -40.0, "tip": 40.0},
             HL={"p": rp("HL", df=0.010)}, HR={"p": rp("HR", df=0.010)})

    def fn(fr, t):
        p = mix(base, base, 0)
        for leg, ph in (("FL", 0.0), ("FR", 0.5)):
            u = (t * 2 + ph) % 1.0
            press = math.sin(math.pi * u) if u < 0.5 else 0.0
            lift = math.sin(math.pi * (u - 0.5) / 0.5) if u >= 0.5 else 0.0
            p[leg] = {"p": rp(leg, df=0.012 + 0.006 * lift, dz=0.018 * lift - 0.004 * press, dx=-0.004),
                      "a": 35.0 * lift - 8.0 * press, "toe": -18.0 * press + 20.0 * lift, "scap": 0.0}
        p["pel_rot"] = (-3.0, 0.0, 1.5 * math.sin(TAU * 2 * t))
        p["head"] = (-6.0 + 1.5 * math.sin(TAU * 4 * t), 0.0, 1.0 * math.sin(TAU * 2 * t))
        p["tail"]["pamp"] = 2.0
        p["tail"]["phase"] = 4 * t
        return p
    return fn


def stretch_fn():
    bow = P(pel=(0.0, 0.020, 0.004), pel_rot=(-16.0, 0, 0), spine=(-10.0, 0, 0), neck_lift=-6.0, head=(10.0, 0, 0),
            jaw=0.0, earL=(12.0, 14.0, 6.0), earR=(12.0, 14.0, 6.0), blink=(0.5, 0.5),
            tail={"lift": 40.0, "curve": -10.0, "tip": 20.0},
            FL={"p": rp("FL", df=0.120, dx=0.004), "a": -50.0, "toe": -25.0},
            FR={"p": rp("FR", df=0.115, dx=0.004), "a": -50.0, "toe": -25.0},
            HL={"p": rp("HL", df=0.004)}, HR={"p": rp("HR", df=0.004)})
    yawn = mix(bow, bow, 0)
    yawn["jaw"] = 38.0
    yawn["blink"] = (0.9, 0.9)
    yawn["earL"] = (30.0, 30.0, 14.0)
    yawn["earR"] = (30.0, 30.0, 14.0)
    yawn["tongue_curl"] = -20.0
    rear = P(pel=(0.0, -0.020, -0.012), pel_rot=(4.0, 0, 0), spine=(8.0, 0, 0), head=(4.0, 0, 0),
             tail={"lift": 10.0, "curve": 0.0},
             FL={"p": rp("FL", df=0.010)}, FR={"p": rp("FR", df=0.010)},
             HL={"p": rp("HL", df=-0.110, dz=0.010), "mode": "dir", "dir": (0.0, 0.55, -1.0), "toe": -20.0},
             HR={"p": rp("HR", df=0.010)})
    return lambda fr, t: keyed([(0, STAND), (12, bow), (18, yawn), (26, yawn), (32, bow), (40, STAND), (48, rear),
                                (54, rear), (64, STAND)], fr)


def groom_fn():
    base = mix(SIT, SIT, 0)

    def fn(fr, t):
        p = mix(base, base, 0)
        # raise the left forepaw in front of the chest (curled), lick it 4x, then wipe the face
        lick_t = (t * 4) % 1.0
        wipe = bump(t, 0.72, 0.98)
        paw = Fv(0.018 - 0.010 * wipe, 0.135 + 0.020 * wipe, 0.205 + 0.050 * wipe)
        p["FL"] = {"p": paw, "a": 105.0 - 30.0 * wipe, "toe": 40.0, "scap": -6.0}
        lick = math.sin(math.pi * lick_t) ** 2 * (1 - wipe)
        p["head"] = (-34.0 + 14.0 * lick + 30.0 * wipe, 14.0 * (1 - wipe) - 10.0 * wipe, 10.0 * (1 - wipe) + 26.0 * wipe)
        p["neck_lift"] = 6.0 - 8.0 * lick
        p["jaw"] = 10.0 * lick * (1 - wipe)
        p["tongue"] = 0.9 * lick * (1 - wipe)
        p["tongue_curl"] = -25.0 * lick
        p["blink"] = (0.55 + 0.4 * wipe, 0.55 + 0.4 * wipe)
        p["earL"] = (6.0 + 20.0 * wipe, 10.0 + 20 * wipe, 0.0)
        p["earR"] = (6.0, 10.0, 0.0)
        p["spine"] = (-26.0, 4.0, 3.0)
        return p
    return fn


def turn_fn(sign: int):
    nf = 20
    order = [("FL", 0.05, 0.40), ("FR", 0.25, 0.60), ("HL", 0.40, 0.75), ("HR", 0.58, 0.92)] if sign > 0 else \
            [("FR", 0.05, 0.40), ("FL", 0.25, 0.60), ("HR", 0.40, 0.75), ("HL", 0.58, 0.92)]

    def rotz(v, deg):
        return Quaternion((0, 0, 1), math.radians(deg)) @ v

    def fn(fr, t):
        psi = 90.0 * sign * t                     # controller yaw (linear)
        p = mix(STAND, STAND, 0)
        for leg, a, b in order:
            w0 = REST_PAW[leg].copy()             # world position at the start (model == world at t=0)
            w1 = rotz(REST_PAW[leg], 90.0 * sign)  # world position at the end
            if t <= a:
                w = w0
                z = 0.0
                fl = 0.0
            elif t >= b:
                w = w1
                z = 0.0
                fl = 0.0
            else:
                u = ease5((t - a) / (b - a))
                ang = 90.0 * sign * u
                w = rotz(w0, ang)
                z = 0.028 * math.sin(math.pi * (t - a) / (b - a))
                fl = 60.0 * math.sin(math.pi * (t - a) / (b - a))
            m = rotz(w, -psi)                     # into model space
            m.z += z
            p[leg] = {"p": m, "a": fl if leg[0] == "F" else fl * 0.3, "toe": fl * 0.3, "scap": 0.0,
                      "mode": "panto", "dir": None}
        lead = bump(t, 0.0, 0.85)
        p["spine"] = (0.0, sign * 14.0 * lead, 0.0)
        p["pel_rot"] = (0.0, -sign * 6.0 * lead, 0.0)
        p["head"] = (-4.0, sign * 28.0 * bump(t, 0.0, 0.7), 0.0)
        p["eyes"] = (sign * 12.0 * bump(t, 0.0, 0.5), 0.0)
        p["tail"].update({"yaw": -sign * 30.0 * bump(t, 0.1, 1.0), "amp": 4.0, "phase": t})
        return p
    return fn


def build_all(solver) -> list:
    acts = []
    for name, (nf, fn, loop) in clip_defs().items():
        acts.append(write_action(solver, name, nf, fn, loop))
    return acts


CONTRACT = ["idle", "idle_look", "walk", "trot", "run", "sneak", "sneak_idle", "jump_crouch", "jump_up", "fall", "land",
            "land_hard", "sit_down", "sit_idle", "stand_up", "lie_down", "sleep", "groom", "meow", "hiss", "swipe",
            "scratch", "climb", "turn_left_90", "turn_right_90", "drink", "eat", "knead", "stretch", "balance_walk",
            "pickup", "knock"]
LOOPING = {"idle", "idle_look", "walk", "trot", "run", "sneak", "sneak_idle", "fall", "sit_idle", "sleep", "groom",
           "scratch", "climb", "drink", "eat", "knead", "balance_walk"}
