"""Ventana 3D con el modelo OFICIAL del robot.

No corre fisica: escribe la pose y llama mj_forward. Ver robots.py para el
porque.
"""

from __future__ import annotations

import math
import time

from .robots import Robot as RobotSim


def mujoco_disponible() -> tuple[bool, str]:
    try:
        import mujoco  # noqa: F401
        import mujoco.viewer  # noqa: F401
        return True, ""
    except Exception as exc:
        return False, str(exc)


class Visor:
    def __init__(self, mundo, robot: RobotSim):
        import mujoco

        ruta = robot.ruta_escena()
        if ruta is None:
            from .robots import faltan_modelos
            raise FileNotFoundError(faltan_modelos())

        self.mundo = mundo
        self.robot = robot
        self.mj = mujoco
        self.model = mujoco.MjModel.from_xml_path(ruta)
        self.data = mujoco.MjData(self.model)
        self.ruta = ruta
        # Sin gravedad: el modelo no tiene que caerse mientras lo posicionamos.
        self.model.opt.gravity[:] = 0.0
        self._primera_art = 7   # qpos[0:3] posicion, qpos[3:7] cuaternion

    def _pose(self) -> None:
        e = self.mundo.leer()
        q = self.data.qpos

        q[0] = e["x"]
        q[1] = e["y"]
        q[2] = self.robot.altura + e.get("z_suelo", 0.0)
        roll = float(e.get("roll", 0.0))
        pitch = float(e.get("pitch", 0.0))
        yaw = float(e["yaw"])
        cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
        cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
        cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
        q[3] = cr * cp * cy + sr * sp * sy
        q[4] = sr * cp * cy - cr * sp * sy
        q[5] = cr * sp * cy + sr * cp * sy
        q[6] = cr * cp * sy - sr * sp * cy

        art = q[self._primera_art:]
        art[:] = 0.0
        for idx, valor in self.robot.pose_de_pie.items():
            if idx < len(art):
                art[idx] = valor

        from .robots import aplicar_emote

        if aplicar_emote(
            art, self.robot,
            "six_seven" if e.get("accion") in ("six_seven", "festejando")
            else e["accion"],
        ):
            pass
        elif e["moviendose"]:
            f = e["fase"]
            for idx, amplitud, desfase in self.robot.marcha:
                if idx < len(art):
                    art[idx] += amplitud * math.sin(f + desfase)

        self.mj.mj_forward(self.model, self.data)

    def correr(self, hz: float = 50.0) -> None:
        import mujoco.viewer

        periodo = 1.0 / hz
        with mujoco.viewer.launch_passive(
            self.model, self.data, show_left_ui=False, show_right_ui=False
        ) as v:
            v.cam.distance = 3.5 if self.robot.tipo == "humanoide" else 2.6
            v.cam.elevation = -20
            while v.is_running():
                inicio = time.perf_counter()
                self.mundo.avanzar()
                self._pose()
                v.sync()
                resto = periodo - (time.perf_counter() - inicio)
                if resto > 0:
                    time.sleep(resto)


def correr_sin_ventana(mundo, hz: float = 50.0, detener=None) -> None:
    periodo = 1.0 / hz
    while detener is None or not detener.is_set():
        mundo.avanzar()
        time.sleep(periodo)
