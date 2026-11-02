"""Human NPC clip set (owner: creatures).

Clips (all in place, 30 fps): idle(L), walk(L), sit(L, on a 0.25 m plastic stool), talk(L),
sell(L), pet_cat(L, crouched stroking), shoo(L), look_around(L), carry(L, walking with a load
held at the waist), phone(L). Style per character: stoop, gait scale, walk speed.
"""
from __future__ import annotations

import math

import numpy as np
from mathutils import Quaternion, Vector

import npc_anim as A
from npc_anim import Pose, qx, qy, qz, q, wave, noise1, ease, smoothstep

CLIPS = {  # name: (frames, loop)
    "idle": (120, True), "walk": (32, True), "sit": (120, True), "talk": (120, True), "sell": (120, True),
    "pet_cat": (90, True), "shoo": (40, True), "look_around": (180, True), "carry": (32, True),
    "phone": (150, True),
}


class HumanAnim:
    def __init__(self, body):
        self.body = body
        sp = body.spec
        self.sp = sp
        L = body.L
        self.s = body.s
        self.hip = {k: np.array(L[f"hip_{k}"]) for k in "LR"}
        self.knee = {k: np.array(L[f"knee_{k}"]) for k in "LR"}
        self.ankle = {k: np.array(L[f"ankle_{k}"]) for k in "LR"}
        self.ball = {k: np.array(L[f"ball_{k}"]) for k in "LR"}
        self.l1 = float(np.linalg.norm(self.knee["L"] - self.hip["L"]))
        self.l2 = float(np.linalg.norm(self.ankle["L"] - self.knee["L"]))
        self.p1r = A.pitch_of(self.hip["L"], self.knee["L"])
        self.p2r = A.pitch_of(self.knee["L"], self.ankle["L"])
        d = body.d_ua
        self.elbow_axis = Vector(np.cross(d, (0, -1, 0)))
        self.finger_axis = Vector(np.cross(body.d_fa, body.n_palm))
        self.lower = 34.0       # arm lowering from the A-pose
        self.ankle_h = float(self.ankle["L"][2])
        self.clips = dict(CLIPS)
        if sp.gait < 0.9:      # elderly: slower cadence
            self.clips["walk"] = (38, True)
            self.clips["carry"] = (38, True)
        self.foot_len = float(np.linalg.norm(self.ball["L"] - self.ankle["L"]))

    # ---------------------------------------------------------------
    def base(self, t, p: Pose | None = None, breathe=1.0, arms=True) -> Pose:
        p = p or Pose()
        sp = self.sp
        st = sp.stoop
        br = wave(t, 4.0) * breathe
        p.r("spine_01", qx(4 * st))
        p.r("spine_02", qx(7 * st + 0.6 * br))
        p.r("chest", qx(9 * st - 0.8 * br))
        p.r("neck", qx(-6 * st))
        p.r("head", qx(-10 * st))
        if arms:
            for sd in "LR":
                p.r(f"upperarm_{sd}", qy(self.lower) @ Quaternion(), sd)
                p.r(f"forearm_{sd}", q(self.elbow_axis, 12 + 6 * st), sd)
                p.r(f"fingers_{sd}", q(self.finger_axis, 18), sd)
                p.r(f"clavicle_{sd}", qy(-2 + 0.5 * br), sd)
        return p

    def arm(self, p, sd, fwd=0.0, out=0.0, elbow=0.0, twist=0.0, wrist=0.0, fingers=0.0, wrist_side=0.0):
        """Add arm deltas on top of the base pose. fwd: raise forward (deg), out: abduct (deg),
        elbow: extra flexion, twist: upper-arm twist about the arm axis, wrist: flex."""
        ua = p.rot.get(f"upperarm_{sd}", Quaternion())
        p.rot[f"upperarm_{sd}"] = ua
        if twist:
            tq = q(Vector(self.body.d_ua), twist)
            if sd == "R":
                tq = Quaternion((tq.w, tq.x, -tq.y, -tq.z))
            p.rot[f"upperarm_{sd}"] = p.rot[f"upperarm_{sd}"] @ tq
        if out:
            p.r(f"upperarm_{sd}", qy(-out), sd)
        if fwd:
            p.r(f"upperarm_{sd}", qx(-fwd), sd)
        if elbow:
            p.r(f"forearm_{sd}", q(self.elbow_axis, elbow), sd)
        if wrist or wrist_side:
            p.r(f"hand_{sd}", q(self.elbow_axis, wrist) @ qx(wrist_side), sd)
        if fingers:
            p.r(f"fingers_{sd}", q(self.finger_axis, fingers), sd)
        return p

    def legs(self, p: Pose, pelvis_off, pelvis_pitch, targets: dict, foot_pitch: dict, toe: dict | None = None):
        """targets[sd] = (y, z) ankle target in armature space; pelvis_off (x, y, z)."""
        p.t("pelvis", pelvis_off)
        p.r("pelvis", qx(pelvis_pitch))
        pp = math.radians(pelvis_pitch)
        for sd in "LR":
            hip = self.hip[sd]
            # hip joint moves with the pelvis (rotation about the pelvis head ~ hip centre)
            hy = hip[1] + pelvis_off[1]
            hz = hip[2] + pelvis_off[2]
            ty, tz = targets[sd]
            p1, p2, _ = A.ik2((hy, hz), (ty, tz), self.l1, self.l2, bend_sign=-1.0)
            th = (p1 - self.p1r) - pp
            sh = (p2 - self.p2r) - (p1 - self.p1r)
            ft = math.radians(foot_pitch.get(sd, 0.0)) - (p2 - self.p2r)
            p.r(f"thigh_{sd}", qx(math.degrees(th)), sd)
            p.r(f"shin_{sd}", qx(math.degrees(sh)), sd)
            p.r(f"foot_{sd}", qx(math.degrees(ft)), sd)
            if toe and sd in toe:
                p.r(f"toe_{sd}", qx(-toe[sd]), sd)
        return p

    def stand_legs(self, p, drop=0.0, shift=0.0, pitch=0.0):
        tg = {sd: (self.ankle[sd][1], self.ankle_h) for sd in "LR"}
        return self.legs(p, (shift, 0.0, -drop), pitch, tg, {})

    # ---------------------------------------------------------------
    def idle(self, t):
        p = self.base(t)
        sh = 0.012 * self.s * wave(t, 4.0, 0.1)
        self.stand_legs(p, drop=0.004 + 0.003 * abs(wave(t, 4.0)), shift=sh)
        p.r("pelvis", qy(-2.0 * wave(t, 4.0, 0.1)))
        p.r("spine_02", qy(1.5 * wave(t, 4.0, 0.1)))
        p.r("head", qz(6 * noise1(t, 3, 4.0)) @ qx(2 * noise1(t, 5, 4.0)))
        p.r("neck", qz(3 * noise1(t, 3, 4.0)))
        self.arm(p, "L", fwd=2 + 2 * wave(t, 4.0), elbow=2)
        self.arm(p, "R", fwd=3 + 2 * wave(t, 4.0, 0.3), elbow=4)
        return p

    def _walk_core(self, t, period, carry=False):
        sp = self.sp
        s = self.s
        duty = 0.62
        T = period
        # stride limited by leg reach (85 % of the leg at mid-swing height)
        L = self.l1 + self.l2
        hip_z = self.hip["L"][2]
        reach = 0.985 * L
        half = sp.walk_speed * T * duty * 0.5
        # pelvis height so the leading ankle (raised ~1 cm at heel strike) is reachable
        need = hip_z - self.ankle_h - 0.010 * s - math.sqrt(max(reach ** 2 - half ** 2, 1e-4)) + 0.012 * s
        drop = min(max(need, 0.012 * s), 0.065 * s) + 0.015 * sp.stoop * s
        vert = hip_z - drop - 0.012 * s - self.ankle_h - 0.010 * s
        half = min(half, math.sqrt(max(reach ** 2 - vert ** 2, 1e-4)))
        self.walk_speed_eff = 2 * half / (T * duty)
        p = self.base(t, breathe=0.3)
        ph_L = (t / T) % 1.0
        targets, fpitch, toe = {}, {}, {}
        for sd, ph in (("L", ph_L), ("R", (ph_L + 0.5) % 1.0)):
            y0 = self.ankle[sd][1]
            if ph < duty:
                u = ph / duty
                y = y0 - half + 2 * half * u
                # heel strike: toes up then flat; heel-off after 70 % of stance
                fp = -14 * (1 - smoothstep(0.0, 0.18, u)) + 32 * smoothstep(0.62, 1.0, u)
                lift = 0.0
                # ankle rises when the heel lifts (pivot on the ball)
                ang = math.radians(max(fp, 0))
                z = self.ankle_h + self.foot_len * math.sin(ang) * 0.9
                if fp < 0:
                    z = self.ankle_h + 0.012 * s * (-fp / 14)
                toe[sd] = -fp * 0.8 if fp > 0 else 0.0
            else:
                u = (ph - duty) / (1 - duty)
                e = 0.5 - 0.5 * math.cos(math.pi * u)
                y = y0 + half - 2 * half * e
                lift = math.sin(math.pi * u) ** 1.2 * (0.075 * s * sp.gait + 0.02 * s)
                fp = 32 * (1 - smoothstep(0.0, 0.45, u)) - 14 * smoothstep(0.55, 1.0, u)
                z = self.ankle_h + lift + self.foot_len * math.sin(math.radians(max(fp, 0))) * 0.6 * (1 - u)
                toe[sd] = 10 * (1 - u)
            targets[sd] = (y, z)
            fpitch[sd] = fp
        bob = -drop - 0.012 * s * math.cos(4 * math.pi * ph_L)
        sway = 0.016 * s * math.sin(2 * math.pi * ph_L)
        self.legs(p, (sway, 0.0, bob), 2.0 + 3 * sp.stoop, targets, fpitch, toe)
        p.r("pelvis", qz(-5 * math.sin(2 * math.pi * ph_L)) @ qy(-3 * math.sin(2 * math.pi * ph_L)))
        p.r("spine_02", qz(3.5 * math.sin(2 * math.pi * ph_L)) @ qx(3 + 2 * sp.stoop))
        p.r("chest", qz(3 * math.sin(2 * math.pi * ph_L)))
        p.r("head", qz(1.5 * math.sin(2 * math.pi * ph_L)) @ qx(-2 - 3 * math.cos(4 * math.pi * ph_L) * 0.4))
        if carry:
            for sd in "LR":
                self.arm(p, sd, fwd=28, out=-14, elbow=78, twist=-25, wrist=-10, fingers=25)
            p.r("spine_02", qx(-4))
            p.r("chest", qx(-3))
        else:
            sw = 17 * sp.gait * math.cos(2 * math.pi * ph_L)
            self.arm(p, "L", fwd=-sw * 0.8 + 2, elbow=10 + max(0.0, -sw) * 0.0 + 8 * (1 + math.cos(2 * math.pi * ph_L)))
            self.arm(p, "R", fwd=sw * 0.8 + 2, elbow=10 + 8 * (1 - math.cos(2 * math.pi * ph_L)))
        return p

    def walk(self, t):
        return self._walk_core(t, self.clips["walk"][0] / A.FPS)

    def carry(self, t):
        return self._walk_core(t, self.clips["carry"][0] / A.FPS, carry=True)

    def sit(self, t):
        s = self.s
        sp = self.sp
        p = self.base(t, breathe=1.0)
        seat = 0.25
        hip_z_target = seat + 0.088 * s
        drop = self.hip["L"][2] - hip_z_target
        tg = {}
        for sd in "LR":
            tg[sd] = (self.ankle[sd][1] - 0.30 * s, self.ankle_h)
        # knees apart: thighs abducted a little
        self.legs(p, (0, 0.035 * s, -drop), -8.0, tg, {"L": 0, "R": 0})
        for sd in "LR":
            p.r(f"thigh_{sd}", qz(9) if sd == "L" else qz(-9))
        p.r("spine_01", qx(14 + 6 * sp.stoop))
        p.r("spine_02", qx(10))
        p.r("chest", qx(4))
        p.r("neck", qx(-12))
        p.r("head", qx(-12 + 3 * noise1(t, 9, 4.0)) @ qz(10 * noise1(t, 4, 4.0)))
        # forearms resting on the thighs
        for sd in "LR":
            self.arm(p, sd, fwd=40, out=-6, elbow=58, twist=-30, wrist=12, fingers=10)
        return p

    def talk(self, t):
        p = self.idle(t)
        g1 = 0.5 + 0.5 * wave(t, 2.0)
        g2 = 0.5 + 0.5 * wave(t, 4.0, 0.35)
        self.arm(p, "R", fwd=14 + 10 * g1, out=4, elbow=50 + 22 * g1, twist=-35, wrist=-12 * g1, fingers=-12)
        self.arm(p, "L", fwd=6 + 8 * g2, out=2, elbow=25 + 25 * g2, twist=-25, fingers=-8)
        p.r("head", qx(5 * wave(t, 1.0)) @ qz(8 * wave(t, 4.0, 0.2)))
        p.r("chest", qz(4 * wave(t, 4.0, 0.15)))
        open_ = max(0.0, math.sin(2 * math.pi * t * 3.2)) * (0.6 + 0.4 * math.sin(2 * math.pi * t * 0.75))
        p.r("jaw", qx(9 * open_))
        return p

    def sell(self, t):
        p = self.base(t)
        self.stand_legs(p, drop=0.006, shift=0.004 * wave(t, 4.0))
        u = 0.5 + 0.5 * wave(t, 2.0)
        p.r("spine_02", qx(9 + 3 * u))
        p.r("chest", qx(4) @ qz(-8))
        # right hand offers forward (palm up), left hand beckons
        self.arm(p, "R", fwd=48 + 10 * u, out=-5, elbow=32 - 12 * u, twist=-70, wrist=-14, fingers=-15)
        b = max(0.0, math.sin(2 * math.pi * t * 1.5))
        self.arm(p, "L", fwd=35, out=12, elbow=70, twist=-60, wrist=-25 + 30 * b, fingers=40 * b)
        p.r("head", qx(-4 + 6 * wave(t, 2.0)) @ qz(-10 + 18 * wave(t, 4.0)))
        open_ = max(0.0, math.sin(2 * math.pi * t * 2.6)) * 0.8
        p.r("jaw", qx(7 * open_))
        return p

    def pet_cat(self, t):
        s = self.s
        p = self.base(t, breathe=0.6)
        hip_z = 0.40 * s
        drop = self.hip["L"][2] - hip_z
        tg = {"L": (self.ankle["L"][1] - 0.02 * s, self.ankle_h + 0.035 * s),
              "R": (self.ankle["R"][1] + 0.10 * s, self.ankle_h + 0.05 * s)}
        self.legs(p, (0, 0.08 * s, -drop), -4.0, tg, {"L": 18, "R": 30}, toe={"L": 18, "R": 30})
        p.r("thigh_L", qz(10))
        p.r("thigh_R", qz(-14))
        p.r("spine_01", qx(16))
        p.r("spine_02", qx(16))
        p.r("chest", qx(10))
        p.r("neck", qx(5))
        p.r("head", qx(8 + 4 * wave(t, 3.0)) @ qz(5 * wave(t, 6.0)))
        stroke = math.sin(2 * math.pi * t / 1.5)
        self.arm(p, "R", fwd=58 + 12 * stroke, out=-10, elbow=12 - 6 * stroke, twist=-15, wrist=18 - 10 * stroke,
                 fingers=-10)
        self.arm(p, "L", fwd=30, out=-8, elbow=55, twist=-20, wrist=8, fingers=15)
        return p

    def shoo(self, t):
        p = self.base(t, breathe=0.0)
        T = self.clips["shoo"][0] / A.FPS
        w = math.sin(2 * math.pi * t / T * 2)
        self.stand_legs(p, drop=0.02 * self.s, shift=0.01 * self.s)
        p.r("spine_02", qx(14))
        p.r("chest", qx(6))
        p.r("head", qx(-8) @ qz(4 * w))
        self.arm(p, "R", fwd=40 + 18 * w, out=10, elbow=40 - 25 * w, twist=-50, wrist=25 * w, fingers=-15)
        self.arm(p, "L", fwd=20 + 10 * w, out=8, elbow=50, twist=-30, wrist=-15 * w, fingers=-10)
        p.r("jaw", qx(6 * max(0.0, w)))
        return p

    def look_around(self, t):
        p = self.idle(t)
        T = self.clips["look_around"][0] / A.FPS
        u = t / T
        k = (smoothstep(0.08, 0.22, u) - smoothstep(0.38, 0.55, u)) * 1.0 \
            - (smoothstep(0.55, 0.68, u) - smoothstep(0.85, 0.98, u)) * 1.0
        p.r("head", qz(42 * k) @ qx(-5 * abs(k)))
        p.r("neck", qz(22 * k))
        p.r("chest", qz(14 * k))
        p.r("spine_02", qz(6 * k))
        return p

    def phone(self, t):
        p = self.idle(t)
        self.arm(p, "R", fwd=55, out=8, elbow=128, twist=-70, wrist=-18, fingers=10)
        self.arm(p, "L", fwd=25, out=-18, elbow=95, twist=-55, fingers=20)
        p.r("head", qy(-9) @ qx(4 * wave(t, 5.0)) @ qz(-8 + 6 * noise1(t, 7, 5.0)))
        open_ = max(0.0, math.sin(2 * math.pi * t * 2.8)) * (0.5 + 0.5 * math.sin(2 * math.pi * t / 5.0))
        p.r("jaw", qx(7 * open_))
        return p

    def bake_all(self, animator):
        for name, (frames, loop) in self.clips.items():
            animator.bake_clip(name, getattr(self, name), frames, loop)
