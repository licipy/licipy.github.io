"""Pruebas fijas del validador de nuevo_simulador.py (casos aprobados el 12/10/2026).

Regla: los nombres que vienen del registro público de la DNCP (convocante, adjudicatarios, ítems)
nunca se bloquean por nombre; sí se bloquean los nombres como destinatario o cliente_ref y en los
textos nuestros. RUC, teléfono y correo se rechazan en cualquier campo.

  python -m unittest discover -s tests -v
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import nuevo_simulador as n  # noqa: E402

# Nombres ficticios que figuran en la lista local de nombres prohibidos (como si fueran contactos).
# Las palabras fijas del validador van como sha256 y siguen el mismo camino que esta lista.
PROHIBIDAS = {"LICIPY_PROHIBIDAS": "Juana Prueba Ficticia,Pedro Ejemplo Inventado"}


class Validador(unittest.TestCase):
    def acepta(self, datos):
        with mock.patch.dict(os.environ, PROHIBIDAS):
            self.assertEqual(n.validar(datos), [])

    def rechaza(self, datos):
        with mock.patch.dict(os.environ, PROHIBIDAS):
            self.assertNotEqual(n.validar(datos), [])

    def test_adjudicatario_que_tambien_es_contacto(self):
        self.acepta({"comparables": [{"nombre": "J. P. Ficticia", "pct": 0.85}],
                     "competidores": [{"nombre": "Juana Prueba Ficticia", "n": 1}]})

    def test_adjudicatario_con_nombre_prohibido(self):
        self.acepta({"competidores": [{"nombre": "Pedro Ejemplo Inventado", "n": 2}],
                     "items": [{"descripcion": "Trabajos según Pedro Ejemplo Inventado", "unidad": "Unidad"}]})

    def test_convocante(self):
        self.acepta({"entidad": "Municipalidad de Pedro Ejemplo Inventado", "sigla": "la MPEI",
                     "objeto": "Plaza Juana Prueba Ficticia"})

    def test_contacto_en_texto_nuestro(self):
        self.rechaza({"fuentes": "Datos de Juana Prueba Ficticia"})
        self.rechaza({"bandas_nota": "Pedro Ejemplo Inventado"})

    def test_destinatario_y_cliente(self):
        self.rechaza({"destinatario": "Juan"})
        self.rechaza({"cliente": "C-001"})

    def test_ruc_en_un_adjudicatario(self):
        self.rechaza({"comparables": [{"nombre": "X 4000603-4", "pct": 1}]})

    def test_telefono_en_el_objeto(self):
        self.rechaza({"objeto": "llamar al 0981 123 456"})


if __name__ == "__main__":
    unittest.main()
