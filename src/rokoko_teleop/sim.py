"""MuJoCo scene: a floating Shadow Dexterous Hand (MuJoCo Menagerie), a
table and a fragile egg.

The hand hangs from a freejoint welded to a mocap target, so the operator's
wrist pose moves it compliantly (contacts push back instead of teleporting
through the table). Gravity compensation keeps it from sagging. The egg
"cracks" when the hand squeezes it harder than `crack_force_n`, which turns
grip force into something the operator, the judges and the dataset all see.
"""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import mujoco
import numpy as np

from . import quat as Q
from .retarget.shadow import ACTUATORS

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MENAGERIE = PACKAGE_ROOT / "third_party" / "mujoco_menagerie"

EGG_RGBA = np.array([0.96, 0.93, 0.85, 1.0])
CRACKED_RGBA = np.array([0.85, 0.15, 0.1, 1.0])
HOT_RGBA = np.array([1.0, 0.65, 0.1, 1.0])


def menagerie_dir() -> Path:
    return Path(os.environ.get("MENAGERIE_DIR", DEFAULT_MENAGERIE))


@dataclass
class SceneConfig:
    egg_pos: tuple[float, float, float] = (0.0, 0.0, 0.0)  # on the table top (z = table top)
    egg_radii: tuple[float, float] = (0.024, 0.031)  # equatorial, polar (metres)
    egg_mass: float = 0.06
    crack_force_n: float = 8.0  # summed hand-on-egg normal force (a sim proxy; see README)
    table_top_z: float = 0.0
    timestep: float = 0.002
    width: int = 640
    height: int = 480
    look: str = "default"  # "studio": dark backdrop; "light": light-grey seamless product-shot look (for video)


@dataclass
class EggState:
    pos: np.ndarray
    quat_xyzw: np.ndarray
    force_n: float  # summed normal force from the hand this step
    peak_force_n: float
    cracked: bool
    lifted_m: float  # height above its resting height
    hand_contacts: int


@dataclass
class TeleopSim:
    config: SceneConfig = field(default_factory=SceneConfig)
    hand_xml: Path | None = None

    def __post_init__(self) -> None:
        self.model, self._ids = build_model(self.config, self.hand_xml)
        self.data = mujoco.MjData(self.model)
        self._renderer: mujoco.Renderer | None = None
        self.camera = mujoco.MjvCamera()
        self.camera.type = mujoco.mjtCamera.mjCAMERA_FREE
        self.camera.lookat[:] = [0.0, 0.0, 0.07]
        self.camera.distance = 0.55
        self.camera.azimuth = 125
        self.camera.elevation = -18
        self._calibrate_palm()
        self.reset()

    # --- setup ---------------------------------------------------------------

    def _calibrate_palm(self) -> None:
        """Palm pose in the hand-root frame, and the fixed rotation from an
        OpenXR wrist frame to the Shadow palm frame, both read off the model
        so no axis convention is hand-typed."""
        m, d = self.model, mujoco.MjData(self.model)
        root_q = self._ids["root_qpos"]
        d.qpos[root_q : root_q + 3] = 0.0
        d.qpos[root_q + 3 : root_q + 7] = [1, 0, 0, 0]
        mujoco.mj_forward(m, d)
        palm = self._ids["palm"]
        R_palm = d.xmat[palm].reshape(3, 3)
        p_palm = d.xpos[palm].copy()
        self.palm_in_root_pos = p_palm  # root at identity
        self.palm_in_root_rot = R_palm.copy()

        def body_pos(name: str) -> np.ndarray:
            return d.xpos[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, name)]

        fwd = body_pos("rh_mfdistal") - p_palm
        side = body_pos("rh_thproximal") - p_palm  # towards the thumb
        # Snap to the palm's principal axes: the thumb base sits a little
        # towards the palm, which would otherwise roll the hand ~15 degrees.
        f = _snap_axis(R_palm.T @ fwd)
        s = R_palm.T @ side
        s = _snap_axis(s - f * (s @ f))
        u = np.cross(f, s)  # dorsal for a right hand: forward x thumb-side
        # Columns: OpenXR wrist axes (X = away from thumb, Y = dorsal, Z = back)
        # expressed in the palm frame.
        self.xr_in_palm = np.stack([-s, u, -f], axis=1)
        self.palm_length = float(np.linalg.norm(fwd))

    def reset(self) -> None:
        mujoco.mj_resetData(self.model, self.data)
        self.peak_force = 0.0
        self.cracked = False
        self._egg_rest_z = None
        self.model.geom_rgba[self._ids["egg_geom"]] = EGG_RGBA
        self.set_wrist(np.array([-0.12, 0.0, 0.25]), _palm_down_xr())
        self._snap_root_to_target()
        mujoco.mj_forward(self.model, self.data)
        self._egg_rest_z = float(self.data.xpos[self._ids["egg"]][2])

    def _snap_root_to_target(self) -> None:
        q = self._ids["root_qpos"]
        mid = self._ids["mocap"]
        self.data.qpos[q : q + 3] = self.data.mocap_pos[mid]
        self.data.qpos[q + 3 : q + 7] = self.data.mocap_quat[mid]

    # --- control -------------------------------------------------------------

    def set_wrist(self, pos, xr_quat_xyzw) -> None:
        """Place the hand so its palm frame matches an OpenXR wrist pose (Z-up)."""
        R_xr = Q.to_matrix(xr_quat_xyzw)
        R_palm = R_xr @ self.xr_in_palm.T
        R_root = R_palm @ self.palm_in_root_rot.T
        p_root = np.asarray(pos, dtype=float) - R_root @ self.palm_in_root_pos
        mid = self._ids["mocap"]
        self.data.mocap_pos[mid] = p_root
        self.data.mocap_quat[mid] = Q.to_wxyz(Q.from_matrix(R_root))

    def set_ctrl(self, ctrl: np.ndarray) -> None:
        lo = self.model.actuator_ctrlrange[:, 0]
        hi = self.model.actuator_ctrlrange[:, 1]
        self.data.ctrl[self._ids["act"]] = np.clip(ctrl, lo[self._ids["act"]], hi[self._ids["act"]])

    def step(self, dt: float) -> EggState:
        n = max(1, int(round(dt / self.model.opt.timestep)))
        peak = 0.0
        for _ in range(n):
            mujoco.mj_step(self.model, self.data)
            peak = max(peak, self._egg_hand_force()[0])
        return self._update_egg(peak)

    def _egg_hand_force(self) -> tuple[float, int]:
        m, d = self.model, self.data
        egg_g = self._ids["egg_geom"]
        hand_bodies = self._ids["hand_bodies"]
        total, count = 0.0, 0
        f6 = np.zeros(6)
        for i in range(d.ncon):
            c = d.contact[i]
            if c.geom1 == egg_g:
                other = c.geom2
            elif c.geom2 == egg_g:
                other = c.geom1
            else:
                continue
            if m.geom_bodyid[other] not in hand_bodies:
                continue
            mujoco.mj_contactForce(m, d, i, f6)
            total += abs(f6[0])
            count += 1
        return total, count

    def _update_egg(self, step_peak: float) -> EggState:
        d = self.data
        egg = self._ids["egg"]
        force, contacts = self._egg_hand_force()
        self.peak_force = max(self.peak_force, step_peak)
        if step_peak > self.config.crack_force_n:
            self.cracked = True
        g = self._ids["egg_geom"]
        if self.cracked:
            self.model.geom_rgba[g] = CRACKED_RGBA
        else:
            t = min(1.0, step_peak / self.config.crack_force_n)
            self.model.geom_rgba[g] = (1 - t) * EGG_RGBA + t * HOT_RGBA
        rest = self._egg_rest_z if self._egg_rest_z is not None else d.xpos[egg][2]
        return EggState(
            pos=d.xpos[egg].copy(),
            quat_xyzw=Q.from_wxyz(d.xquat[egg]),
            force_n=max(force, step_peak),
            peak_force_n=self.peak_force,
            cracked=self.cracked,
            lifted_m=float(d.xpos[egg][2] - rest),
            hand_contacts=contacts,
        )

    # --- observation -----------------------------------------------------------

    def hand_qpos(self) -> np.ndarray:
        return self.data.qpos[self._ids["hand_qpos"]].copy()

    def root_pose(self) -> np.ndarray:
        q = self._ids["root_qpos"]
        return self.data.qpos[q : q + 7].copy()

    def ctrl(self) -> np.ndarray:
        return self.data.ctrl[self._ids["act"]].copy()

    def render(self) -> np.ndarray:
        if self._renderer is None:
            self._renderer = mujoco.Renderer(self.model, self.config.height, self.config.width)
        self._renderer.update_scene(self.data, self.camera)
        return self._renderer.render()

    def close(self) -> None:
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None


def _snap_axis(v) -> np.ndarray:
    """The signed principal axis closest to v."""
    out = np.zeros(3)
    i = int(np.argmax(np.abs(v)))
    out[i] = np.sign(v[i])
    return out


def _palm_down_xr() -> np.ndarray:
    """OpenXR wrist orientation (Z-up world) for a palm-down hand whose
    fingers point along +X: local -Z -> +X, local +Y -> +Z."""
    R = np.array([[0.0, 0.0, -1.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    return Q.from_matrix(R)


def palm_down_xr() -> np.ndarray:
    return _palm_down_xr()


def build_model(cfg: SceneConfig, hand_xml: Path | None = None) -> tuple[mujoco.MjModel, dict]:
    hand_xml = hand_xml or (menagerie_dir() / "shadow_hand" / "right_hand.xml")
    if not hand_xml.exists():
        raise FileNotFoundError(f"{hand_xml} missing: run scripts/fetch_menagerie.sh")

    ex, ez = cfg.egg_radii
    top = cfg.table_top_z
    ox, oy, _ = cfg.egg_pos
    egg_rgba = " ".join(f"{x:g}" for x in EGG_RGBA)
    if cfg.look == "light":
        visual = f"""
  <visual>
    <global offwidth="{max(3840, cfg.width)}" offheight="{max(2160, cfg.height)}" fovy="30"/>
    <quality shadowsize="16384" offsamples="8"/>
    <headlight ambient="0.32 0.32 0.32" diffuse="0.18 0.18 0.18" specular="0.03 0.03 0.03"/>
    <rgba haze="0.86 0.86 0.86 1"/>
    <map znear="0.01" haze="1.2" fogstart="1.2" fogend="3.5"/>
  </visual>
  <asset>
    <texture name="sky" type="skybox" builtin="flat" rgb1="0.86 0.86 0.86" rgb2="0.86 0.86 0.86" width="64" height="384"/>
    <material name="grid" rgba="0.86 0.86 0.86 1" reflectance="0"/>
    <material name="wood" rgba="0.8 0.8 0.8 1" reflectance="0" specular="0.05" shininess="0.1"/>
  </asset>"""
        lights = """
    <light name="key" pos="0.3 -0.5 1.4" dir="-0.2 0.35 -1" directional="true" diffuse="0.4 0.4 0.4" specular="0.2 0.2 0.2" castshadow="true"/>
    <light name="fill" pos="-0.8 -0.4 0.8" dir="0.8 0.4 -0.6" diffuse="0.14 0.14 0.14" specular="0 0 0" castshadow="false"/>
    <light name="rim" pos="-0.4 0.8 0.7" dir="0.4 -0.8 -0.6" diffuse="0.3 0.3 0.3" specular="0.35 0.35 0.35" castshadow="false"/>"""
    elif cfg.look == "studio":
        visual = f"""
  <visual>
    <global offwidth="{max(1920, cfg.width)}" offheight="{max(1080, cfg.height)}" fovy="30"/>
    <quality shadowsize="8192" offsamples="8"/>
    <headlight ambient="0.18 0.18 0.2" diffuse="0.25 0.25 0.27" specular="0.05 0.05 0.05"/>
    <rgba haze="0.055 0.065 0.085 1"/>
    <map znear="0.01" haze="0.6"/>
  </visual>
  <asset>
    <texture name="sky" type="skybox" builtin="gradient" rgb1="0.09 0.1 0.13" rgb2="0.03 0.035 0.05" width="512" height="3072"/>
    <material name="grid" rgba="0.06 0.07 0.09 1" reflectance="0.0"/>
    <material name="wood" rgba="0.2 0.21 0.24 1" reflectance="0" specular="0.2" shininess="0.3"/>
  </asset>"""
        lights = """
    <light name="key" pos="0.6 -0.7 1.1" dir="-0.5 0.6 -1" diffuse="0.85 0.82 0.78" specular="0.3 0.3 0.3" castshadow="true" cutoff="40" exponent="4"/>
    <light name="fill" pos="-0.8 -0.3 0.6" dir="0.8 0.3 -0.5" diffuse="0.35 0.38 0.45" specular="0 0 0" castshadow="false"/>
    <light name="rim" pos="-0.4 0.8 0.7" dir="0.4 -0.8 -0.6" diffuse="0.6 0.65 0.75" specular="0.4 0.4 0.4" castshadow="false"/>"""
    else:
        visual = f"""
  <visual>
    <global offwidth="{max(1280, cfg.width)}" offheight="{max(960, cfg.height)}"/>
    <quality shadowsize="4096"/>
    <rgba haze="0.15 0.25 0.35 1"/>
  </visual>
  <asset>
    <texture name="sky" type="skybox" builtin="gradient" rgb1="0.3 0.5 0.7" rgb2="0 0 0" width="512" height="3072"/>
    <texture name="grid" type="2d" builtin="checker" mark="edge" rgb1="0.2 0.3 0.4" rgb2="0.1 0.2 0.3"
      markrgb="0.8 0.8 0.8" width="300" height="300"/>
    <material name="grid" texture="grid" texuniform="true" texrepeat="5 5" reflectance="0.2"/>
    <material name="wood" rgba="0.55 0.38 0.24 1"/>
  </asset>"""
        lights = """
    <light pos="0 0 1.5" dir="0 0 -1" directional="true"/>
    <light pos="0.5 -0.5 1.0" dir="-0.5 0.5 -1"/>"""
    # The collision table is the same in every look, so a render gives exactly the
    # physics of the evaluation (a bigger collision box flipped a sensitive grasp).
    # "light" draws a large visual-only table over it and hides the collision box.
    table_half = 3.0 if cfg.look == "studio" else 0.4
    floor_z = top - 0.75
    floor_col = ""
    table_vis = ' rgba="0 0 0 0"' if cfg.look == "light" else ' material="wood"'
    extra = (f'<geom name="table_visual" type="box" size="3 3 0.02" pos="0 0 {top - 0.02}" material="wood" '
             f'contype="0" conaffinity="0" group="1"/>') if cfg.look == "light" else ""
    xml = f"""
<mujoco model="rokoko_teleop_egg">
  <option timestep="{cfg.timestep}" cone="elliptic" impratio="10"/>
  <statistic extent="0.5"/>{visual}
  <worldbody>{lights}
    <geom name="floor" type="plane" size="0 0 0.05" pos="0 0 {floor_z}" material="grid"{floor_col}/>
    <geom name="table" type="box" size="{table_half} {table_half} 0.02" pos="0 0 {top - 0.02}"{table_vis} friction="1 0.01 0.001"/>
    {extra}
    <body name="egg" pos="{ox} {oy} {top + ez + 0.001}">
      <freejoint name="egg_free"/>
      <geom name="egg_geom" type="ellipsoid" size="{ex} {ex} {ez}" mass="{cfg.egg_mass}" rgba="{egg_rgba}"
        condim="6" priority="1" friction="1.2 0.02 0.002" solref="0.004 1"/>
    </body>
    <body name="hand_target" mocap="true" pos="-0.12 0 0.3"/>
    <body name="hand_root" pos="-0.12 0 0.3">
      <freejoint name="hand_free"/>
      <frame name="hand_mount"/>
    </body>
  </worldbody>
  <equality>
    <weld name="hand_weld" body1="hand_target" body2="hand_root" relpose="0 0 0 1 0 0 0" solref="0.01 1"/>
  </equality>
</mujoco>
"""
    spec = mujoco.MjSpec.from_string(xml)
    hand = mujoco.MjSpec.from_file(str(hand_xml))
    frame = spec.frame("hand_mount") if hasattr(spec, "frame") else None
    if frame is None:
        frame = spec.body("hand_root").add_frame()
    spec.attach(hand, prefix="", frame=frame)

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Attaching a spec with an empty prefix")
        model = spec.compile()

    if cfg.look == "light":
        # Product-shot materials: graphite with soft highlights (not a flat
        # black silhouette) and a satin light-grey forearm shell.
        for name, rgba, spec, shin in (("black", (0.2, 0.205, 0.215, 1), 0.65, 0.55),
                                       ("gray", (0.93, 0.93, 0.92, 1), 0.35, 0.4),
                                       ("metallic", (0.78, 0.79, 0.8, 1), 0.9, 0.85)):
            mid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_MATERIAL, name)
            if mid >= 0:
                model.mat_rgba[mid] = rgba
                model.mat_specular[mid] = spec
                model.mat_shininess[mid] = shin

    def bid(name: str) -> int:
        return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)

    root_id = bid("hand_root")
    hand_bodies = {b for b in range(model.nbody) if model.body_rootid[b] == root_id}
    for b in hand_bodies:
        model.body_gravcomp[b] = 1.0
    # The forearm is a mounting stub, not a manipulator: let it pass through
    # the table so the operator can reach low without it propping the hand up.
    stub = {bid("rh_forearm"), bid("rh_wrist")}
    for g in range(model.ngeom):
        if model.geom_bodyid[g] in stub:
            model.geom_contype[g] = 0
            model.geom_conaffinity[g] = 0
    if cfg.look == "light":  # satin light-grey forearm shell, graphite hand
        fa = bid("rh_forearm")
        for g in range(model.ngeom):
            if model.geom_bodyid[g] == fa and model.geom_group[g] != 3:
                model.geom_matid[g] = -1
                model.geom_rgba[g] = (0.86, 0.86, 0.85, 1)
    hand_joint_ids = [
        j for j in range(model.njnt)
        if model.jnt_bodyid[j] in hand_bodies and model.jnt_type[j] == mujoco.mjtJoint.mjJNT_HINGE
    ]
    act_ids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, n) for n in ACTUATORS]
    if min(act_ids) < 0:
        missing = [n for n, i in zip(ACTUATORS, act_ids) if i < 0]
        raise ValueError(f"hand model lacks actuators {missing}")
    free_j = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "hand_free")
    ids = {
        "egg": bid("egg"),
        "egg_geom": mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "egg_geom"),
        "palm": bid("rh_palm"),
        "root": root_id,
        "root_qpos": int(model.jnt_qposadr[free_j]),
        "mocap": int(model.body_mocapid[bid("hand_target")]),
        "hand_bodies": hand_bodies,
        "hand_qpos": np.array([model.jnt_qposadr[j] for j in hand_joint_ids]),
        "hand_joint_names": [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, j) for j in hand_joint_ids],
        "act": np.array(act_ids),
    }
    return model, ids
