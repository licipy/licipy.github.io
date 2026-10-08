# licipy.github.io

Simuladores de precio de LiciPy para llamados de la DNCP. Información de fuentes públicas
(DNCP, datos abiertos). No garantiza la adjudicación.

- `sitio/`: lo que se publica en https://licipy.github.io/. La raíz no enlaza a nada y
  `robots.txt` bloquea todo. Cada simulador está en una carpeta aleatoria de 32 caracteres, con
  `noindex,nofollow`, y su contenido va cifrado: la clave está solo en el enlace, después de `#`.
- `plantilla/`: `simulador.html` (la página, sin datos) y `contenido.html` (la parte que se cifra).
- `scripts/nuevo_simulador.py`: genera un simulador a partir de un JSON con datos públicos del
  llamado (formato en `ejemplos/ejemplo.json`). Rechaza el JSON si trae datos de cliente.
- `scripts/limpiar_vencidos.py`: borra los simuladores vencidos y hace commit + push.
- `.github/workflows/publicar.yml`: publica `sitio/` y cada hora retira los vencidos.

Los datos de cada llamado y la relación cliente → carpeta no se guardan acá: quedan en un CSV
local (`--config` o la variable `LICIPY_SIMULADORES`).

## Uso

    pip install cryptography
    git config --local user.name "LiciPy"
    git config --local user.email "licipy@users.noreply.github.com"
    python scripts/nuevo_simulador.py datos_493194.json --vence "2026-10-09 12:00" --cliente C001 --config "<ruta>/simuladores.csv"
    python scripts/nuevo_simulador.py ... --publicar        # lo mismo, con commit + push
    python scripts/limpiar_vencidos.py --config "<ruta>/simuladores.csv" [--simular]
