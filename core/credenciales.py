"""Almacenamiento local y cifrado de las credenciales del RPA.

Las credenciales se guardan en un archivo JSON junto a la aplicación. La
contraseña nunca se guarda en claro: se cifra con DPAPI (Data Protection API de
Windows). DPAPI ata el cifrado a la cuenta de usuario de Windows, así que solo
el mismo usuario en la misma máquina puede descifrarla, y sin que tengamos que
manejar (ni guardar) una llave propia.

Se usa vía ctypes para no agregar dependencias; solo funciona en Windows, que es
la plataforma de la herramienta.
"""

from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes
import json
import os

from . import rutas

RUTA = os.path.join(rutas.DATOS, "credenciales_rpa.json")


class _DATA_BLOB(ctypes.Structure):
    """Estructura DATA_BLOB que DPAPI usa para entrada y salida."""

    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _a_blob(datos: bytes) -> _DATA_BLOB:
    buffer = ctypes.create_string_buffer(datos, len(datos))
    return _DATA_BLOB(len(datos), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))


def _de_blob(blob: _DATA_BLOB) -> bytes:
    datos = ctypes.string_at(blob.pbData, blob.cbData)
    ctypes.windll.kernel32.LocalFree(blob.pbData)  # DPAPI reserva la memoria
    return datos


def _cifrar(texto: str) -> str:
    entrada = _a_blob(texto.encode("utf-8"))
    salida = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(entrada), None, None, None, None, 0, ctypes.byref(salida)
    ):
        raise OSError("No se pudo cifrar la credencial (DPAPI).")
    return base64.b64encode(_de_blob(salida)).decode("ascii")


def _descifrar(b64: str) -> str:
    entrada = _a_blob(base64.b64decode(b64))
    salida = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(entrada), None, None, None, None, 0, ctypes.byref(salida)
    ):
        raise OSError("No se pudo descifrar la credencial (DPAPI).")
    return _de_blob(salida).decode("utf-8")


def guardar(usuario: str, contrasena: str) -> None:
    """Guarda usuario (en claro) y contraseña (cifrada) en el archivo local."""
    datos = {"usuario": usuario, "contrasena": _cifrar(contrasena)}
    with open(RUTA, "w", encoding="utf-8") as fh:
        json.dump(datos, fh)


def cargar() -> tuple[str, str] | None:
    """Devuelve (usuario, contraseña) si hay credenciales guardadas y se pueden
    descifrar; None si no hay archivo o no se puede leer/descifrar."""
    if not os.path.exists(RUTA):
        return None
    try:
        with open(RUTA, encoding="utf-8") as fh:
            datos = json.load(fh)
        return datos.get("usuario", ""), _descifrar(datos["contrasena"])
    except (OSError, ValueError, KeyError):
        return None


def borrar() -> None:
    """Elimina las credenciales guardadas (al desmarcar 'recordar')."""
    try:
        os.remove(RUTA)
    except FileNotFoundError:
        pass
