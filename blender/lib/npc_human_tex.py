"""Human NPC texture synthesis (owner: creatures): albedo / roughness / AO / tangent normal
from per-texel 3D samples (SurfaceMaps) + SDF labels. Skin with tone variation, blush,
age spots, brows, lash line, lips; hair with strand streaks; garments with prints,
weave relief, hems/stitching, wear and dirt; accessories (straw hat, rubber, plastic ...).
"""
from __future__ import annotations

import math

import numpy as np

import npc_tex as X
from npc_tex import col, mix, sstep

DEFAULT_MATS = {
    "skin": dict(pattern="skin"),
    "lips": dict(pattern="lips"),
    "hair": dict(pattern="hair"),
    "hair_tie": dict(color="#7a2030", pattern="plain", rough=0.5),
    "greens": dict(color="#4f7a2a", color2="#2d4f18", pattern="leafy", rough=0.6),
}


def _rgb(c):
    return col(c) if isinstance(c, str) else np.asarray(c)


class HumanTex:
    def __init__(self, body, model, mats: dict):
        self.body = body
        self.model = model
        self.sp = body.spec
        self.names = model.label_names()
        self.mats = dict(DEFAULT_MATS)
        self.mats.update(mats)
        self.hems = {}
        for L in model.layers:
            self.hems[L.label] = getattr(L, "hems", [])
            for p in L.prims:
                self.hems.setdefault(p.label, getattr(L, "hems", []))
        hb = body.L
        self.head_c = body.h(0, 0.01, 1.49)
        self.eye = {sd: np.asarray(hb[f"eye_{sd}"]) for sd in "LR"}

    def mat(self, name):
        if name in self.mats:
            return self.mats[name]
        base = name.split("_")[0]
        if base in self.mats:
            m = dict(self.mats[base])
            # trim / sole / strap variants: slightly different shade
            if name.endswith("_sole"):
                m.update(color=m.get("sole", "#2b2622"), pattern="rubber", rough=0.75)
            elif name.endswith("_strap") or name.endswith("_ribbon"):
                m.update(color=m.get("strap", m.get("color2", m.get("color", "#333333"))), pattern="plain", rough=0.55)
            elif name.endswith("_trim"):
                m.update(color=m.get("trim", m.get("color", "#cccccc")))
            elif name.endswith("_tip"):
                m.update(color="#1d1b19", pattern="rubber", rough=0.7)
            elif name.endswith("_visor"):
                m.update(color=m.get("visor", "#3a3836"), pattern="plastic", rough=0.25)
            elif name.endswith("_brim"):
                m.update(color=m.get("brim", m.get("color")))
            elif name.endswith("_ring"):
                m.update(color="#8a7350", pattern="plain", rough=0.7)
            elif name.endswith("_handle"):
                m.update(pattern="plastic")
            return m
        return dict(color="#808080", pattern="plain", rough=0.6)

    # ------------------------------------------------------------------
    def hem_dist(self, label, P):
        hs = self.hems.get(label, [])
        d = np.full(len(P), 1.0)
        for hm in hs:
            if hm[0] == "z":
                dd = np.abs(P[:, 2] - hm[1])
            else:
                pt, n = np.asarray(hm[1]), np.asarray(hm[2])
                n = n / np.linalg.norm(n)
                dd = np.abs((P - pt) @ n)
                dd = np.where(np.linalg.norm(P - pt, axis=1) < 0.25, dd, 1.0)
            d = np.minimum(d, dd)
        return d

    # ------------------------------------------------------------------
    def albedo_rough(self, P, N, lab, ao):
        """Returns linear albedo (K,3), roughness (K,), metallic (K,), height-type ids."""
        K = len(P)
        alb = np.zeros((K, 3))
        rough = np.full(K, 0.6)
        metal = np.zeros(K)
        for li, name in enumerate(self.names):
            m = lab == li
            if not m.any():
                continue
            a, r, mt = self._mat_eval(name, P[m], N[m], ao[m])
            alb[m] = a
            rough[m] = r
            metal[m] = mt
        # cavity darkening (subtle; the real AO goes to the ORM map)
        alb *= (0.72 + 0.28 * ao)[:, None]
        return alb, rough, metal

    def _mat_eval(self, name, P, N, ao):
        md = self.mat(name)
        pat = md.get("pattern", "plain")
        seed = self.sp.seed
        K = len(P)
        if pat == "skin":
            return self._skin(P, N)
        if pat == "lips":
            return self._lips(P)
        if pat == "hair":
            return self._hair(P, N)
        base = _rgb(md.get("color", "#808080"))
        c2 = _rgb(md.get("color2", "#ffffff"))
        r0 = md.get("rough", 0.65)
        macro = X.fbm(P, 6.0, 3, seed + 3)
        fine = X.fbm(P, 90.0, 2, seed + 4)
        a = base[None] * (1 + 0.07 * macro[:, None] + 0.035 * fine[:, None])
        r = np.full(K, r0) + 0.05 * macro
        mt = np.zeros(K)
        if pat == "floral":
            sz = md.get("scale", 0.045)
            d, cid, fp = X.cells(P, sz, seed + 9)
            rel = P - fp
            ang = np.arctan2(rel[:, 2], rel[:, 0] + rel[:, 1])
            petal = 0.32 * sz * (0.75 + 0.25 * np.cos(5 * ang + cid * 6.28))
            flower = sstep(petal, petal * 0.8, d)
            center = sstep(0.09 * sz, 0.06 * sz, d)
            c3 = _rgb(md.get("color3", "#e9d36a"))
            leaf_d, lid, lp = X.cells(P + 0.013, sz * 0.7, seed + 19)
            leaf = sstep(0.16 * sz, 0.11 * sz, leaf_d) * (lid > 0.55)
            cl = _rgb(md.get("leaf", "#4d6b3c"))
            pick = (cid > 0.5)[:, None]
            fc = np.where(pick, c2[None], c2[None] * 0.8 + 0.2 * c3[None])
            a = mix(a, cl[None] * (1 + 0.05 * macro[:, None]), leaf * 0.85)
            a = mix(a, fc, flower * 0.92)
            a = mix(a, c3[None], center)
        elif pat in ("plaid", "check"):
            sz = md.get("scale", 0.05)
            # triplanar projection (front/back: x-z, sides: y-z, tops: x-y)
            ax = np.argmax(np.abs(N), 1)
            u = np.where(ax == 1, P[:, 0], np.where(ax == 0, P[:, 1], P[:, 0]))
            v = np.where(ax == 2, P[:, 1], P[:, 2])
            bu = (np.sin(2 * np.pi * u / sz) > 0.35).astype(float)
            bv = (np.sin(2 * np.pi * v / sz) > 0.35).astype(float)
            thin_u = (np.abs(np.sin(2 * np.pi * u / sz * 3)) > 0.96).astype(float)
            thin_v = (np.abs(np.sin(2 * np.pi * v / sz * 3)) > 0.96).astype(float)
            c3 = _rgb(md.get("color3", "#e0d8c0"))
            k = np.clip(0.45 * bu + 0.45 * bv, 0, 1)
            a = mix(a, c2[None] * (1 + 0.05 * macro[:, None]), k)
            a = mix(a, c3[None], np.clip(thin_u + thin_v, 0, 1) * 0.7)
        elif pat == "stripes":
            sz = md.get("scale", 0.02)
            st = (np.sin(2 * np.pi * P[:, 2] / sz) > 0.5).astype(float)
            a = mix(a, c2[None], st * 0.9)
        elif pat == "denim":
            tw = np.sin((P[:, 2] * 1.0 + np.arctan2(P[:, 0], -P[:, 1]) * 0.12) * 2 * np.pi / 0.0035)
            a = a * (1 + 0.06 * tw[:, None])
            fade = sstep(0.2, 0.9, X.fbm(P * np.array([3, 3, 1.2]), 8.0, 2, seed + 21) * 0.5 + 0.5)
            a = mix(a, a * 1.45, fade * 0.35)
            r = r + 0.05
        elif pat == "satin":
            r = r0 + 0.08 * X.fbm(P, 20.0, 2, seed + 23)
            a = base[None] * (1 + 0.04 * macro[:, None])
        elif pat == "rubber":
            dirt = sstep(0.0, 0.6, X.fbm(P, 25.0, 3, seed + 25)) * sstep(0.25, 0.0, P[:, 2])
            a = mix(a, col("#6b5a45")[None], dirt * 0.55)
            r = r0 - 0.2 * (1 - dirt) + 0.05 * fine
            scuff = sstep(0.75, 0.95, X.ridged(P, 45.0, 2, seed + 26))
            r = r + 0.15 * scuff
        elif pat == "plastic":
            scr = sstep(0.82, 0.97, X.ridged(P * np.array([1, 1, 4]), 60.0, 2, seed + 27))
            r = r0 + 0.25 * scr + 0.03 * fine
            a = a * (1 - 0.04 * scr[:, None])
        elif pat == "straw":
            # nón lá: palm leaf strips radiating from the apex, bamboo rings, sun-bleaching, stains
            top = self.body.L["head_top"]
            rel = P - top
            ang = np.arctan2(rel[:, 0], rel[:, 1])
            rad = np.sqrt(rel[:, 0] ** 2 + rel[:, 1] ** 2)
            strips = np.abs(np.sin(ang * 64))
            grain = X.fbm(np.stack([np.cos(ang) * 40, np.sin(ang) * 40, rad * 3], 1), 1.0, 3, seed + 31)
            rings = np.exp(-((np.mod(rad, 0.034) - 0.017) / 0.0016) ** 2)
            a = base[None] * (0.88 + 0.12 * strips[:, None] + 0.10 * grain[:, None])
            a = mix(a, base[None] * 0.62, rings * 0.55)
            bleach = sstep(-0.2, 0.6, X.fbm(P, 9.0, 3, seed + 33))
            a = mix(a, col("#d9cfae")[None], bleach * 0.35 * (N[:, 2] > 0.2))
            stain = sstep(0.55, 0.9, X.fbm(P, 14.0, 3, seed + 34))
            a = mix(a, col("#7d6440")[None], stain * 0.35)
            r = 0.72 + 0.1 * grain
        elif pat == "weave_plastic":
            u = np.arctan2(P[:, 0] - P[:, 0].mean(), P[:, 1] - P[:, 1].mean()) * 30
            v = P[:, 2] * 260
            chk = (np.sign(np.sin(u)) * np.sign(np.sin(v)) > 0).astype(float)
            a = mix(a, a * 0.75, chk * 0.6)
            r = 0.4 + 0.15 * chk
        elif pat == "leafy":
            v = X.fbm(P, 60.0, 3, seed + 41)
            a = mix(base[None], c2[None], sstep(-0.3, 0.4, v))
            r = 0.55 + 0.1 * v
        elif pat == "metal":
            mt[:] = 1.0
            r = r0 + 0.1 * fine
        elif pat == "knit":
            rib = np.abs(np.sin(np.arctan2(P[:, 0], -P[:, 1]) * 180))
            a = a * (0.92 + 0.12 * rib[:, None])
        # generic fabric wear: lighter on exposed convex edges, dirt near hems & low
        if pat in ("plain", "floral", "plaid", "check", "stripes", "denim", "knit", "satin"):
            hd = self.hem_dist(name, P)
            stitch = sstep(0.0035, 0.0015, np.abs(hd - 0.009)) * (np.sin(np.einsum("ij,j->i", P, (37, 41, 43)) * 600) > -0.2)
            a = mix(a, a * 0.7, stitch * 0.5)
            hem_wear = sstep(0.006, 0.0, hd)
            a = mix(a, a * 1.15 + 0.01, hem_wear * 0.4)
            low = sstep(0.35, 0.05, P[:, 2])
            a = mix(a, col("#5a4b3a")[None], low * 0.25 * sstep(-0.2, 0.5, macro))
            wear = sstep(0.55, 0.85, ao) * sstep(0.2, 0.7, X.fbm(P, 18.0, 2, seed + 51))
            a = a * (1 + 0.06 * wear[:, None])
            r = r + md.get("sheen_rough", 0.0)
        return np.clip(a, 0.012, 0.88), np.clip(r, 0.04, 1.0), mt

    # ------------------------------------------------------------------
    def _face_local(self, P):
        """Coordinates relative to the head (metres in head scale units)."""
        return (P - self.body.neck_top) / self.body.hs + np.array([0, 0, 1.405])

    def _skin(self, P, N):
        sp = self.sp
        seed = sp.seed
        base = col(sp.skin)
        Q = self._face_local(P)
        K = len(P)
        macro = X.fbm(P, 9.0, 3, seed + 61)
        mott = X.fbm(P, 55.0, 3, seed + 62)
        a = base[None] * (1 + 0.06 * macro[:, None] + 0.04 * mott[:, None])
        # warmth / redness: cheeks, nose tip, ears, knuckles, elbows, knees
        red = np.zeros(K)
        on_head = Q[:, 2] > 1.36
        for sd in (1, -1):
            red += np.exp(-np.sum(((Q - np.array([0.040 * sd, -0.064, 1.452])) / np.array([0.022, 0.03, 0.018])) ** 2,
                                  1)) * on_head
            red += 0.8 * np.exp(-np.sum(((Q - np.array([0.071 * sd, 0.012, 1.474])) / 0.02) ** 2, 1)) * on_head
        red += 0.8 * np.exp(-np.sum(((Q - np.array([0, -0.10, 1.445])) / 0.012) ** 2, 1)) * on_head
        for nm in ("knee", "elbow", "knuckle"):
            for sd in "LR":
                c = np.asarray(self.body.L[f"{nm}_{sd}"])
                red += 0.5 * np.exp(-np.sum((P - c) ** 2, 1) / (0.035 * self.body.s) ** 2)
        tint = col("#c46a5c")
        a = mix(a, a * 0.55 + tint[None] * 0.45, np.clip(red, 0, 1) * 0.30)
        # sun tan on forearms/face/neck vs paler upper arms (covered by sleeves anyway)
        # lash line + soft brows
        for sd, nm in ((1, "L"), (-1, "R")):
            e = self.eye[nm]
            q = (P - e) / self.body.hs
            # lash line: just around the aperture edge (upper lid stronger)
            r_ap = np.sqrt((q[:, 0] / 0.0155) ** 2 + (q[:, 2] / 0.0068) ** 2)
            front = q[:, 1] < -0.004
            lash = sstep(1.35, 1.0, r_ap) * sstep(0.7, 0.95, r_ap) * front
            lash_up = lash * (q[:, 2] > -0.001)
            a = mix(a, col("#2b1d17")[None], np.clip(lash_up * 0.85 + lash * 0.25, 0, 1))
            # upper lid crease shadow
            crease = np.exp(-((q[:, 2] - 0.0085) / 0.0022) ** 2) * sstep(0.022, 0.012, np.abs(q[:, 0])) * front
            a = mix(a, a * 0.78, crease * 0.5)
            # brows: arc above the eye
            bx = q[:, 0] * sd
            arc_z = 0.0205 + 0.006 * np.cos(np.clip(bx / 0.026, -1.5, 1.5) * 1.2) - 0.0025 * (bx > 0.01) * (bx - 0.01) / 0.01
            thick = 0.0052 * (1 - 0.45 * sstep(-0.005, 0.024, bx))
            bd = np.abs(q[:, 2] - arc_z)
            brow = sstep(thick, thick * 0.4, bd) * sstep(0.031, 0.02, np.abs(bx - 0.003)) * (q[:, 1] < 0.0)
            strands = 0.6 + 0.4 * X.aniso(P, np.array([sd * 0.95, 0, 0.3]) / 1.0, 2500.0, 150.0, seed + 70)
            hc = col(sp.hair_col if sp.age < 0.7 else "#6b625a")
            a = mix(a, hc[None] * 0.85, np.clip(brow * strands * 1.15, 0, 1) * (0.92 - 0.25 * sp.age))
        # age: spots + under-eye darkness
        if sp.age > 0.55:
            d, cid, _ = X.cells(P, 0.018, seed + 71)
            spot = sstep(0.0035, 0.0015, d) * (cid > 0.55) * on_head
            spot2 = sstep(0.004, 0.002, d) * (cid > 0.7) * (P[:, 2] < 1.2 * self.body.s)
            a = mix(a, a * 0.62 + col("#6a4a32")[None] * 0.2, np.clip(spot + 0.6 * spot2, 0, 1) * 0.6)
        if sp.beard > 0:
            beard_zone = on_head & (Q[:, 1] < -0.01) & (Q[:, 2] < 1.43)
            bz = beard_zone * sstep(1.445, 1.415, Q[:, 2])
            stub = 0.5 + 0.5 * X.vnoise(P, 3000.0, seed + 72)
            a = mix(a, a * 0.55 + col("#2a2420")[None] * 0.12, bz * sp.beard * (0.5 + 0.5 * stub))
        # nails (finger tips, dorsal)
        for sd in "LR":
            tip = np.asarray(self.body.L[f"fingertip_{sd}"])
            dn = np.linalg.norm(P - tip, axis=1)
            nail = sstep(0.05 * self.body.s, 0.03 * self.body.s, dn) * 0.0
            a = mix(a, col("#e8c0b0")[None], nail)
        rough = 0.52 + 0.06 * mott
        # T-zone oilier
        tz = np.exp(-np.sum(((Q - np.array([0, -0.09, 1.48])) / np.array([0.02, 0.03, 0.05])) ** 2, 1)) * on_head
        rough = rough - 0.12 * tz
        return np.clip(a, 0.02, 0.85), rough, np.zeros(K)

    def _lips(self, P):
        sp = self.sp
        Q = self._face_local(P)
        base = col(sp.lips)
        sk = col(sp.skin)
        a = mix(sk[None], base[None], 0.75) * (1 + 0.05 * X.fbm(P, 400.0, 2, sp.seed + 81)[:, None])
        # blend to skin at the lip border (soft vermilion edge) and toward the corners
        d_mid = np.abs(Q[:, 2] - 1.4152)
        edge = np.clip(sstep(0.0035, 0.0068, d_mid) + sstep(0.016, 0.024, np.abs(Q[:, 0])), 0, 1)
        a = mix(a, sk[None] * 0.97, edge * 0.85)
        # mouth line
        line = sstep(0.0012, 0.0002, d_mid) * (Q[:, 1] < -0.075) * sstep(0.024, 0.015, np.abs(Q[:, 0]))
        a = mix(a, col("#4a2624")[None], line * 0.8)
        r = 0.38 + 0.08 * X.fbm(P, 500.0, 2, sp.seed + 82)
        return np.clip(a, 0.02, 0.8), r, np.zeros(len(P))

    def _hair_axis(self, P):
        """Strand direction field: from the hairline/crown toward the bun / nape."""
        style = None
        for L in self.model.layers:
            if hasattr(L, "hair_style"):
                style = L.hair_style
        hc = self.head_c
        if style in ("bun", "ponytail"):
            target = self.body.h(0, 0.11, 1.50)
            dirs = target - P
        else:
            crown = self.body.h(0, 0.045, 1.60)
            dirs = P - crown
            dirs[:, 2] -= 0.02
        n = P - hc
        n /= np.linalg.norm(n, axis=1, keepdims=True)
        dirs -= np.einsum("ij,ij->i", dirs, n)[:, None] * n
        dirs /= np.maximum(np.linalg.norm(dirs, axis=1, keepdims=True), 1e-6)
        return dirs

    def _hair(self, P, N):
        sp = self.sp
        base = col(sp.hair_col)
        ax = self._hair_axis(P)
        s1 = X.aniso(P, ax, 420.0, 10.0, sp.seed + 91, 2)        # strand clumps
        clump = X.aniso(P, ax, 120.0, 5.0, sp.seed + 95, 2)      # combed bands
        a = base[None] * (0.82 + 0.20 * clump[:, None] + 0.10 * s1[:, None])
        if sp.age > 0.7:
            grey = sstep(-0.2, 0.5, X.aniso(P, ax, 500.0, 12.0, sp.seed + 93))
            a = mix(a, col("#dcd8d0")[None], grey * 0.45)
            a = mix(a, col("#5a5450")[None], sstep(0.55, 0.95, X.aniso(P, ax, 900.0, 15.0, sp.seed + 94)) * 0.35)
        r = 0.56 + 0.05 * s1 - 0.04 * clump
        return np.clip(a, 0.015, 0.8), r, np.zeros(len(P))

    # ------------------------------------------------------------------
    def height(self, P, lab):
        """Micro-relief (metres) used for the tangent-space normal map."""
        h = np.zeros(len(P))
        seed = self.sp.seed
        for li, name in enumerate(self.names):
            m = lab == li
            if not m.any():
                continue
            Pm = P[m]
            md = self.mat(name)
            pat = md.get("pattern", "plain")
            if pat == "skin":
                v = 0.00006 * X.fbm(Pm, 700.0, 2, seed + 101)
                if self.sp.age > 0.5:
                    Q = self._face_local(Pm)
                    fh = np.exp(-((Q[:, 1] + 0.08) / 0.02) ** 2) * (Q[:, 2] > 1.50) * (Q[:, 2] < 1.55)
                    v -= 0.00035 * self.sp.age * fh * np.maximum(np.sin(Q[:, 2] * 2 * np.pi / 0.008), 0) ** 2
                    for sd in (1, -1):
                        cf = np.exp(-np.sum(((Q - np.array([0.058 * sd, -0.055, 1.486])) / 0.012) ** 2, 1))
                        ang = np.arctan2(Q[:, 2] - 1.486, (Q[:, 0] - 0.058 * sd) * sd)
                        v -= 0.0003 * self.sp.age * cf * np.maximum(np.sin(ang * 9), 0) ** 3
                        nl = np.exp(-(((Q[:, 0] * sd - 0.028) - (1.445 - Q[:, 2]) * 0.4) / 0.004) ** 2) \
                            * (Q[:, 2] < 1.452) * (Q[:, 2] > 1.405) * (Q[:, 1] < -0.06)
                        v -= 0.0006 * self.sp.age * nl
                h[m] = v
            elif pat == "hair":
                ax = self._hair_axis(Pm)
                h[m] = 0.00005 * X.aniso(Pm, ax, 420.0, 10.0, seed + 91, 2) + \
                    0.00035 * X.aniso(Pm, ax, 120.0, 5.0, seed + 95, 2)
            elif pat in ("plain", "floral", "plaid", "check", "stripes", "denim", "knit", "satin"):
                around, up = X.cyl_axes(Pm)
                wv = 0.00010 * X.aniso(Pm, up, 900.0, 80.0, seed + 104, 1) + \
                    0.00008 * X.aniso(Pm, around, 900.0, 80.0, seed + 105, 1)
                # soft fabric folds: low-frequency stretched noise (gravity drape)
                folds = 0.0016 * X.aniso(Pm, up, 28.0, 5.0, seed + 106, 3)
                hd = self.hem_dist(name, Pm)
                hem = -0.0006 * sstep(0.0035, 0.0012, np.abs(hd - 0.009)) + 0.0004 * sstep(0.004, 0.0, hd)
                h[m] = wv + folds * md.get("folds", 1.0) + hem
            elif pat == "straw":
                top = self.body.L["head_top"]
                rel = Pm - top
                ang = np.arctan2(rel[:, 0], rel[:, 1])
                rad = np.sqrt(rel[:, 0] ** 2 + rel[:, 1] ** 2)
                h[m] = 0.00045 * np.abs(np.sin(ang * 64)) - 0.0006 * np.exp(-((np.mod(rad, 0.034) - 0.017) / 0.002) ** 2)
            elif pat == "rubber":
                h[m] = 0.00015 * X.fbm(Pm, 200.0, 2, seed + 107)
            elif pat == "weave_plastic":
                u = np.arctan2(Pm[:, 0] - Pm[:, 0].mean(), Pm[:, 1] - Pm[:, 1].mean()) * 30
                v = Pm[:, 2] * 260
                h[m] = 0.0006 * np.sign(np.sin(u)) * np.sign(np.sin(v)) * np.abs(np.sin(u) * np.sin(v)) ** 0.3
        return h
