"""Escenario de ascensor: recrea por que el robot fisico se desestabiliza.

En el robot real el controlador de equilibrio lee el IMU. Cuando la cabina
acelera o frena en vertical, el acelerometro suma esa aceleracion a la
gravedad. El controlador cree que se esta cayendo o inclinando, corrige con
un paso o un ladeo, y ahi se desestabiliza.

Esto NO corre fisica de verdad (el simulador es cinematico). Modela el
sintoma: durante aceleracion/frenado, si el equilibrio sigue activo, el
robot se tambalea y cae. Si se activa el modo seguro -- congelar locomocion
e ignorar el transitorio vertical del IMU -- se mantiene de pie.

Eso es lo que hay que hacer en el G1/Go2 fisico: entrar, frenar, pasar a
un modo de hold/damp, esperar a que az vuelva a ~g, y recien ahi caminar.
"""

from __future__ import annotations

import math
import time

import numpy as np

# Cabina en el mundo. El robot arranca en x=0 y camina hacia +x.
X_CENTRO = 2.85
X_MIN, X_MAX = 1.55, 4.15
Y_MIN, Y_MAX = -1.20, 1.20
ALTO_CABINA = 2.70
ANCHO = X_MAX - X_MIN
FONDO = Y_MAX - Y_MIN

AZ_ASCENSOR = 1.20          # m/s^2, un ascensor de edificio tipico
T_ACEL = 1.60
T_CRUCERO = 2.00
T_PUERTA = 1.40

IDENTIDAD = np.eye(3).flatten()

# Paredes casi invisibles: se ve al robot adentro.
COLOR_PARED = np.array([0.70, 0.78, 0.88, 0.05], dtype=np.float32)
COLOR_TECHO = np.array([0.70, 0.78, 0.88, 0.03], dtype=np.float32)
COLOR_PISO = np.array([0.28, 0.30, 0.34, 0.55], dtype=np.float32)
COLOR_PUERTA = np.array([0.85, 0.90, 0.96, 0.08], dtype=np.float32)
COLOR_HALL = np.array([0.70, 0.72, 0.74, 0.30], dtype=np.float32)
COLOR_MARCO = np.array([0.30, 0.34, 0.40, 0.16], dtype=np.float32)
COLOR_PLATAFORMA = np.array([0.95, 0.78, 0.22, 1.00], dtype=np.float32)

X_SALIDA = -1.40
VEL_MARCHA = 0.35
VEL_GIRO = 1.10
T_EMOTE = 3.2


class Ascensor:
    """Maquina de estados del viaje. La integra `Mundo.avanzar`."""

    def __init__(self):
        self.apagar()

    def apagar(self) -> None:
        self.activo = False
        self.proteccion = False
        self.fase = "apagado"
        self.z = 0.0
        self.vz = 0.0
        self.az = 0.0
        self.t_fase = 0.0
        self.puerta = 1.0          # 1 abierta, 0 cerrada
        self.mensaje = ""

    def iniciar(self, proteccion: bool = False) -> None:
        self.apagar()
        self.activo = True
        self.proteccion = bool(proteccion)
        self.fase = "entrando"
        self.mensaje = (
            "MODO SEGURO: va a congelar el equilibrio antes de viajar"
            if self.proteccion else
            "SIN proteccion: el IMU se va a confundir al acelerar"
        )

    def forzar_salida(self, mundo) -> None:
        """Si el viaje termino y el robot sigue adentro, lo saca igual."""
        if mundo.caido:
            return
        mundo.modo_seguro = False
        self.activo = True
        self.puerta = 1.0
        self.az = 0.0
        self.vz = 0.0
        if self.fase in ("festejando", "llegado") and mundo.x <= X_SALIDA + 0.15:
            return
        self._pasar("girando_salida", mundo)
        mundo.avisos.append("Forzando salida a la plataforma.")

    def adentro(self, x: float, y: float) -> bool:
        return X_MIN <= x <= X_MAX and Y_MIN <= y <= Y_MAX

    def paso(self, dt: float, mundo) -> None:
        if not self.activo:
            return
        self.t_fase += dt
        fase = self.fase
        if fase == "entrando":
            self._entrar(dt, mundo)
        elif fase == "puertas_cerrando":
            self.puerta = max(0.0, 1.0 - self.t_fase / T_PUERTA)
            if self.t_fase >= T_PUERTA:
                self._pasar("acelerando", mundo)
                if self.proteccion:
                    mundo.modo_seguro = True
                    mundo.avisos.append(
                        "MODO ASCENSOR activo: locomocion congelada, "
                        "se ignora el transitorio vertical del IMU")
        elif fase == "acelerando":
            self._viajar(dt, mundo, az=AZ_ASCENSOR)
            if self.t_fase >= T_ACEL:
                self._pasar("crucero", mundo)
                self.az = 0.0
        elif fase == "crucero":
            self.az = 0.0
            self.z += self.vz * dt
            if self.t_fase >= T_CRUCERO:
                self._pasar("frenando", mundo)
        elif fase == "frenando":
            self._viajar(dt, mundo, az=-AZ_ASCENSOR)
            if self.t_fase >= T_ACEL or self.vz <= 0.0:
                self.vz = 0.0
                self.az = 0.0
                if mundo.caido:
                    self._pasar("caido", mundo)
                else:
                    # Primero el saludo (se ve adentro). Despues intenta salir.
                    self.puerta = 1.0
                    mundo.modo_seguro = False
                    self.fase = "festejando"
                    self.t_fase = 0.0
                    self.mensaje = "festejando"
                    mundo.gesto("six_seven", T_EMOTE)
                    mundo.avisos.append(
                        "Ascensor parado. Hace el 6-7 y despues sale.")
        elif fase == "puertas_abriendo":
            self.puerta = min(1.0, self.t_fase / T_PUERTA)
            if self.t_fase >= T_PUERTA and not mundo.caido:
                mundo.modo_seguro = False
                self.puerta = 1.0
                self._pasar("girando_salida", mundo)
        elif fase == "girando_salida":
            self.puerta = min(1.0, self.puerta + dt / T_PUERTA)
            self._girar_salida(dt, mundo)
        elif fase == "saliendo":
            self.puerta = 1.0
            self._salir(dt, mundo)
        elif fase == "festejando":
            if self.t_fase < T_EMOTE:
                mundo.accion = "six_seven"
            elif mundo.x > X_SALIDA + 0.20:
                self._pasar("girando_salida", mundo)
                mundo.avisos.append("Sale a la plataforma.")
            else:
                self._pasar("llegado", mundo)
                mundo.accion = "quieto"
        elif fase == "caido":
            self.az = 0.0

    def _pasar(self, fase: str, mundo) -> None:
        self.fase = fase
        self.t_fase = 0.0
        mundo.accion = fase
        self.mensaje = fase

    def _entrar(self, dt: float, mundo) -> None:
        if mundo.x < X_CENTRO - 0.08:
            mundo.x += VEL_MARCHA * dt
            mundo.vx = VEL_MARCHA
            mundo.vy = 0.0
            mundo.vyaw = 0.0
            mundo.accion = "entrando_ascensor"
        else:
            mundo.vx = mundo.vy = mundo.vyaw = 0.0
            mundo.accion = "quieto"
            self._pasar("puertas_cerrando", mundo)

    def _girar_salida(self, dt: float, mundo) -> None:
        # Queda mirando a la puerta (yaw = 180°) y despues camina hacia afuera.
        objetivo = math.pi
        error = (objetivo - mundo.yaw + math.pi) % (2 * math.pi) - math.pi
        if abs(error) > 0.10:
            mundo.vyaw = VEL_GIRO if error > 0 else -VEL_GIRO
            mundo.yaw += mundo.vyaw * dt
            mundo.yaw = (mundo.yaw + math.pi) % (2 * math.pi) - math.pi
            mundo.vx = mundo.vy = 0.0
            mundo.accion = "girando"
            return
        mundo.yaw = objetivo
        mundo.vyaw = 0.0
        self._pasar("saliendo", mundo)

    def _salir(self, dt: float, mundo) -> None:
        if mundo.x > X_SALIDA:
            mundo.x -= VEL_MARCHA * dt
            mundo.vx = VEL_MARCHA
            mundo.vy = 0.0
            mundo.vyaw = 0.0
            mundo.accion = "saliendo_ascensor"
            return
        mundo.x = X_SALIDA
        mundo.vx = mundo.vy = mundo.vyaw = 0.0
        self.fase = "festejando"
        self.t_fase = 0.0
        self.mensaje = "festejando"
        mundo.gesto("six_seven", T_EMOTE)
        mundo.avisos.append("Emote: 6-7")

    def _viajar(self, dt: float, mundo, az: float) -> None:
        self.az = az
        self.vz = max(0.0, self.vz + az * dt)
        self.z += self.vz * dt
        self._inestabilidad(dt, mundo)

    def _inestabilidad(self, dt: float, mundo) -> None:
        """El controlador de equilibrio 'cree' el IMU y corrige de mas."""
        if mundo.modo_seguro:
            mundo.roll = 0.0
            mundo.pitch = 0.0
            mundo.caido = False
            return

        # Caminar adentro mientras az != 0 empeora: el pie no encuentra el
        # piso que el IMU espera.
        mundo.inestabilidad += abs(self.az) * dt * 0.85
        if abs(mundo.vx) + abs(mundo.vy) > 1e-4:
            mundo.inestabilidad += 1.6 * dt

        t = time.time()
        ganancia = min(1.2, mundo.inestabilidad)
        mundo.pitch = 0.40 * math.sin(t * 9.0) * ganancia
        mundo.roll = 0.25 * math.sin(t * 7.0 + 0.8) * ganancia

        if mundo.inestabilidad > 1.10:
            mundo.caido = True
            mundo.de_pie = False
            mundo.pitch = 1.20
            mundo.roll = 0.40
            mundo.vx = mundo.vy = mundo.vyaw = 0.0
            mundo._vence_en = 0.0
            mundo.accion = "caido"
            self.fase = "caido"
            self.az = 0.0
            mundo.avisos.append(
                "CAIDA: el equilibrio compensó la aceleración del ascensor "
                "como si el robot se estuviera cayendo")


def dibujar_ascensor(user_scn, ascensor: Ascensor) -> int:
    """Cabina + hall superpuestos a la escena oficial, sin tocar el XML."""
    import mujoco

    n = 0
    z0 = float(ascensor.z)
    cx = (X_MIN + X_MAX) / 2.0
    cy = (Y_MIN + Y_MAX) / 2.0
    espesor = 0.035

    def _caja(tamano, pos, color):
        nonlocal n
        if n >= user_scn.maxgeom:
            return
        mujoco.mjv_initGeom(
            user_scn.geoms[n], mujoco.mjtGeom.mjGEOM_BOX,
            np.array(tamano, dtype=np.float64),
            np.array(pos, dtype=np.float64),
            IDENTIDAD, color)
        n += 1

    # Hall en la planta baja (no viaja).
    _caja([1.70, 1.40, 0.02], [0.05, 0.0, 0.02], COLOR_HALL)

    # Plataforma de llegada, a la altura de la cabina, bien visible.
    largo_plat = (X_MIN - X_SALIDA) / 2.0 + 0.80
    cx_plat = X_MIN - largo_plat
    _caja([largo_plat, FONDO / 2 + 0.15, 0.05],
          [cx_plat, cy, z0 + 0.05], COLOR_PLATAFORMA)

    # Piso de la cabina (viaja con z).
    _caja([ANCHO / 2, FONDO / 2, 0.04], [cx, cy, z0 + 0.04], COLOR_PISO)

    # Paredes: fondo, izquierda, derecha, techo.
    _caja([espesor, FONDO / 2, ALTO_CABINA / 2],
          [X_MAX, cy, z0 + ALTO_CABINA / 2], COLOR_PARED)
    _caja([ANCHO / 2, espesor, ALTO_CABINA / 2],
          [cx, Y_MAX, z0 + ALTO_CABINA / 2], COLOR_PARED)
    _caja([ANCHO / 2, espesor, ALTO_CABINA / 2],
          [cx, Y_MIN, z0 + ALTO_CABINA / 2], COLOR_PARED)
    _caja([ANCHO / 2, FONDO / 2, espesor],
          [cx, cy, z0 + ALTO_CABINA], COLOR_TECHO)

    # Marco de la puerta (frente, x = X_MIN).
    _caja([espesor, 0.10, ALTO_CABINA / 2],
          [X_MIN, Y_MAX - 0.10, z0 + ALTO_CABINA / 2], COLOR_MARCO)
    _caja([espesor, 0.10, ALTO_CABINA / 2],
          [X_MIN, Y_MIN + 0.10, z0 + ALTO_CABINA / 2], COLOR_MARCO)

    # Hojas de la puerta: se abren hacia los costados.
    hueco = FONDO - 0.28
    hoja = hueco / 4.0
    # puerta=1 abierta (hojas a los costados); puerta=0 cerrada (al centro).
    offset = (1.0 - ascensor.puerta) * 0.02 + ascensor.puerta * (hoja + 0.18)
    _caja([espesor, hoja, (ALTO_CABINA - 0.15) / 2],
          [X_MIN, cy + offset, z0 + (ALTO_CABINA - 0.15) / 2], COLOR_PUERTA)
    _caja([espesor, hoja, (ALTO_CABINA - 0.15) / 2],
          [X_MIN, cy - offset, z0 + (ALTO_CABINA - 0.15) / 2], COLOR_PUERTA)

    user_scn.ngeom = n
    return n
