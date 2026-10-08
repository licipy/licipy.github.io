"""Genera un simulador de precio en sitio/<carpeta aleatoria>/index.html.

  python scripts/nuevo_simulador.py datos_493194.json --vence "2026-10-09 12:00" --cliente EJO
        [--config "G:/Mi unidad/licita-pymes/salidas/config/simuladores.csv"] [--publicar]

El JSON del llamado lleva solo datos públicos de la DNCP (ver ejemplos/ejemplo.json). Antes de
generar se rechaza si tiene campos o textos de cliente (nombre, RUC, teléfono, correo, palabras prohibidas).

El contenido de la página va cifrado (AES-GCM). La clave viaja solo en el enlace, después de
"#", y el navegador no la manda al servidor: en el repositorio público queda solo texto cifrado.

La relación cliente -> carpeta se anota solo en el archivo de configuración local, fuera del
repositorio. --cliente acepta iniciales o un ID interno, nunca el nombre completo ni el RUC.
Sin --publicar no hace commit: revise la página y después corra con --publicar o haga el
commit a mano.
"""

import argparse
import base64
import hashlib
import os
import html
import json
import re
import secrets
import string
import sys
import unicodedata
from datetime import datetime

from comun import (PLANTILLA, PY, SITIO, URL_BASE, agregar_config, commit_y_push, error, fecha, iso,
                   ruta_config, verificar_identidad)

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    sys.exit("Falta el paquete cryptography:  pip install cryptography")

LARGO = 32
CAMPOS_PROHIBIDOS = {
    "cliente", "nombrecliente", "razonsocial", "ruc", "ci", "cedula", "telefono", "tel", "celular",
    "whatsapp", "correo", "email", "mail", "contacto", "preparadopara", "destinatario", "para",
    "oferente", "proveedor", "empresa", "direccion", "nombre",
}
# "nombre" se permite solo dentro de "comparables" (competidores, dato público de la DNCP)
NOMBRE_PERMITIDO_EN = {"comparables"}
TEXTOS_PROHIBIDOS = [
    (re.compile(r"\b\d{5,8}-\d\b"), "RUC"),
    (re.compile(r"(\+?595|\b0)9\d{2}[\s.-]?\d{3}[\s.-]?\d{3}\b"), "teléfono"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "correo"),
    (re.compile(r"preparado para(?! (su|el) llamado)", re.I), "'Preparado para <nombre>'"),
]
# Palabras que nunca pueden aparecer (nombres propios y marcas ajenas). Van como sha256 para no
# escribirlas en el repositorio. Se suman las de la variable LICIPY_PROHIBIDAS (separadas por
# coma), por ejemplo nombres de clientes, que quedan solo en la PC.
PROHIBIDAS_SHA = {
    "c857d09db23e6822e3600bc06ad8d58f92ed62bc8efd81c753f77048662cb97d",
    "c70eca6b0f88f44d81a41311647e50fda1ac454ec04ffd442b0eb4743a993131",
    "1315d80f42fa8d683b9d39c7b54c579af14f2d959595750e1b524e4877de0990",
    "8849853b957fe153b7056d0e7d65f99fb21070daf5122ddf1d7c942d4643c33d",
}


def palabra_prohibida(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    extra = [norm_txt(w) for w in os.environ.get("LICIPY_PROHIBIDAS", "").split(",") if len(norm_txt(w)) >= 4]
    for w in extra:
        if w in t:
            return w
    for m in re.finditer(r"[a-z0-9]+", t):
        pal = m.group(0)
        for i in range(len(pal)):
            for j in range(i + 4, min(len(pal), i + 12) + 1):
                if hashlib.sha256(pal[i:j].encode()).hexdigest() in PROHIBIDAS_SHA:
                    return pal
    return None


def norm_txt(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


OBLIGATORIOS = ["llamado", "entidad", "sigla", "objeto", "modalidad", "monto", "cierre", "datos_al",
                "escala", "inicial", "comparables", "bandas", "items", "fuentes"]
COMO_CALCULA = ("En un contrato abierto se factura hasta el monto máximo con cualquier precio: si baja "
                "su porcentaje, entrega más trabajos por la misma plata. Ganancia ≈ monto máximo sin "
                "IVA × (1 − su costo ÷ su meta) − gastos fijos. Es una orientación: la decisión de "
                "precio es suya.")


def norm(k):
    k = unicodedata.normalize("NFKD", str(k)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", k)


def validar(d, ruta="", padre=""):
    """Lista de problemas: campos de cliente y textos con RUC, teléfono, correo o palabras prohibidas."""
    malos = []
    if isinstance(d, dict):
        for k, v in d.items():
            n = norm(k)
            if n in CAMPOS_PROHIBIDOS and not (n == "nombre" and padre in NOMBRE_PERMITIDO_EN):
                malos.append(f"campo prohibido '{ruta}{k}'")
            malos += validar(v, f"{ruta}{k}.", k)
    elif isinstance(d, list):
        for i, v in enumerate(d):
            malos += validar(v, f"{ruta}{i}.", padre)
    elif isinstance(d, str):
        for rx, que in TEXTOS_PROHIBIDOS:
            if rx.search(d):
                malos.append(f"{que} en '{ruta.rstrip('.')}': {d[:60]!r}")
        if palabra_prohibida(d):
            malos.append(f"palabra prohibida en '{ruta.rstrip('.')}'")
    return malos


def gs(v):
    return "Gs. " + f"{round(v):,}".replace(",", ".")


def dmy(d, hora=True):
    return d.astimezone(PY).strftime("%d/%m/%Y %H:%M" if hora else "%d/%m/%Y")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("datos", help="JSON con los datos públicos del llamado")
    ap.add_argument("--vence", required=True, help='fecha de vencimiento, "AAAA-MM-DD HH:MM" en hora de Paraguay')
    ap.add_argument("--cliente", default="", help="iniciales o ID interno (solo va al archivo de configuración)")
    ap.add_argument("--config", help="CSV local de simuladores (fuera del repositorio)")
    ap.add_argument("--publicar", action="store_true", help="commit + push con la identidad LiciPy")
    a = ap.parse_args()

    with open(a.datos, encoding="utf-8") as f:
        d = json.load(f)
    malos = validar(d)
    if a.cliente and (len(a.cliente) > 12 or validar({"x": a.cliente})):
        malos.append("--cliente debe ser iniciales o un ID interno corto, no el nombre ni el RUC")
    falta = [k for k in OBLIGATORIOS if k not in d]
    if falta:
        malos.append(f"faltan campos: {', '.join(falta)}")
    if malos:
        error("el JSON no se puede publicar:\n  - " + "\n  - ".join(malos))

    vence = fecha(a.vence)
    if vence <= datetime.now(PY):
        error(f"la fecha de vencimiento ya pasó: {iso(vence)}")
    cierre = fecha(d["cierre"])
    config = ruta_config(a.config)
    if not config:
        error("indique --config o la variable LICIPY_SIMULADORES (CSV fuera del repositorio)")
    if a.publicar:
        verificar_identidad()

    e = lambda s: html.escape(str(s), quote=True)
    valores = {
        "LLAMADO": e(d["llamado"]), "ENTIDAD": e(d["entidad"]), "SIGLA": e(d["sigla"]),
        "OBJETO": e(d["objeto"]), "MODALIDAD": e(d["modalidad"]), "MONTO_TXT": e(gs(d["monto"])),
        "CIERRE_TXT": dmy(cierre), "CIERRE_FECHA": dmy(cierre, False),
        "DATOS_AL": dmy(fecha(d["datos_al"] + " 00:00"), False), "VENCE_TXT": dmy(vence),
        "ITEMS_HINT": e(d.get("items_hint", "Ítems del pliego con precio a batir.")),
        "COMO_CALCULA": e(d.get("como_calcula", COMO_CALCULA)), "FUENTES": e(d["fuentes"]),
    }
    contenido = (PLANTILLA / "contenido.html").read_text(encoding="utf-8")
    for k, v in valores.items():
        contenido = contenido.replace("{{" + k + "}}", v)
    datos = {k: d[k] for k in ("monto", "escala", "inicial", "comparables", "bandas", "items")}
    datos["bandas_nota"] = d.get("bandas_nota", "")
    datos["iva_divisor"] = d.get("iva_divisor", 1.1)
    carga = json.dumps({"titulo": f"Simulador de precio {d['llamado']}", "html": contenido, "datos": datos},
                       ensure_ascii=False).encode()

    clave = AESGCM.generate_key(bit_length=256)
    iv = secrets.token_bytes(12)
    cifrado = base64.b64encode(iv + AESGCM(clave).encrypt(iv, carga, None)).decode()
    clave_url = base64.urlsafe_b64encode(clave).decode().rstrip("=")

    pagina = (PLANTILLA / "simulador.html").read_text(encoding="utf-8").replace("{{VENCE_ISO}}", iso(vence))
    if "{{" in pagina.replace("{{CIFRADO}}", "") or "{{" in contenido:
        error("quedaron marcadores sin reemplazar en la plantilla")
    for texto in (pagina, contenido):         # se revisa antes de meter el cifrado
        for rx, que in TEXTOS_PROHIBIDOS:
            if rx.search(texto):
                error(f"la página generada contiene {que}: {rx.search(texto).group(0)!r}")
        if palabra_prohibida(texto):
            error("la página generada contiene una palabra prohibida")
    pagina = pagina.replace("{{CIFRADO}}", cifrado)

    alfabeto = string.ascii_lowercase + string.digits
    while True:
        carpeta = "".join(secrets.choice(alfabeto) for _ in range(LARGO))
        if not (SITIO / carpeta).exists():
            break
    (SITIO / carpeta).mkdir(parents=True)
    (SITIO / carpeta / "index.html").write_text(pagina, encoding="utf-8")

    url = f"{URL_BASE}{carpeta}/#{clave_url}"
    agregar_config(config, {"llamado": d["llamado"], "cliente": a.cliente, "carpeta": carpeta,
                            "vence": iso(vence), "url": url, "creado": iso(datetime.now(PY))})
    print(f"Simulador del llamado {d['llamado']} en sitio/{carpeta}/index.html")
    print(f"Anotado en {config}")
    print(f"Línea para el secret VENCIMIENTOS:  {carpeta}:{iso(vence)}")
    if a.publicar:
        commit_y_push(f"Nuevo simulador (vence {dmy(vence, False)})", ["sitio"])
    else:
        print("Sin publicar. Revise y después:  git add sitio && git commit -m \"Nuevo simulador\" && git push")
    print(f"\nURL:  {url}")


if __name__ == "__main__":
    main()
