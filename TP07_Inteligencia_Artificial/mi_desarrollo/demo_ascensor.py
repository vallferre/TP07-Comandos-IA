# =====================================================================
#  Demo: el robot se desestabiliza en el ascensor, y como evitarlo.
#
#  El simulador tiene que estar abierto (INICIAR_SIMULADOR).
#
#    py -3 mi_desarrollo/demo_ascensor.py
#    py -3 mi_desarrollo/demo_ascensor.py --seguro
# =====================================================================

from __future__ import annotations

import argparse
import sys
import time

from robot import Robot


def _esperar(robot: Robot, timeout: float = 50.0) -> dict:
    fin = time.monotonic() + timeout
    ultimo = ""
    estado = {}
    while time.monotonic() < fin:
        estado = _estado(robot)
        fase = estado.get("fase_ascensor", "")
        linea = (f"  fase={fase:<18}  z={estado.get('z_suelo', 0):+.2f} m  "
                 f"az={estado.get('az_ascensor', 0):+.2f} m/s2  "
                 f"pitch={estado.get('pitch', 0):+.2f}  "
                 f"{'SEGURO' if estado.get('modo_seguro') else 'equilibrio ON'}")
        if linea != ultimo:
            print(linea)
            ultimo = linea
        if fase in ("llegado", "caido") or estado.get("caido"):
            return estado
        time.sleep(0.2)
    return estado


def _estado(robot: Robot) -> dict:
    preguntar = getattr(robot._cliente, "Estado", None)
    if preguntar is None:
        return {}
    return preguntar() or {}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Recrea el problema del ascensor y el modo que lo evita")
    ap.add_argument("--seguro", action="store_true",
                    help="viaja con el equilibrio congelado (no se cae)")
    args = ap.parse_args()

    print()
    print("=" * 62)
    print("  ASCENSOR — recreacion del caso real")
    print("=" * 62)
    print()
    print("  En el robot fisico, al acelerar/frenar la cabina el IMU suma")
    print("  esa aceleracion vertical a la gravedad. El controlador de")
    print("  equilibrio cree que se esta cayendo y corrige: ahi se tambalea.")
    print()
    if args.seguro:
        print("  Este viaje: MODO SEGURO")
        print("    1. entra y frena")
        print("    2. congela locomocion")
        print("    3. ignora el transitorio vertical del IMU")
        print("    4. espera a que az vuelva a 0 y recien ahi suelta")
    else:
        print("  Este viaje: SIN proteccion (recrea el fallo)")
        print("    El equilibrio sigue activo -> se desestabiliza y cae.")
        print("  Para ver la solucion:  demo_ascensor.py --seguro")
    print("=" * 62)
    print()

    robot = Robot()
    robot.conectar()
    try:
        robot.iniciar_ascensor(proteccion=args.seguro)
        estado = _esperar(robot)
        print()
        if estado.get("fase_ascensor") == "caido" or estado.get("caido"):
            print("  RESULTADO: se cayo. Es el sintoma del caso real.")
            print("  Proba de nuevo con --seguro.")
            return 2
        print("  RESULTADO: llego de pie. El modo seguro evito la caida.")
        return 0
    finally:
        robot.desconectar()


if __name__ == "__main__":
    sys.exit(main())
