"""Borra de sitio/ los simuladores vencidos y hace commit + push con la identidad LiciPy.

  python scripts/limpiar_vencidos.py [--config <csv local>] [--simular] [--sin-push]

De dónde saca los vencimientos (se usan todos los que haya):
  1. el CSV local de simuladores (--config, LICIPY_SIMULADORES o LICIPY_SALIDAS/config/simuladores.csv);
  2. la variable VENCIMIENTOS: una línea "carpeta:AAAA-MM-DDTHH:MM:SS-03:00" por simulador, sin
     nombres (en GitHub Actions viene del secret del mismo nombre);
  3. la marca <meta name="licipy-vence"> de cada página, que no tiene datos de clientes.
Si una carpeta tiene varias fechas, vale la más temprana.

No muestra nombres de clientes: en la consola solo aparecen los primeros caracteres de la carpeta.
"""

import argparse
import os
import re
import shutil
from datetime import datetime

from comun import (CARPETA_RE, PY, SITIO, commit_y_push, error, fecha, leer_config, ruta_config,
                   verificar_identidad)

META_RE = re.compile(r'<meta name="licipy-vence" content="([^"]+)"')


def vencimientos(config):
    v = {}

    def anotar(carpeta, cuando):
        carpeta = carpeta.strip()
        if CARPETA_RE.match(carpeta) and cuando.strip():
            f = fecha(cuando)
            v[carpeta] = min(v.get(carpeta, f), f)

    for fila in leer_config(config):
        anotar(fila.get("carpeta", ""), fila.get("vence", ""))
    for linea in os.environ.get("VENCIMIENTOS", "").splitlines():
        if ":" in linea:
            carpeta, cuando = linea.split(":", 1)
            anotar(carpeta, cuando)
    for pagina in SITIO.glob("*/index.html"):
        m = META_RE.search(pagina.read_text(encoding="utf-8", errors="ignore"))
        if m:
            anotar(pagina.parent.name, m.group(1))
    return v


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="CSV local de simuladores (fuera del repositorio)")
    ap.add_argument("--ahora", help="fecha y hora a usar en vez de la actual (para probar)")
    ap.add_argument("--simular", action="store_true", help="solo mostrar qué borraría")
    ap.add_argument("--sin-push", action="store_true", help="commit sin push")
    a = ap.parse_args()

    ahora = fecha(a.ahora) if a.ahora else datetime.now(PY)
    vencidas = sorted(c for c, f in vencimientos(ruta_config(a.config)).items()
                      if f <= ahora and (SITIO / c).is_dir())
    if vencidas and not a.simular:
        verificar_identidad()                 # antes de borrar nada
    print(f"{len(vencidas)} simulador(es) vencido(s) al {ahora.isoformat(timespec='minutes')}.")
    for c in vencidas:
        print(f"  {c[:6]}…" + (" (simulado)" if a.simular else ""))
        if not a.simular:
            # En Windows la carpeta vacía a veces queda trabada (Explorador, antivirus): da igual,
            # git no guarda carpetas vacías. Lo que importa es que no quede ningún archivo.
            shutil.rmtree(SITIO / c, ignore_errors=True)
            if any(p.is_file() for p in (SITIO / c).rglob("*")):
                error(f"no se pudieron borrar los archivos de {c[:6]}…: cierre lo que los tenga abiertos")
    hubo = bool(vencidas) and not a.simular and commit_y_push(
        f"Retirar {len(vencidas)} simulador(es) vencido(s)", ["sitio"], push=not a.sin_push)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"cambios={'si' if hubo else 'no'}\n")


if __name__ == "__main__":
    main()
