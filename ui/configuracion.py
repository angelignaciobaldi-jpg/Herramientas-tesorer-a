"""Configuración: credenciales de inicio de sesión del SIPP (para el RPA).

Se abre como diálogo desde el botón de la barra superior. Captura usuario y
contraseña, que siempre se guardan localmente con la contraseña cifrada (ver
core/credenciales.py). Otras pantallas (p. ej. el RPA de dispersión) leen estas
credenciales con el método credenciales().
"""

from __future__ import annotations

import flet as ft

from core import credenciales
from ui.comun import VERDE

# Ancho útil del modal: los inputs lo abarcan de margen a margen.
_ANCHO = 400


class SeccionConfiguracion:
    """Diálogo de configuración con las credenciales del SIPP."""

    def __init__(self, app):
        self.app = app
        self.page = app.page
        self._construir()
        self._cargar_credenciales()

    # ------------------------------------------------------------ UI
    def _construir(self) -> None:
        self.tf_usuario = ft.TextField(
            label="Usuario", width=_ANCHO, height=40, dense=True, content_padding=10,
        )
        self.tf_contrasena = ft.TextField(
            label="Contraseña", width=_ANCHO, password=True, height=40,
            can_reveal_password=False, dense=True, content_padding=10,
        )
        # Apartado "Credenciales SIPP" dentro de la configuración.
        credenciales_apartado = ft.Column(
            [
                ft.Text("Credenciales SIPP", size=15, weight=ft.FontWeight.BOLD),
                self.tf_usuario,
                self.tf_contrasena,
            ],
            spacing=12, tight=True,
        )
        self.dialogo = ft.AlertDialog(
            modal=True,
            # Encabezado: título grande en negritas + botón "X" para cerrar.
            title=ft.Row(
                [
                    ft.Text("Configuración", size=25, weight=ft.FontWeight.BOLD),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE, tooltip="Cerrar", on_click=self._cerrar,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                width=_ANCHO,
            ),
            content=ft.Column([credenciales_apartado], spacing=18, tight=True, width=_ANCHO),
            actions=[
                ft.FilledButton("Guardar", icon=ft.Icons.SAVE, on_click=self._guardar),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    # -------------------------------------------------------- acciones
    def abrir(self, _e=None) -> None:
        self.page.show_dialog(self.dialogo)

    def _cerrar(self, _e=None) -> None:
        self.page.pop_dialog()

    def _guardar(self, _e=None) -> None:
        """Guarda las credenciales (la contraseña, cifrada)."""
        usuario, contrasena = self.credenciales()
        credenciales.guardar(usuario, contrasena)
        self._cerrar()
        self.app.avisar("Configuración guardada.", VERDE)

    # --------------------------------------------------- credenciales
    def _cargar_credenciales(self) -> None:
        """Precarga las credenciales guardadas, si las hay."""
        datos = credenciales.cargar()
        if datos is None:
            return
        usuario, contrasena = datos
        self.tf_usuario.value = usuario
        self.tf_contrasena.value = contrasena

    def credenciales(self) -> tuple[str, str]:
        """Devuelve (usuario, contraseña) tal como están capturados ahora."""
        return (self.tf_usuario.value or "").strip(), self.tf_contrasena.value or ""
