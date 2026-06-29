"""Herramienta Integral de Tesorería — punto de entrada (shell).

Arma la ventana: encabezado con logo y botón de modo claro/oscuro, y las
pestañas. Cada pestaña es una pantalla en su propio módulo, para que se pueda
trabajar en colaboración sin pisarse:

    ui/alta_beneficiarios.py  -> pestaña "Alta de beneficiarios"
    ui/devoluciones.py        -> pestaña "Generar dispersión devoluciones"
    ui/comun.py               -> constantes y utilidades compartidas

El shell expone a cada pantalla: page, picker (diálogos de archivo) y avisar().
"""

from __future__ import annotations

import flet as ft

from core import db, ocr, rutas
from ui.alta_beneficiarios import SeccionAltaBeneficiarios
from ui.configuracion import SeccionConfiguracion
from ui.devoluciones import SeccionDevoluciones
from ui.dispersion_no_pemex import SeccionDispersionNoPemex


class AppTesoreria: 
    """Shell de la aplicación: ventana, encabezado, tema y pestañas."""

    def __init__(self, page: ft.Page):
        self.page = page
        self.picker = ft.FilePicker()
        page.services.append(self.picker)
        self._construir()

    # Servicio compartido por todas las pantallas: aviso tipo snackbar.
    def avisar(self, mensaje: str, color: str | None = None) -> None:
        self.page.show_dialog(
            ft.SnackBar(content=ft.Text(mensaje, color=ft.Colors.WHITE), bgcolor=color)
        )

    def _construir(self) -> None:
        # Cada pantalla construye su propio contenido.
        self.config = SeccionConfiguracion(self)
        self.alta = SeccionAltaBeneficiarios(self)
        self.devoluciones = SeccionDevoluciones(self)
        self.dispersion_no_pemex = SeccionDispersionNoPemex(self)

        tabs = ft.Tabs(
            length=3,
            expand=True,
            content=ft.Column(
                [
                    ft.TabBar(
                        tabs=[
                            ft.Tab(label="Alta de beneficiarios", icon=ft.Icons.ACCOUNT_BALANCE),
                            ft.Tab(label="Generar dispersión devoluciones",
                                   icon=ft.Icons.CURRENCY_EXCHANGE),
                            ft.Tab(label="Dispersión (No Pemex)", icon=ft.Icons.PAYMENTS),
                        ]
                    ),
                    ft.TabBarView(
                        controls=[self.alta.contenido, self.devoluciones.contenido, self.dispersion_no_pemex.contenido],
                        expand=True,
                    ),
                ],
                expand=True,
            ),
        )

        # Encabezado: logo (izquierda) y botón de modo claro/oscuro (derecha).
        self.logo = ft.Image(
            src="Imagenes/Quetzaltic Texto negro.png",
            height=58, fit=ft.BoxFit.CONTAIN,
            error_content=ft.Text("Quetzaltic Solutions", weight=ft.FontWeight.BOLD, size=20),
        )
        self.btn_config = ft.IconButton(
            icon=ft.Icons.SETTINGS, tooltip="Configuración", on_click=self.config.abrir,
        )
        self.btn_tema = ft.IconButton(
            icon=ft.Icons.DARK_MODE, tooltip="Modo oscuro", on_click=self._alternar_tema,
        )
        encabezado = ft.Row(
            [self.logo, ft.Row([self.btn_config, self.btn_tema])],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Pie de página: crédito fijo abajo, centrado y discreto.
        pie = ft.Container(
            content=ft.Text(
                "Quetzaltic Solutions - 2026",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
                text_align=ft.TextAlign.CENTER,
            ),
            alignment=ft.Alignment(0, 0),
            padding=6,
        )

        self.page.add(encabezado, tabs, pie)
        # El redimensionado afecta la tabla de la pantalla de alta.
        self.page.on_resize = self.alta._on_resize
        # Ya con la página construida, se cargan los registros guardados.
        self.alta.cargar_desde_db()

    def _alternar_tema(self, _e) -> None:
        """Cambia entre modo claro y oscuro (y ajusta el logo y el ícono)."""
        oscuro = self.page.theme_mode != ft.ThemeMode.DARK
        self.page.theme_mode = ft.ThemeMode.DARK if oscuro else ft.ThemeMode.LIGHT
        self.logo.src = (
            "Imagenes/Quetzaltic Texto Blanco .png" if oscuro
            else "Imagenes/Quetzaltic Texto negro.png"
        )
        self.btn_tema.icon = ft.Icons.LIGHT_MODE if oscuro else ft.Icons.DARK_MODE
        self.btn_tema.tooltip = "Modo claro" if oscuro else "Modo oscuro"
        self.page.update()


def main(page: ft.Page) -> None:
    page.title = "Herramienta Integral de Tesorería"
    page.padding = 18
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window.width = 1180
    page.window.height = 800
    db.inicializar()

    if not ocr.tesseract_disponible():
        page.show_dialog(
            ft.SnackBar(
                content=ft.Text(
                    "No se encontró el motor Tesseract. Los PDF con texto se leerán igual, "
                    "pero los documentos escaneados no podrán procesarse por OCR."
                ),
                bgcolor=ft.Colors.AMBER_800,
            )
        )

    AppTesoreria(page)


if __name__ == "__main__":
    ft.run(main, assets_dir=rutas.BUNDLE)
