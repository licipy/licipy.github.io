"""Piezas comunes de nuevo_simulador.py y limpiar_vencidos.py.

Identidad: todos los commits de este repositorio salen como LiciPy. Los scripts no hacen
commit si `git config --local` no tiene exactamente esa identidad.

Archivo de configuración (fuera del repositorio, por ejemplo en Drive, salidas/config):
  --config <ruta>, o la variable LICIPY_SIMULADORES, o LICIPY_SALIDAS/config/simuladores.csv
Columnas: llamado, cliente (iniciales o ID interno), carpeta, vence, url, creado.
"""

import csv
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SITIO = RAIZ / "sitio"
PLANTILLA = RAIZ / "plantilla"
URL_BASE = "https://licipy.github.io/"
PY = timezone(timedelta(hours=-3))                 # Paraguay, sin horario de verano desde 2024
NOMBRE, CORREO = "LiciPy", "licipy@users.noreply.github.com"
COLUMNAS = ["llamado", "cliente", "carpeta", "vence", "url", "creado"]
CARPETA_RE = re.compile(r"^[a-z0-9]{24,}$")


def error(msg):
    sys.exit(f"ERROR: {msg}")


def fecha(texto):
    """'AAAA-MM-DD HH:MM' (hora de Paraguay, -03:00) o ISO con zona. Devuelve datetime con zona."""
    t = texto.strip().replace(" ", "T", 1)
    try:
        d = datetime.fromisoformat(t)
    except ValueError:
        error(f"fecha inválida: {texto!r} (use AAAA-MM-DD HH:MM)")
    return d if d.tzinfo else d.replace(tzinfo=PY)


def iso(d):
    return d.astimezone(PY).isoformat(timespec="seconds")


def ruta_config(arg):
    r = arg or os.environ.get("LICIPY_SIMULADORES")
    if not r and os.environ.get("LICIPY_SALIDAS"):
        r = Path(os.environ["LICIPY_SALIDAS"]) / "config" / "simuladores.csv"
    if not r:
        return None
    r = Path(r).resolve()
    if r == RAIZ or RAIZ in r.parents:
        error(f"el archivo de configuración no puede estar dentro del repositorio: {r}")
    return r


def leer_config(ruta):
    if not ruta or not ruta.exists():
        return []
    with open(ruta, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def agregar_config(ruta, fila):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not ruta.exists()
    with open(ruta, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        if nuevo:
            w.writeheader()
        w.writerow(fila)


def git(*args, salida=False):
    r = subprocess.run(["git", "-C", str(RAIZ), *args], capture_output=True, text=True)
    if r.returncode:
        error(f"git {' '.join(args)}: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout.strip() if salida else None


def verificar_identidad():
    for clave, esperado in (("user.name", NOMBRE), ("user.email", CORREO)):
        r = subprocess.run(["git", "-C", str(RAIZ), "config", "--local", "--get", clave],
                           capture_output=True, text=True)
        if r.stdout.strip() != esperado:
            error(f"identidad git incorrecta: {clave}={r.stdout.strip()!r}. Corra:\n"
                  f'  git config --local user.name "{NOMBRE}"\n'
                  f'  git config --local user.email "{CORREO}"')


def commit_y_push(mensaje, rutas, push=True):
    verificar_identidad()
    git("add", "-A", "--", *rutas)
    if not git("status", "--porcelain", "--", *rutas, salida=True):
        print("Sin cambios para commitear.")
        return False
    # -c fuerza la identidad aunque haya variables GIT_AUTHOR_* en el entorno
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_AUTHOR_", "GIT_COMMITTER_"))}
    r = subprocess.run(["git", "-C", str(RAIZ), "-c", f"user.name={NOMBRE}", "-c", f"user.email={CORREO}",
                        "commit", "-q", "-m", mensaje], capture_output=True, text=True, env=env)
    if r.returncode:
        error(f"git commit: {r.stderr.strip()}")
    print(f"Commit: {mensaje}")
    if push:
        rama = git("rev-parse", "--abbrev-ref", "HEAD", salida=True)
        git("push", "-q", "origin", rama)
        print(f"Push a origin/{rama}.")
    return True
