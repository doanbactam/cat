"""Animation authoring helpers for NPC rigs (owner: creatures).

Clips are written as Python functions `pose(t) -> Pose` (t in seconds). A Pose holds,
per bone, a rotation *delta relative to the parent* expressed in ARMATURE axes
(X = character's left, Y = back, Z = up; front is -Y) plus optional armature-space
translations. `bake_clip` converts those into bone-local quaternions and keys every
frame into its own Action (one Action == one Godot animation).
"""
from __future__ import annotations

import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

FPS = 30


def q(axis, deg) -> Quaternion:
    return Quaternion(Vector(axis).normalized(), math.radians(deg))


def qx(d):
    return q((1, 0, 0), d)


def qy(d):
    return q((0, 1, 0), d)


def qz(d):
    return q((0, 0, 1), d)


def qe(x=0.0, y=0.0, z=0.0) -> Quaternion:
    """Euler-ish composition (applied Z, then X, then Y), degrees, armature axes."""
    return qy(y) @ qx(x) @ qz(z)


class Pose:
    def __init__(self):
        self.rot: dict[str, Quaternion] = {}
        self.loc: dict[str, Vector] = {}

    def r(self, bone: str, quat: Quaternion, side: str | None = None) -> "Pose":
        """Compose (pre-multiply) a rotation delta onto `bone`. If `side` is 'R' the
        rotation is mirrored across the X=0 plane (Y/Z rotation components negate)."""
        if side == "R":
            quat = Quaternion((quat.w, quat.x, -quat.y, -quat.z))
        cur = self.rot.get(bone, Quaternion())
        self.rot[bone] = quat @ cur
        return self

    def rl(self, base: str, quat: Quaternion) -> "Pose":
        """Same delta on base_L and mirrored on base_R."""
        self.r(base + "_L", quat)
        self.r(base + "_R", quat, "R")
        return self

    def t(self, bone: str, vec) -> "Pose":
        cur = self.loc.get(bone, Vector())
        self.loc[bone] = cur + Vector(vec)
        return self


def smoothstep(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def wave(t, period, phase=0.0):
    return math.sin(2 * math.pi * (t / period + phase))


def noise1(t, seed=0, period=3.0):
    """Smooth pseudo-random 1D signal in [-1,1] that loops every `period` (sum of harmonics)."""
    rng = np.random.default_rng(seed)
    a = rng.uniform(0.3, 1.0, 3)
    ph = rng.uniform(0, 1, 3)
    s = sum(a[i] * math.sin(2 * math.pi * ((i + 1) * t / period + ph[i])) for i in range(3))
    return s / a.sum()


def ik2(hip, target, l1, l2, bend_sign=-1.0):
    """Planar 2-bone IK in the YZ plane. Pitch angles are measured from straight down
    (0) toward +Y (positive). bend_sign=-1 puts the middle joint toward -Y (a knee),
    +1 toward +Y (a dog's/bird's hock or a human elbow seen from the side).
    Returns (pitch1, pitch2, middle_joint (y, z))."""
    dy = target[0] - hip[0]
    dz = target[1] - hip[1]
    d = math.hypot(dy, dz)
    d = min(max(d, abs(l1 - l2) + 1e-4), (l1 + l2) * 0.9995)
    phi0 = math.atan2(dy, -dz)
    cos_a = (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)
    a = math.acos(min(max(cos_a, -1.0), 1.0))
    p1 = phi0 + bend_sign * a
    ky = hip[0] + l1 * math.sin(p1)
    kz = hip[1] - l1 * math.cos(p1)
    p2 = math.atan2(target[0] - ky, -(target[1] - kz))
    return p1, p2, (ky, kz)


def pitch_of(a, b) -> float:
    """Pitch (from straight down toward +Y) of the segment a->b, using Y/Z only."""
    return math.atan2(b[1] - a[1], -(b[2] - a[2]))


class Animator:
    def __init__(self, arm_ob):
        self.arm = arm_ob
        self.rest = {}
        for b in arm_ob.data.bones:
            self.rest[b.name] = b.matrix_local.to_3x3().copy()
        for pb in arm_ob.pose.bones:
            pb.rotation_mode = "QUATERNION"
        self.actions = []
        self.scaled: set = set()

    def _local(self, bone, qa: Quaternion) -> Quaternion:
        R = self.rest[bone]
        M = R.inverted() @ qa.to_matrix() @ R
        return M.to_quaternion()

    def bake_clip(self, name: str, pose_fn, frames: int, loop: bool) -> bpy.types.Action:
        arm = self.arm
        if arm.animation_data is None:
            arm.animation_data_create()
        act = bpy.data.actions.new(name)
        act.use_fake_user = True
        arm.animation_data.action = act
        prev: dict[str, Quaternion] = {}
        last = frames if loop else frames - 1
        for f in range(0, last + 1):
            t = (f % frames if loop else f) / FPS
            p = pose_fn(t)
            for pb in arm.pose.bones:
                qa = p.rot.get(pb.name, Quaternion())
                ql = self._local(pb.name, qa)
                if pb.name in prev and prev[pb.name].dot(ql) < 0:
                    ql = Quaternion((-ql.w, -ql.x, -ql.y, -ql.z))
                prev[pb.name] = ql
                pb.rotation_quaternion = ql
                la = p.loc.get(pb.name)
                if la is not None:
                    pb.location = self.rest[pb.name].inverted() @ Vector(la)
                else:
                    pb.location = Vector()
                pb.keyframe_insert("rotation_quaternion", frame=f + 1)
                pb.keyframe_insert("location", frame=f + 1)
                scl = getattr(p, "scl", {})
                if pb.name in scl or pb.name in self.scaled:
                    sv = scl.get(pb.name, 1.0)
                    pb.scale = Vector((sv, sv, sv))
                    pb.keyframe_insert("scale", frame=f + 1)
                    self.scaled.add(pb.name)
        act.use_frame_range = True
        act.frame_start = 1
        act.frame_end = last + 1
        act["loop"] = bool(loop)
        arm.animation_data.action = None
        for pb in arm.pose.bones:
            pb.rotation_quaternion = Quaternion()
            pb.location = Vector()
            pb.scale = Vector((1, 1, 1))
        self.actions.append(act)
        return act

    def set_pose(self, p: Pose) -> None:
        """Apply a Pose statically (for previews)."""
        for pb in self.arm.pose.bones:
            pb.rotation_quaternion = self._local(pb.name, p.rot.get(pb.name, Quaternion()))
            la = p.loc.get(pb.name)
            pb.location = self.rest[pb.name].inverted() @ Vector(la) if la is not None else Vector()
            sv = getattr(p, "scl", {}).get(pb.name, 1.0)
            pb.scale = Vector((sv, sv, sv))
        bpy.context.view_layer.update()
