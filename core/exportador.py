"""Generación del archivo TXT de dispersión (formato de ancho fijo).

Replica el formato que producía la macro de Excel. Cada registro es una línea
de 102 caracteres terminada en CRLF:

    pos  0  ancho  3 : código de banco (los 3 primeros dígitos de la CLABE)
    pos  3  ancho 18 : CLABE
    pos 21  ancho  3 : moneda  -> 'MXP'
    pos 24  ancho 16 : monto, relleno con ceros a la izquierda, 2 decimales
    pos 40  ancho 30 : beneficiario, justificado a la izquierda (espacios)
    pos 70  ancho 30 : alias, justificado a la izquierda (espacios)
    pos 100 ancho  2 : tipo de cuenta -> '40' (CLABE)
"""

from __future__ import annotations

import re
import unicodedata

MONEDA = "MXP"
TIPO_CUENTA = "40"
ANCHO_MONTO = 16
ANCHO_NOMBRE = 30
FIN_LINEA = "\r\n"


def _ascii_banco(texto: str) -> str:
    """Convierte a ASCII en mayúsculas, sin acentos ni caracteres especiales
    (los archivos de banco solo aceptan letras, dígitos y espacios)."""
    sin_acentos = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    limpio = re.sub(r"[^A-Z0-9 ]", " ", sin_acentos.upper())
    return " ".join(limpio.split())


def _campo_nombre(texto: str) -> str:
    return _ascii_banco(texto)[:ANCHO_NOMBRE].ljust(ANCHO_NOMBRE)


def _campo_monto(monto: float | None) -> str:
    cadena = f"{float(monto or 0):.2f}"
    return cadena.rjust(ANCHO_MONTO, "0")[-ANCHO_MONTO:]


def linea_registro(clabe: str, monto: float | None, beneficiario: str, alias: str) -> str:
    """Construye la línea de ancho fijo para un beneficiario."""
    clabe = re.sub(r"\D", "", clabe or "")
    return (
        clabe[:3]
        + clabe
        + MONEDA
        + _campo_monto(monto)
        + _campo_nombre(beneficiario)
        + _campo_nombre(alias)
        + TIPO_CUENTA
    )


def generar_txt(registros: list[tuple[str, float | None, str, str]]) -> str:
    """Genera el contenido completo del TXT.

    Args:
        registros: lista de tuplas (clabe, monto, beneficiario, alias).
    """
    return "".join(linea_registro(*r) + FIN_LINEA for r in registros)
