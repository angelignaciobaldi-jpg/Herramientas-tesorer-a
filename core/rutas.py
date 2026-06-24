"""Rutas base de la aplicación, válidas tanto en desarrollo como empaquetada.

Distingue dos ubicaciones:
  - BUNDLE: archivos empaquetados de solo lectura (tessdata, Imagenes).
            Al estar congelado con PyInstaller, viven en la carpeta temporal
            de extracción (sys._MEIPASS).
  - DATOS : archivos externos/escribibles (base de datos, caché, el Excel de
            cuentas bancarias que el usuario actualiza). Al estar congelado,
            es la carpeta donde está el .exe.
En desarrollo, ambas apuntan a la carpeta del proyecto.
"""

from __future__ import annotations

import os
import sys

_PROYECTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if getattr(sys, "frozen", False):  # ejecutándose como .exe (PyInstaller)
    BUNDLE = getattr(sys, "_MEIPASS", _PROYECTO)
    DATOS = os.path.dirname(sys.executable)
else:  # ejecutándose como script de Python
    BUNDLE = _PROYECTO
    DATOS = _PROYECTO
