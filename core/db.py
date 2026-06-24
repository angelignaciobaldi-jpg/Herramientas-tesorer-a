"""Persistencia local de beneficiarios (SQLite, sin servidor).

La base de datos vive junto a la aplicación en 'tesoreria.db'. La CLABE es la
clave única: no se permiten dos beneficiarios con la misma CLABE.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass

from . import rutas

RUTA_DB = os.path.join(rutas.DATOS, "tesoreria.db")


@dataclass
class Beneficiario:
    id: int
    clabe: str
    beneficiario: str
    alias: str
    email: str
    banco: str
    creado_en: str
    monto: float | None = None
    ruta_archivo: str | None = None


def _conectar() -> sqlite3.Connection:
    con = sqlite3.connect(RUTA_DB)
    con.row_factory = sqlite3.Row
    return con


def inicializar() -> None:
    """Crea la tabla de beneficiarios si no existe y aplica migraciones."""
    with _conectar() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS beneficiarios (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                clabe        TEXT    NOT NULL UNIQUE,
                beneficiario TEXT    NOT NULL,
                alias        TEXT    NOT NULL,
                email        TEXT,
                banco        TEXT,
                monto        REAL,
                ruta_archivo TEXT,
                creado_en    TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
            )
            """
        )
        # Migraciones: agrega columnas a bases creadas antes de que existieran.
        columnas = {fila["name"] for fila in con.execute("PRAGMA table_info(beneficiarios)")}
        if "monto" not in columnas:
            con.execute("ALTER TABLE beneficiarios ADD COLUMN monto REAL")
        if "ruta_archivo" not in columnas:
            con.execute("ALTER TABLE beneficiarios ADD COLUMN ruta_archivo TEXT")


class CLABEDuplicada(Exception):
    """Ya existe un beneficiario con esa CLABE."""


def guardar(
    clabe: str, beneficiario: str, alias: str, email: str, banco: str,
    monto: float | None = None, ruta_archivo: str | None = None,
) -> int:
    """Inserta un beneficiario. Devuelve su id. Lanza CLABEDuplicada si ya existe."""
    try:
        with _conectar() as con:
            cur = con.execute(
                """INSERT INTO beneficiarios
                   (clabe, beneficiario, alias, email, banco, monto, ruta_archivo)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (clabe, beneficiario, alias, email, banco, monto, ruta_archivo),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError as exc:
        raise CLABEDuplicada(clabe) from exc


def actualizar(
    id_beneficiario: int, clabe: str, beneficiario: str, alias: str, email: str,
    banco: str, monto: float | None = None, ruta_archivo: str | None = None,
) -> None:
    """Modifica un beneficiario existente. Lanza CLABEDuplicada si la nueva
    CLABE ya pertenece a otro registro."""
    try:
        with _conectar() as con:
            con.execute(
                """UPDATE beneficiarios
                   SET clabe = ?, beneficiario = ?, alias = ?, email = ?, banco = ?,
                       monto = ?, ruta_archivo = ?
                   WHERE id = ?""",
                (clabe, beneficiario, alias, email, banco, monto, ruta_archivo, id_beneficiario),
            )
    except sqlite3.IntegrityError as exc:
        raise CLABEDuplicada(clabe) from exc


def listar() -> list[Beneficiario]:
    with _conectar() as con:
        filas = con.execute(
            "SELECT * FROM beneficiarios ORDER BY creado_en DESC, id DESC"
        ).fetchall()
    return [Beneficiario(**dict(f)) for f in filas]


def eliminar(id_beneficiario: int) -> None:
    with _conectar() as con:
        con.execute("DELETE FROM beneficiarios WHERE id = ?", (id_beneficiario,))
