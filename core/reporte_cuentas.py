"""Lector del reporte 'Cuentas Bancarias' para conciliar con los estados de cuenta.

El reporte (Excel) trae, por cada proveedor, su CLABE (columna 'Cuenta'), el
nombre del beneficiario, una descripción, el banco, el RFC y el correo. Se usa
para complementar/validar los registros extraídos por OCR: si la CLABE de un
estado de cuenta aparece en el reporte, se toman de ahí el nombre y el correo,
que son la fuente autorizada.

El formato del archivo trae filas de metadatos arriba (título, fechas, etc.),
así que la fila de encabezados se localiza buscando las columnas 'Beneficiario'
y 'Cuenta' en lugar de asumir una posición fija.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import openpyxl


@dataclass
class CuentaReporte:
    clabe: str
    beneficiario: str
    descripcion: str
    banco: str
    rfc: str
    correo: str


def _norm(valor) -> str:
    return str(valor).strip().lower() if valor is not None else ""


def _solo_digitos(valor) -> str:
    return re.sub(r"\D", "", str(valor)) if valor is not None else ""


def leer(ruta: str) -> dict[str, CuentaReporte]:
    """Lee el reporte y devuelve un diccionario {CLABE -> CuentaReporte}.

    Lanza ValueError si el Excel no tiene el formato esperado (sin columnas
    'Beneficiario' y 'Cuenta').
    """
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    try:
        ws = wb.active
        filas = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()

    # Localiza la fila de encabezados (la que tiene 'Beneficiario' y 'Cuenta')
    # y mapea cada título a su número de columna.
    col: dict[str, int] = {}
    idx_enc: int | None = None
    for i, fila in enumerate(filas):
        titulos = {_norm(v) for v in fila}
        if "beneficiario" in titulos and "cuenta" in titulos:
            idx_enc = i
            col = {_norm(v): j for j, v in enumerate(fila) if _norm(v)}
            break
    if idx_enc is None:
        raise ValueError(
            "El Excel no tiene el formato del reporte 'Cuentas Bancarias' "
            "(no se encontraron las columnas 'Beneficiario' y 'Cuenta')."
        )

    def campo(fila, *nombres: str) -> str:
        for n in nombres:
            j = col.get(n)
            if j is not None and j < len(fila) and fila[j] is not None:
                return str(fila[j]).strip()
        return ""

    catalogo: dict[str, CuentaReporte] = {}
    for fila in filas[idx_enc + 1:]:
        clabe = _solo_digitos(campo(fila, "cuenta"))
        if len(clabe) != 18:  # ignora totales, cuentas extranjeras y filas vacías
            continue
        catalogo[clabe] = CuentaReporte(
            clabe=clabe,
            beneficiario=campo(fila, "beneficiario"),
            descripcion=campo(fila, "descripción", "descripcion"),
            banco=campo(fila, "nombre banco"),
            rfc=campo(fila, "rfc"),
            correo=campo(fila, "correo"),
        )
    return catalogo
