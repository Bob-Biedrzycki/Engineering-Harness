"""3D frame solver (direct stiffness) for welded skid frames, grillages, stands and legs.

What it does
- Linear static analysis of 3D beam-column members (12 DOF Timoshenko elements: axial, two-plane bending with
  optional shear deformation, St Venant torsion). Each member is split into sub-elements (default 8, plus a cut at
  every member point load) so internal forces and deflections are reported along the member.
- End moment releases (pins) by static condensation.
- Supports per DOF: "fixed", "free", a spring stiffness (number, lb/in or lb-in/rad), or "contact" on a
  translational DOF: compression only (the floor, a fork tine, a leveling foot). Contacts are solved by an active
  set: a contact pulling in tension is released; a released contact the structure would pass through is restored.
- Second order (P-Delta) by iterating the geometric stiffness from the member axial forces.
- Elastic buckling load factor (linear eigen-buckling) and natural frequencies (lumped mass, shift-invert).

Coordinates: global X, Y horizontal, Z up. Gravity acts in -Z. Units: in, lb, psi, lb-in.

Local member axes: x from end i to end j. For a non-vertical member local y is the projection of global +Z
(so a beam's depth H, which lies along local y, is vertical); local z = x cross y. For a vertical member local
y = global +X. "roll" (degrees) rotates y and z about x; "ref" (a global vector) sets local y directly.

Validated in tests/ against closed-form beams, Euler columns, portal frames and modal frequencies.
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from . import materials as mats
from . import sections as secs
from .core import InputError

DOFS = ("ux", "uy", "uz", "rx", "ry", "rz")


# =============================================================== element matrices
def local_stiffness(E, G, A, Iy, Iz, J, L, Avy=0.0, Avz=0.0):
    """12x12 local stiffness; DOF order per end: ux uy uz rx ry rz. Shear deformation when Av > 0."""
    k = np.zeros((12, 12))
    phy = 12 * E * Iz / (G * Avy * L * L) if Avy > 0 else 0.0     # bending in x-y (uy, rz)
    phz = 12 * E * Iy / (G * Avz * L * L) if Avz > 0 else 0.0     # bending in x-z (uz, ry)
    ea, gj = E * A / L, G * J / L
    k[0, 0] = k[6, 6] = ea
    k[0, 6] = k[6, 0] = -ea
    k[3, 3] = k[9, 9] = gj
    k[3, 9] = k[9, 3] = -gj
    # x-y plane: uy (1,7) rz (5,11)
    a = E * Iz / (L ** 3 * (1 + phy))
    idx = [1, 5, 7, 11]
    m = a * np.array([[12, 6 * L, -12, 6 * L],
                      [6 * L, (4 + phy) * L * L, -6 * L, (2 - phy) * L * L],
                      [-12, -6 * L, 12, -6 * L],
                      [6 * L, (2 - phy) * L * L, -6 * L, (4 + phy) * L * L]])
    k[np.ix_(idx, idx)] = m
    # x-z plane: uz (2,8) ry (4,10)
    b = E * Iy / (L ** 3 * (1 + phz))
    idx = [2, 4, 8, 10]
    m = b * np.array([[12, -6 * L, -12, -6 * L],
                      [-6 * L, (4 + phz) * L * L, 6 * L, (2 - phz) * L * L],
                      [-12, 6 * L, 12, 6 * L],
                      [-6 * L, (2 - phz) * L * L, 6 * L, (4 + phz) * L * L]])
    k[np.ix_(idx, idx)] = m
    return k


def local_geometric(P, A, Iy, Iz, L):
    """12x12 geometric stiffness for axial force P (tension positive). Moment-coupling terms neglected."""
    kg = np.zeros((12, 12))
    c = P / L
    m = c * np.array([[6 / 5, L / 10, -6 / 5, L / 10],
                      [L / 10, 2 * L * L / 15, -L / 10, -L * L / 30],
                      [-6 / 5, -L / 10, 6 / 5, -L / 10],
                      [L / 10, -L * L / 30, -L / 10, 2 * L * L / 15]])
    idx = [1, 5, 7, 11]
    kg[np.ix_(idx, idx)] = m
    m2 = m.copy()
    m2[0, 1] = m2[1, 0] = m2[0, 3] = m2[3, 0] = -L / 10 * c
    m2[1, 2] = m2[2, 1] = m2[2, 3] = m2[3, 2] = L / 10 * c
    idx = [2, 4, 8, 10]
    kg[np.ix_(idx, idx)] = m2
    t = P * (Iy + Iz) / (A * L)
    kg[3, 3] = kg[9, 9] = t
    kg[3, 9] = kg[9, 3] = -t
    return kg


def rotation(xi, xj, roll_deg=0.0, ref=None):
    """3x3 matrix whose rows are local x, y, z in global coordinates."""
    v = np.asarray(xj, float) - np.asarray(xi, float)
    L = float(np.linalg.norm(v))
    if L <= 1e-9:
        raise InputError("zero-length member")
    ex = v / L
    if ref is not None:
        r = np.asarray(ref, float)
        ey = r - r.dot(ex) * ex
        if np.linalg.norm(ey) < 1e-9:
            raise InputError("member 'ref' vector is parallel to the member")
    elif abs(ex[2]) >= math.cos(math.radians(1.0)):
        # within 1 deg of vertical: local y from global +X projected square to the member, so a small tilt does
        # not swing the axes (CPM-190 F-07). Members between 1 and 89 deg take y from global +Z.
        Xg = np.array([1.0, 0.0, 0.0])
        ey = Xg - Xg.dot(ex) * ex
    else:
        Zg = np.array([0.0, 0.0, 1.0])
        ey = Zg - Zg.dot(ex) * ex
    ey = ey / np.linalg.norm(ey)
    ez = np.cross(ex, ey)
    if roll_deg:
        c, s = math.cos(math.radians(roll_deg)), math.sin(math.radians(roll_deg))
        ey, ez = c * ey + s * ez, -s * ey + c * ez
    return np.vstack([ex, ey, ez]), L


def _T12(R):
    T = np.zeros((12, 12))
    for b in range(4):
        T[3 * b:3 * b + 3, 3 * b:3 * b + 3] = R
    return T


_REL = {"rx": 3, "ry": 4, "rz": 5}


def _condense_transform(k_el, k_other, released):
    """Carry another matrix (the geometric stiffness) through the ELASTIC condensation of released DOFs:
    u_r = -Krr^-1 Krk u_k, so k_other* = T^T k_other T (CPM-190 F-08; a matrix's own Schur complement fails
    when the released member carries no axial force)."""
    if not released:
        return k_other
    r = sorted(released)
    keep = [i for i in range(12) if i not in r]
    T = np.zeros((12, len(keep)))
    T[keep, range(len(keep))] = 1.0
    T[np.ix_(r, range(len(keep)))] = -np.linalg.solve(k_el[np.ix_(r, r)], k_el[np.ix_(r, keep)])
    out = np.zeros((12, 12))
    out[np.ix_(keep, keep)] = T.T @ k_other @ T
    return out


def _condense(k, f, released):
    """Static condensation of released local DOFs (indices into 12): returns k*, f* with zero rows there."""
    if not released:
        return k, f
    r = sorted(released)
    keep = [i for i in range(12) if i not in r]
    krr = k[np.ix_(r, r)]
    kkr = k[np.ix_(keep, r)]
    try:
        inv = np.linalg.inv(krr)
    except np.linalg.LinAlgError:
        raise InputError("member releases leave the member unstable (released at both ends about the same axis "
                         "with torsion also released?)")
    kc = np.zeros_like(k)
    kc[np.ix_(keep, keep)] = k[np.ix_(keep, keep)] - kkr @ inv @ kkr.T
    fc = np.zeros_like(f)
    fc[keep] = f[keep] - kkr @ inv @ f[r]
    return kc, fc


# =============================================================== model
@dataclass
class Element:
    member: str
    n1: int
    n2: int
    s0: float               # station of the element start along the member, in
    L: float
    R: np.ndarray
    sec: object
    mat: object
    released: list = field(default_factory=list)


@dataclass
class Member:
    id: str
    i: str
    j: str
    section: object
    material: object
    L: float
    R: np.ndarray
    elements: list = field(default_factory=list)
    node_ids: list = field(default_factory=list)   # internal node indices along the member
    stations: list = field(default_factory=list)   # distance from end i for each internal node
    meta: dict = field(default_factory=dict)


class FrameModel:
    """Build from a dict (see from_dict) or programmatically with add_node / add_member / support / load."""

    def __init__(self, divisions: int = 8, shear_deformation: bool = True):
        self.divisions = int(divisions)
        self.shear_deformation = bool(shear_deformation)
        self.node_xyz: list = []
        self.node_name: list = []
        self.node_index: dict = {}
        self.members: dict = {}
        self.supports: dict = {}          # node index -> {dof: spec}
        self.cases: dict = {}             # name -> case dict
        self.nodal_mass: dict = {}        # node index -> lb (weight) for modal analysis
        self._built = False

    # ---------------------------------------------------------- building
    def add_node(self, name, xyz):
        name = str(name)
        if name in self.node_index:
            raise InputError(f"duplicate node '{name}'")
        self.node_index[name] = len(self.node_xyz)
        self.node_xyz.append(np.asarray(xyz, float))
        self.node_name.append(name)
        return self.node_index[name]

    def _node(self, name):
        name = str(name)
        if name not in self.node_index:
            raise InputError(f"unknown node '{name}'")
        return self.node_index[name]

    def add_member(self, mid, i, j, section, material, releases=None, roll=0.0, ref=None, divisions=None, **meta):
        mid = str(mid)
        if mid in self.members:
            raise InputError(f"duplicate member '{mid}'")
        sec = secs.from_spec(section)
        mat = material if isinstance(material, mats.Material) else mats.get(material)
        ni, nj = self._node(i), self._node(j)
        R, L = rotation(self.node_xyz[ni], self.node_xyz[nj], roll, ref)
        rel = releases or {}
        for end in rel:
            if end not in ("i", "j"):
                raise InputError(f"member {mid} releases: ends are 'i' and 'j'")
            for d in rel[end]:
                if d not in _REL:
                    raise InputError(f"member {mid} release '{d}' must be one of rx, ry, rz")
        m = Member(mid, str(i), str(j), sec, mat, L, R, meta=dict(meta))
        m.meta["releases"] = rel
        m.meta["divisions"] = int(divisions) if divisions else self.divisions
        self.members[mid] = m
        self._built = False
        return m

    def support(self, node, **dofs):
        """support('N1', ux='fixed', uz='contact', ry=1e6). Unlisted DOFs are free."""
        n = self._node(node)
        d = self.supports.setdefault(n, {})
        for k, v in dofs.items():
            if k not in DOFS:
                raise InputError(f"support DOF '{k}' must be one of {DOFS}")
            if v == "contact" and k not in ("ux", "uy", "uz"):
                raise InputError("contact supports are for translations (ux, uy, uz)")
            d[k] = v

    def add_case(self, name, self_weight=0.0, nodal=None, member_udl=None, member_point=None, body=None):
        """A load case.

        self_weight: factor on member self weight acting in -Z (1.0 = gravity).
        body: [fx, fy, fz] multiples of weight applied as forces to member self weight AND to the nodal weights
              registered with add_mass (equipment). Gravity is [0, 0, -1]; a 0.5 g lateral transport load in +Y is
              [0, 0.5, 0]. Use it for transport, seismic and lifting-impact cases.
        nodal: {node: [Fx, Fy, Fz, Mx, My, Mz]}; member_udl: [{member, w: [wx, wy, wz] lb/in, local: false}];
        member_point: [{member, at (fraction of length, or inches with fraction: false), P: [..6], local: false}]."""
        self.cases[str(name)] = {"self_weight": float(self_weight), "nodal": nodal or {},
                                 "member_udl": member_udl or [], "member_point": member_point or [],
                                 "body": None if body is None else [float(v) for v in body]}
        self._built = False

    def add_mass(self, node, weight_lb):
        n = self._node(node)
        self.nodal_mass[n] = self.nodal_mass.get(n, 0.0) + float(weight_lb)

    # ---------------------------------------------------------- mesh
    def _mesh(self):
        if self._built:
            return
        self.xyz = [x.copy() for x in self.node_xyz]
        self.names = list(self.node_name)
        self.elements = []
        cuts = {mid: set() for mid in self.members}
        for case in self.cases.values():
            for pl in case["member_point"]:
                mid = str(pl["member"])
                if mid not in self.members:
                    raise InputError(f"point load on unknown member '{mid}'")
                at = float(pl["at"])
                L = self.members[mid].L
                s = at * L if pl.get("fraction", True) else at
                if not (0.0 <= s <= L):
                    raise InputError(f"point load on {mid} at {s} is off the member (0..{L:.3f})")
                cuts[mid].add(round(s, 9))
        for mid, m in self.members.items():
            n = m.meta["divisions"]
            st = {round(m.L * k / n, 9) for k in range(n + 1)} | cuts[mid]
            st = sorted(st)
            ni, nj = self._node(m.i), self._node(m.j)
            ids = [ni]
            p0 = self.node_xyz[ni]
            p1 = self.node_xyz[nj]
            for s in st[1:-1]:
                self.xyz.append(p0 + (p1 - p0) * (s / m.L))
                self.names.append(f"{mid}@{s:.3f}")
                ids.append(len(self.xyz) - 1)
            ids.append(nj)
            m.node_ids, m.stations, m.elements = ids, st, []
            rel = m.meta["releases"]
            for k in range(len(ids) - 1):
                released = []
                if k == 0:
                    released += [_REL[d] for d in rel.get("i", [])]
                if k == len(ids) - 2:
                    released += [6 + _REL[d] for d in rel.get("j", [])]
                el = Element(mid, ids[k], ids[k + 1], st[k], st[k + 1] - st[k], m.R, m.section, m.material, released)
                m.elements.append(el)
                self.elements.append(el)
        self.ndof = 6 * len(self.xyz)
        self._built = True

    # ---------------------------------------------------------- assembly
    def _k_el(self, el, P=0.0, geometric=False):
        s, mt = el.sec, el.mat
        Avy = s.Avy if self.shear_deformation else 0.0
        Avz = s.Avz if self.shear_deformation else 0.0
        k = local_geometric(P, s.A, s.Iy, s.Iz, el.L) if geometric else \
            local_stiffness(mt.E, mt.G, s.A, s.Iy, s.Iz, s.J, el.L, Avy, Avz)
        return k

    @staticmethod
    def _edofs(el):
        return [6 * el.n1 + d for d in range(6)] + [6 * el.n2 + d for d in range(6)]

    def _assemble(self, axial=None, geometric_only=False):
        rows, cols, vals = [], [], []
        for e_i, el in enumerate(self.elements):
            T = _T12(el.R)
            ke = self._k_el(el)
            if geometric_only:
                P = 0.0 if axial is None else axial[e_i]
                kl = _condense_transform(ke, self._k_el(el, P, geometric=True), el.released)
            else:
                kl, _ = _condense(ke, np.zeros(12), el.released)
                if axial is not None:
                    kl = kl + _condense_transform(ke, self._k_el(el, axial[e_i], geometric=True), el.released)
            kg = T.T @ kl @ T
            ed = self._edofs(el)
            for a in range(12):
                for b in range(12):
                    if kg[a, b] != 0.0:
                        rows.append(ed[a]); cols.append(ed[b]); vals.append(kg[a, b])
        return sp.csr_matrix((vals, (rows, cols)), shape=(self.ndof, self.ndof))

    def _loads(self, factors: dict):
        """Global load vector and per-element local uniform loads (wx, wy, wz) for a combination."""
        F = np.zeros(self.ndof)
        wloc = [np.zeros(3) for _ in self.elements]
        el_index = {}
        for e_i, el in enumerate(self.elements):
            el_index.setdefault(el.member, []).append(e_i)
        for cname, fac in factors.items():
            if cname not in self.cases:
                raise InputError(f"combination uses unknown load case '{cname}'")
            case = self.cases[cname]
            fac = float(fac)
            for node, vec in case["nodal"].items():
                v = list(vec) + [0.0] * (6 - len(vec))
                F[6 * self._node(node):6 * self._node(node) + 6] += fac * np.asarray(v[:6], float)
            sw = case["self_weight"]
            if sw:
                for e_i, el in enumerate(self.elements):
                    wg = np.array([0.0, 0.0, -el.sec.A * el.mat.density * sw * fac])
                    wloc[e_i] += el.R @ wg
            body = case.get("body")
            if body:
                bv = np.asarray(body, float) * fac
                for e_i, el in enumerate(self.elements):
                    wloc[e_i] += el.R @ (el.sec.A * el.mat.density * bv)
                for n, wlb in self.nodal_mass.items():
                    F[6 * n:6 * n + 3] += wlb * bv
            for u in case["member_udl"]:
                mid = str(u["member"])
                if mid not in el_index:
                    raise InputError(f"distributed load on unknown member '{mid}'")
                w = np.asarray(u["w"], float) * fac
                if u.get("local", False):
                    for e_i in el_index[mid]:
                        wloc[e_i] += w
                else:
                    for e_i in el_index[mid]:
                        wloc[e_i] += self.elements[e_i].R @ w
            for pl in case["member_point"]:
                mid = str(pl["member"])
                m = self.members[mid]
                s = float(pl["at"]) * m.L if pl.get("fraction", True) else float(pl["at"])
                k = min(range(len(m.stations)), key=lambda q: abs(m.stations[q] - s))
                n = m.node_ids[k]
                P = np.asarray(list(pl["P"]) + [0.0] * (6 - len(pl["P"])), float) * fac
                if pl.get("local", False):
                    P[:3] = m.R.T @ P[:3]
                    P[3:] = m.R.T @ P[3:]
                F[6 * n:6 * n + 6] += P
        # equivalent nodal loads of the uniform loads
        self._feq = []
        for e_i, el in enumerate(self.elements):
            wx, wy, wz = wloc[e_i]
            L = el.L
            f = np.array([wx * L / 2, wy * L / 2, wz * L / 2, 0, -wz * L * L / 12, wy * L * L / 12,
                          wx * L / 2, wy * L / 2, wz * L / 2, 0, wz * L * L / 12, -wy * L * L / 12])
            kl = self._k_el(el)
            _, fc = _condense(kl, f, el.released)
            self._feq.append(fc)
            F[self._edofs(el)] += _T12(el.R).T @ fc
        return F, wloc

    # ---------------------------------------------------------- solve
    def _support_state(self):
        fixed, springs, contacts = {}, {}, []
        for n, d in self.supports.items():
            for dof, spec in d.items():
                g = 6 * n + DOFS.index(dof)
                if spec == "fixed":
                    fixed[g] = 0.0
                elif spec == "contact":
                    contacts.append(g)
                elif spec in ("free", None):
                    pass
                else:
                    try:
                        springs[g] = float(spec)
                    except (TypeError, ValueError):
                        raise InputError(f"support spec {spec!r} must be fixed, free, contact or a stiffness")
        return fixed, springs, contacts

    def solve(self, factors: dict, pdelta: bool = False, max_iter: int | None = None, gap=None):
        """Solve one load combination {case: factor}. Returns a Result."""
        self._mesh()
        F, wloc = self._loads(factors)
        fixed, springs, contacts = self._support_state()
        if max_iter is None:
            max_iter = 60 + 3 * len(contacts)      # one contact released per iteration (CPM-190 N-1)
        gap = gap or {}
        active = set(contacts)
        axial = None
        K0 = self._assemble()
        history = []
        for it in range(max_iter):
            K = K0 if axial is None else self._assemble(axial)
            if springs:
                K = K + sp.csr_matrix((list(springs.values()), (list(springs), list(springs))), shape=K.shape)
            presc = dict(fixed)
            for g in active:
                presc[g] = float(gap.get(g, 0.0))
            fdofs = np.array([g for g in range(self.ndof) if g not in presc])
            pdofs = np.array(sorted(presc))
            u = np.zeros(self.ndof)
            if len(pdofs):
                u[pdofs] = [presc[g] for g in pdofs]
            Kff = K[fdofs][:, fdofs].tocsc()
            rhs = F[fdofs] - (K[fdofs][:, pdofs] @ u[pdofs] if len(pdofs) else 0.0)
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    uf = spla.spsolve(Kff, rhs)
            except Exception as exc:  # singular
                raise InputError(f"structure is unstable (mechanism) for this support state: {exc}. "
                                 "Restrain every rigid-body motion: each horizontal direction and rotation "
                                 "needs at least one support.")
            if not np.all(np.isfinite(uf)) or np.linalg.norm(Kff @ uf - rhs) > 1e-6 * (np.linalg.norm(rhs) + 1.0):
                raise InputError("structure is unstable (mechanism): the solve did not converge. Restrain every "
                                 "rigid-body motion; check releases and contact supports.")
            u[fdofs] = uf
            Rfull = K @ u - F
            changed = False
            # contact update: release the most tensile contact; restore penetrating released ones
            tens = [(Rfull[g], g) for g in active if Rfull[g] < -1e-6 * (1 + np.abs(F).max())]
            pen = [g for g in contacts if g not in active and u[g] < float(gap.get(g, 0.0)) - 1e-9]
            if tens:
                active.discard(min(tens)[1])
                changed = True
            elif pen:
                active.update(pen)
                changed = True
            new_axial = None
            if pdelta:
                new_axial = self._axial_forces(u, wloc)
                if axial is None or np.max(np.abs(new_axial - axial)) > 1e-4 * (np.max(np.abs(new_axial)) + 1):
                    changed = True
                axial = new_axial
            history.append(len(active))
            if not changed:
                res = Result(self, factors, u, Rfull, wloc, active, contacts, pdelta, it + 1)
                res.axial = axial
                return res
        raise InputError(f"no converged contact / P-Delta state after {max_iter} iterations ({history[-5:]})")

    def _axial_forces(self, u, wloc):
        out = np.zeros(len(self.elements))
        for e_i, el in enumerate(self.elements):
            ul = _T12(el.R) @ u[self._edofs(el)]
            kl, _ = _condense(self._k_el(el), np.zeros(12), el.released)
            f = kl @ ul - self._feq[e_i]
            out[e_i] = 0.5 * (f[6] - f[0])     # mean element axial force, tension positive
        return out

    # ---------------------------------------------------------- eigen
    def buckling(self, factors: dict, n_modes: int = 3):
        """Elastic buckling load factors (multipliers on the combination) from the linear axial forces."""
        res = self.solve(factors)
        axial = self._axial_forces(res.u, res.wloc)
        if axial.min() >= -1e-6 * (1.0 + np.abs(axial).max()):
            return []                      # nothing in compression: no buckling load
        K = self._assemble()
        Kg = self._assemble(axial, geometric_only=True)
        fixed, springs, contacts = self._support_state()
        presc = set(fixed) | set(g for g in contacts if g in res.active)
        if springs:
            K = K + sp.csr_matrix((list(springs.values()), (list(springs), list(springs))), shape=K.shape)
        f = np.array([g for g in range(self.ndof) if g not in presc])
        Kff, Kgff = K[f][:, f].tocsc(), Kg[f][:, f].tocsc()
        lu = spla.splu(Kff)
        op = spla.LinearOperator(Kff.shape, matvec=lambda x: lu.solve(-(Kgff @ x)))
        k = min(n_modes + 4, len(f) - 2)
        v0 = np.random.default_rng(0).standard_normal(len(f))
        vals = spla.eigs(op, k=k, which="LR", return_eigenvectors=False, v0=v0, maxiter=20 * len(f))
        mus = sorted([v.real for v in vals if v.real > 1e-12 and abs(v.imag) < 1e-6 * abs(v.real) + 1e-12], reverse=True)
        return [1.0 / m for m in mus[:n_modes]]

    def modal(self, n_modes: int = 5, include_self_weight: bool = True, extra_cases: dict | None = None):
        """Natural frequencies (Hz) with lumped translational mass; rotations carry a tiny mass to stay definite.

        extra_cases: {case: factor} whose nodal Z loads (downward) are added as mass (weights of equipment)."""
        self._mesh()
        mass = np.zeros(self.ndof)
        g = 386.0886
        if include_self_weight:
            for el in self.elements:
                w = el.sec.A * el.mat.density * el.L
                for n in (el.n1, el.n2):
                    mass[6 * n:6 * n + 3] += w / 2 / g
        for n, wlb in self.nodal_mass.items():
            mass[6 * n:6 * n + 3] += wlb / g
        if extra_cases:
            for cname, fac in extra_cases.items():
                for node, vec in self.cases[cname]["nodal"].items():
                    n = self._node(node)
                    mass[6 * n:6 * n + 3] += abs(float(vec[2]) * float(fac)) / g
        tmin = mass.reshape(-1, 6)[:, :3].max() if mass.any() else 1.0
        for n in range(len(self.xyz)):
            mass[6 * n + 3:6 * n + 6] = max(1e-9, 1e-6 * tmin)
        K = self._assemble()
        fixed, springs, contacts = self._support_state()
        if springs:
            K = K + sp.csr_matrix((list(springs.values()), (list(springs), list(springs))), shape=K.shape)
        presc = set(fixed) | set(contacts)
        f = np.array([q for q in range(self.ndof) if q not in presc])
        Kff = K[f][:, f].tocsc()
        Mff = sp.diags(mass[f]).tocsc()
        k = min(n_modes, len(f) - 2)
        w2, vec = spla.eigsh(Kff, k=k, M=Mff, sigma=0.0, which="LM")
        order = np.argsort(w2)
        freqs = [math.sqrt(max(v, 0.0)) / (2 * math.pi) for v in w2[order]]
        return freqs


# =============================================================== results
class Result:
    def __init__(self, model, factors, u, R, wloc, active, contacts, pdelta, iterations):
        self.model, self.factors, self.u, self.R, self.wloc = model, factors, u, R, wloc
        self.active, self.contacts, self.pdelta, self.iterations = active, contacts, pdelta, iterations

    def _idx(self, node):
        """User node name, or an internal station node name like 'B1@36.000' (model.names)."""
        name = str(node)
        if name in self.model.node_index:
            return self.model.node_index[name]
        try:
            return self.model.names.index(name)
        except ValueError:
            raise InputError(f"unknown node '{name}'")

    def disp(self, node):
        n = self._idx(node)
        return self.u[6 * n:6 * n + 6].copy()

    def reaction(self, node):
        n = self._idx(node)
        r = self.R[6 * n:6 * n + 6].copy()
        sup = self.model.supports.get(n, {})
        for k, dof in enumerate(DOFS):
            spec = sup.get(dof)
            g = 6 * n + k
            if spec is None or spec == "free" or (spec == "contact" and g not in self.active):
                r[k] = 0.0
            elif spec not in ("fixed", "contact"):
                r[k] = -float(spec) * self.u[g]       # spring: force on the structure (CPM-190 F-02)
        return r

    def reactions(self):
        return {self.model.names[n]: self.reaction(self.model.names[n]) for n in self.model.supports}

    def lifted(self):
        """Contact DOFs that are not bearing (node name, dof)."""
        out = []
        for g in self.contacts:
            if g not in self.active:
                out.append((self.model.names[g // 6], DOFS[g % 6]))
        return out

    def member_forces(self, mid, points_per_element: int = 4):
        """Internal forces along a member: list of dicts (s, N, Vy, Vz, T, My, Mz). N > 0 is tension."""
        m = self.model.members[str(mid)]
        out = []
        model = self.model
        e_index = {id(el): k for k, el in enumerate(model.elements)}
        for el in m.elements:
            e_i = e_index[id(el)]
            ul = _T12(el.R) @ self.u[model._edofs(el)]
            kl = model._k_el(el)
            kc, _ = _condense(kl, np.zeros(12), el.released)
            if self.pdelta and getattr(self, "axial", None) is not None:   # second-order end forces, same
                kc = kc + _condense_transform(kl, model._k_el(el, self.axial[e_i], geometric=True), el.released)
            f = kc @ ul - model._feq[e_i]
            wx, wy, wz = self.wloc[e_i]
            ss = [el.L * q / points_per_element for q in range(points_per_element + 1)]
            # stationary points of the moment parabolas (zero shear)
            for wv, fv in ((wy, f[1]), (wz, f[2])):
                if abs(wv) > 1e-12:
                    s0 = -fv / wv
                    if 0 < s0 < el.L:
                        ss.append(s0)
            for s in sorted(set(ss)):
                N = -(f[0] + wx * s)
                Vy = -(f[1] + wy * s)
                Vz = -(f[2] + wz * s)
                T = -f[3]
                Mz = -f[5] + s * f[1] + wy * s * s / 2
                My = -(f[4] + s * f[2] + wz * s * s / 2)
                out.append({"s": el.s0 + s, "N": N, "Vy": Vy, "Vz": Vz, "T": T, "My": My, "Mz": Mz})
        return out

    def member_envelope(self, mid):
        fr = self.member_forces(mid)
        env = {}
        for key in ("N", "Vy", "Vz", "T", "My", "Mz"):
            row = max(fr, key=lambda d: abs(d[key]))
            env[key] = (row[key], row["s"])
        env["N_min"] = min((d["N"], d["s"]) for d in fr)
        env["N_max"] = max((d["N"], d["s"]) for d in fr)
        return env, fr

    def member_deflection(self, mid):
        """Deflection relative to the chord between the member end nodes (local y, z) and absolute max, in."""
        m = self.model.members[str(mid)]
        R = m.R
        ui = self.u[6 * m.node_ids[0]:6 * m.node_ids[0] + 3]
        uj = self.u[6 * m.node_ids[-1]:6 * m.node_ids[-1] + 3]
        rel_y = rel_z = absmax = 0.0
        for n, s in zip(m.node_ids, m.stations):
            un = self.u[6 * n:6 * n + 3]
            chord = ui + (uj - ui) * (s / m.L)
            d = R @ (un - chord)
            if abs(d[1]) > abs(rel_y):
                rel_y = d[1]
            if abs(d[2]) > abs(rel_z):
                rel_z = d[2]
            absmax = max(absmax, float(np.linalg.norm(un)))
        # cantilever measure: each end's deflection from the tangent line at the other end
        xi = np.asarray(self.model.xyz[m.node_ids[0]])
        xj = np.asarray(self.model.xyz[m.node_ids[-1]])
        ri = self.u[6 * m.node_ids[0] + 3:6 * m.node_ids[0] + 6]
        rj = self.u[6 * m.node_ids[-1] + 3:6 * m.node_ids[-1] + 6]
        tip_j = R @ (uj - ui - np.cross(ri, xj - xi))
        tip_i = R @ (ui - uj - np.cross(rj, xi - xj))
        cant = max(float(np.hypot(tip_j[1], tip_j[2])), float(np.hypot(tip_i[1], tip_i[2])))
        return {"rel_y": rel_y, "rel_z": rel_z, "abs_max": absmax, "cantilever": cant}


# =============================================================== dict front end
def from_dict(d: dict) -> FrameModel:
    """Build a FrameModel from a JSON/YAML-style dict.

    {
      "options": {"divisions": 8, "shear_deformation": true},
      "sections": {"R3": {"shape": "round", "D": 3.0, "t": 0.12}},
      "nodes": {"N1": [0, 0, 0], "N2": [120, 0, 0]},
      "members": [{"id": "B1", "i": "N1", "j": "N2", "section": "R3", "material": "A554-304",
                   "releases": {"i": ["ry", "rz"]}, "roll": 0, "divisions": 8}],
      "supports": {"N1": {"ux": "fixed", "uy": "fixed", "uz": "contact", "rx": "fixed"}},
      "cases": {"D": {"self_weight": 1.0, "nodal": {"N2": [0, 0, -500]},
                      "member_udl": [{"member": "B1", "w": [0, 0, -2.0]}],
                      "member_point": [{"member": "B1", "at": 0.5, "P": [0, 0, -300]}]}},
      "masses": {"N2": 500}
    }
    """
    opt = d.get("options", {})
    m = FrameModel(opt.get("divisions", 8), opt.get("shear_deformation", True))
    sections = d.get("sections", {})
    for name, xyz in d.get("nodes", {}).items():
        if len(xyz) != 3:
            raise InputError(f"node {name} needs [x, y, z]")
        m.add_node(name, xyz)
    for mem in d.get("members", []):
        sec = mem["section"]
        if isinstance(sec, str):
            if sec not in sections:
                raise InputError(f"member {mem.get('id')} uses unknown section '{sec}'")
            sec = sections[sec]
        extra = {k: v for k, v in mem.items() if k not in ("id", "i", "j", "section", "material", "releases", "roll",
                                                             "ref", "divisions", "temperature_F")}
        known = {"kind"}
        unknown = [k for k in extra if k not in known]
        if unknown:
            raise InputError(f"member {mem.get('id')}: unknown keys {unknown} (design values go in the 'design' block)")
        # service temperature: per member, else the model's top-level temperature_F (CPM-190 F-06)
        temp = mem.get("temperature_F", d.get("temperature_F"))
        mat = mats.get(mem["material"], temp) if temp is not None else mem["material"]
        m.add_member(mem["id"], mem["i"], mem["j"], sec, mat, mem.get("releases"), mem.get("roll", 0.0),
                     mem.get("ref"), mem.get("divisions"), **extra)
    for node, dofs in d.get("supports", {}).items():
        m.support(node, **dofs)
    for node, w in d.get("masses", {}).items():
        m.add_mass(node, w)
    for name, c in d.get("cases", {}).items():
        m.add_case(name, c.get("self_weight", 0.0), c.get("nodal"), c.get("member_udl"), c.get("member_point"),
                   c.get("body"))
    return m
