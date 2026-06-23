"""Herramienta Integral de Tesorería — interfaz Flet.

Punto de entrada de la aplicación de escritorio (Flet / Material).

Módulo actual — Alta de beneficiarios:
  - Se cargan uno o varios estados de cuenta (PDF o imagen).
  - Cada archivo se lee (texto del PDF u OCR) y se identifican CLABE,
    beneficiario, alias y email.
  - Cada documento identificado aparece como una fila en la tabla.
  - La revisión y edición se hace directamente en la tabla: las celdas son
    editables y cada fila se guarda/actualiza o se elimina ahí mismo.

La vista usa Tabs (TabBar + TabBarView) pensada para crecer: cada nueva función
de tesorería se agrega como una pestaña adicional.
"""

from __future__ import annotations

import asyncio
import os
import re
from datetime import date

import flet as ft

from core import (
    cuentas_bancarias, db, exportador, exportador_alta_banregio,
    exportador_devoluciones, ocr, reporte_excel,
)
from core.catalogo_bancos import banco_desde_clabe
from core.extractores import extraer_datos, nombre_desde_archivo, validar_clabe

_RE_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_EXTENSIONES = ["pdf", "png", "jpg", "jpeg", "tif", "tiff", "bmp"]

VERDE = ft.Colors.GREEN_700
ROJO = ft.Colors.RED_700
NARANJA = ft.Colors.ORANGE_800
GRIS = ft.Colors.ON_SURFACE_VARIANT

# Anchos de columna (compartidos entre encabezado y celdas para que queden
# perfectamente alineados). Beneficiario/Alias/Email son responsivos.
W_ESTADO = 64
W_CLABE = 200
W_MONTO = 120
W_BANCO = 140
W_ACCIONES = 150
W_NOMBRE = 200
_CENTRO = ft.Alignment(0, 0)


def _celda_centrada(contenido: ft.Control, ancho: int) -> ft.Container:
    return ft.Container(content=contenido, width=ancho, alignment=_CENTRO)


def _encabezado_col(titulo: str, ancho: int) -> ft.Container:
    return ft.Container(
        content=ft.Text(titulo, weight=ft.FontWeight.BOLD, size=13,
                        text_align=ft.TextAlign.CENTER),
        width=ancho, alignment=_CENTRO,
    )


def _solo_digitos(texto: str | None) -> str:
    return re.sub(r"\D", "", texto or "")


def _validar(clabe: str, beneficiario: str, alias: str, email: str) -> str:
    if not validar_clabe(clabe):
        return "La CLABE debe tener 18 dígitos y un dígito de control válido."
    if not beneficiario:
        return "Falta el nombre del beneficiario."
    if not alias:
        return "Falta el alias de la cuenta."
    if email and not _RE_EMAIL.match(email):
        return "El email de notificación no tiene un formato válido."
    return ""


def _parse_monto(texto: str | None) -> float | None:
    """Convierte el texto del monto a número. Vacío -> None. Lanza ValueError
    si no es un número válido o es negativo."""
    s = (texto or "").strip().replace("$", "").replace(",", "").replace(" ", "")
    if not s:
        return None
    valor = float(s)
    if valor < 0:
        raise ValueError("El monto no puede ser negativo.")
    return valor


def _fmt_monto(monto: float | None) -> str:
    return "" if monto is None else f"{monto:,.2f}"


class FilaBeneficiario:
    """Una fila editable de la tabla (un beneficiario, guardado o pendiente)."""

    def __init__(self, app: "AppTesoreria", id_: int | None, clabe: str,
                 beneficiario: str, alias: str, email: str, origen: str = "",
                 monto: float | None = None, ruta_archivo: str | None = None):
        self.app = app
        self.id = id_          # None mientras no se haya guardado en la base
        self.origen = origen   # nombre del archivo de origen (informativo)
        self.ruta_archivo = ruta_archivo  # ruta completa para previsualizar

        self.tf_clabe = ft.TextField(
            value=clabe, dense=True, width=W_CLABE, max_length=18, text_size=12,
            content_padding=8, text_align=ft.TextAlign.CENTER, on_change=self._cambio_clabe,
        )
        self.tf_monto = ft.TextField(
            value=_fmt_monto(monto), dense=True, width=W_MONTO, text_size=12,
            content_padding=8, text_align=ft.TextAlign.RIGHT, hint_text="0.00",
            on_change=self._cambio,
        )
        self.txt_banco = ft.Text(
            banco_desde_clabe(_solo_digitos(clabe)) or "—", size=12,
            text_align=ft.TextAlign.CENTER,
        )
        self.tf_benef = ft.TextField(
            value=beneficiario, dense=True, width=W_NOMBRE, text_size=12,
            content_padding=8, on_change=self._cambio,
        )
        self.tf_alias = ft.TextField(
            value=alias, dense=True, width=W_NOMBRE, text_size=12,
            content_padding=8, on_change=self._cambio,
        )
        self.tf_email = ft.TextField(
            value=email, dense=True, width=W_NOMBRE, text_size=12,
            content_padding=8, on_change=self._cambio,
        )
        self.ico_estado = ft.Icon(ft.Icons.CIRCLE, size=16, color=GRIS)

        self.snapshot = self._valores()
        acciones = ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.VISIBILITY_OUTLINED, tooltip="Ver archivo",
                    icon_color=ft.Colors.BLUE_700, on_click=lambda e: self.previsualizar(),
                ),
                ft.IconButton(
                    icon=ft.Icons.SAVE_OUTLINED, tooltip="Guardar", icon_color=VERDE,
                    on_click=lambda e: self.guardar(),
                ),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE, tooltip="Eliminar", icon_color=ROJO,
                    on_click=lambda e: self.app.eliminar_fila(self),
                ),
            ],
            spacing=0,
            alignment=ft.MainAxisAlignment.CENTER,
        )
        self.fila = ft.DataRow(
            selected=False,
            on_select_change=self._al_seleccionar,
            cells=[
                ft.DataCell(_celda_centrada(self.ico_estado, W_ESTADO)),
                ft.DataCell(self.tf_clabe),
                ft.DataCell(self.tf_monto),
                ft.DataCell(_celda_centrada(self.txt_banco, W_BANCO)),
                ft.DataCell(self.tf_benef),
                ft.DataCell(self.tf_alias),
                ft.DataCell(self.tf_email),
                ft.DataCell(_celda_centrada(acciones, W_ACCIONES)),
            ],
        )
        self._actualizar_estado()

    def _al_seleccionar(self, e) -> None:
        self.fila.selected = str(e.data).lower() == "true"
        self.app.page.update()

    # ------------------------------------------------------------- helpers
    def _valores(self) -> tuple[str, str, str, str, str]:
        return (
            _solo_digitos(self.tf_clabe.value),
            (self.tf_benef.value or "").strip(),
            (self.tf_alias.value or "").strip(),
            (self.tf_email.value or "").strip(),
            (self.tf_monto.value or "").strip(),
        )

    def _cambio_clabe(self, _e) -> None:
        self.txt_banco.value = banco_desde_clabe(_solo_digitos(self.tf_clabe.value)) or "—"
        self._actualizar_estado()
        self.app.page.update()

    def _cambio(self, _e) -> None:
        self._actualizar_estado()
        self.app.page.update()

    def _actualizar_estado(self) -> None:
        clabe = _solo_digitos(self.tf_clabe.value)
        if not validar_clabe(clabe):
            self.ico_estado.icon = ft.Icons.ERROR
            self.ico_estado.color = ROJO
            self.ico_estado.tooltip = "CLABE inválida"
        elif self.id is None:
            self.ico_estado.icon = ft.Icons.RADIO_BUTTON_UNCHECKED
            self.ico_estado.color = NARANJA
            self.ico_estado.tooltip = "Pendiente de guardar"
        elif self._valores() != self.snapshot:
            self.ico_estado.icon = ft.Icons.EDIT
            self.ico_estado.color = NARANJA
            self.ico_estado.tooltip = "Cambios sin guardar"
        else:
            self.ico_estado.icon = ft.Icons.CHECK_CIRCLE
            self.ico_estado.color = VERDE
            self.ico_estado.tooltip = "Guardado"

    @property
    def pendiente(self) -> bool:
        """True si la fila tiene cambios o altas sin persistir."""
        return self.id is None or self._valores() != self.snapshot

    # ------------------------------------------------------------ acciones
    def guardar(self, silencioso: bool = False) -> bool:
        clabe, beneficiario, alias, email, monto_txt = self._valores()
        error = _validar(clabe, beneficiario, alias, email)
        if error:
            if not silencioso:
                self.app.avisar(error, ROJO)
            return False
        try:
            monto = _parse_monto(monto_txt)
        except ValueError:
            if not silencioso:
                self.app.avisar("El monto debe ser un número válido (≥ 0).", ROJO)
            return False
        banco = banco_desde_clabe(clabe)
        try:
            if self.id is None:
                self.id = db.guardar(clabe, beneficiario, alias, email, banco, monto, self.ruta_archivo)
            else:
                db.actualizar(self.id, clabe, beneficiario, alias, email, banco, monto, self.ruta_archivo)
        except db.CLABEDuplicada:
            if not silencioso:
                self.app.avisar("Esa CLABE ya pertenece a otro beneficiario.", ROJO)
            return False
        self.tf_monto.value = _fmt_monto(monto)  # normaliza la presentación
        self.snapshot = self._valores()
        self._actualizar_estado()
        self.app._refrescar_candado_export()
        self.app.page.update()
        if not silencioso:
            self.app.avisar("Beneficiario guardado.", VERDE)
        return True

    def previsualizar(self) -> None:
        """Abre el archivo original del registro en el visor predeterminado del
        sistema, para revisar el documento y corregir lo que haga falta."""
        ruta = self.ruta_archivo
        if not ruta or not os.path.exists(ruta):
            self.app.avisar("No se encontró el archivo original de este registro.", ROJO)
            return
        try:
            os.startfile(ruta)  # Windows: abre en el visor predeterminado
        except Exception as exc:  # noqa: BLE001 — se reporta al usuario
            self.app.avisar(f"No se pudo abrir el archivo: {exc}", ROJO)


# ======================================================================
#  Sección: Generar dispersión de devoluciones
# ======================================================================
class FilaDevolucion:
    """Una fila editable de la tabla de devoluciones (un movimiento)."""

    def __init__(self, seccion: "SeccionDevoluciones"):
        self.seccion = seccion
        self.tf_clabe = ft.TextField(
            dense=True, width=W_CLABE, max_length=18, text_size=12,
            content_padding=8, text_align=ft.TextAlign.CENTER,
        )
        self.tf_monto = ft.TextField(
            dense=True, width=W_MONTO, text_size=12, content_padding=8,
            text_align=ft.TextAlign.RIGHT, hint_text="0.00",
        )
        self.tf_benef = ft.TextField(dense=True, width=W_NOMBRE, text_size=12, content_padding=8)
        self.tf_concepto = ft.TextField(dense=True, width=W_NOMBRE, text_size=12, content_padding=8)
        # Solo el día de la devolución (1-31). Solo se usa en el reporte Excel.
        self.tf_dia = ft.TextField(
            dense=True, width=W_MONTO, max_length=2, text_size=12, content_padding=8,
            text_align=ft.TextAlign.CENTER, hint_text="día",
        )
        self.fila = ft.DataRow(
            cells=[
                ft.DataCell(self.tf_clabe),
                ft.DataCell(self.tf_monto),
                ft.DataCell(self.tf_benef),
                ft.DataCell(self.tf_concepto),
                ft.DataCell(_celda_centrada(self.tf_dia, W_MONTO)),
                ft.DataCell(_celda_centrada(
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE, tooltip="Quitar", icon_color=ROJO,
                        on_click=lambda e: self.seccion.eliminar_fila(self),
                    ),
                    W_ACCIONES,
                )),
            ]
        )

    def valores(self) -> tuple[str, str, str, str, str]:
        return (
            _solo_digitos(self.tf_clabe.value),
            (self.tf_monto.value or "").strip(),
            (self.tf_benef.value or "").strip(),
            (self.tf_concepto.value or "").strip(),
            (self.tf_dia.value or "").strip(),
        )


class SeccionDevoluciones:
    """Pestaña para capturar movimientos y generar el TXT de devoluciones,
    eligiendo el banco (Banregio o Bancomer)."""

    def __init__(self, app: "AppTesoreria"):
        self.app = app
        self.page = app.page
        self.filas: list[FilaDevolucion] = []
        self.catalogo = cuentas_bancarias.CatalogoCuentas()
        self.contenido = self._construir()
        self._agregar_fila()  # arranca con 2 movimientos (mínimo requerido)
        self._agregar_fila()
        # Sin page.update() aquí: la página aún no se ha construido.
        self.tabla.rows = [f.fila for f in self.filas]

    # ------------------------------------------------------------ UI
    def _construir(self) -> ft.Control:
        self.dd_banco = ft.Dropdown(
            label="Banco que dispersa", width=200, value="Banregio",
            options=[
                ft.dropdown.Option(key="Banregio", text="Banregio"),
                ft.dropdown.Option(key="Bancomer", text="Bancomer"),
            ],
            on_select=self._cambio_banco,
        )
        # Empresa que dispersa (de dónde sale el pago).
        self.dd_empresa = ft.Dropdown(
            label="Empresa que dispersa", width=420, enable_filter=True, editable=True,
            options=[ft.dropdown.Option(key=e, text=e) for e in self.catalogo.empresas()],
            on_select=self._actualizar_cuentas,
        )
        # Cuenta origen: se llena sola según empresa + banco (no se escribe).
        self._mapa_num_cuenta: dict[str, str] = {}  # clabe -> número de cuenta
        self.dd_origen = ft.Dropdown(
            label="Cuenta origen (CLABE)", width=300, options=[],
            on_select=self._mostrar_num_cuenta,
        )
        # Número de cuenta (informativo, no editable).
        self.tf_num_cuenta = ft.TextField(
            label="Número de cuenta", width=220, read_only=True,
        )
        # Config Banregio (solo fecha) / Bancomer (solo folio).
        self.tf_fecha = ft.TextField(
            label="Fecha (DDMMAAAA)", width=170, max_length=8,
            value=date.today().strftime("%d%m%Y"),
        )
        self.cfg_banregio = ft.Row([self.tf_fecha])
        self.tf_folio = ft.TextField(label="Folio", width=150, value="0023626H")
        self.cfg_bancomer = ft.Row([self.tf_folio], visible=False)

        nota = ""
        if not self.catalogo.disponible():
            nota = ("⚠ No se pudo leer el Excel de cuentas bancarias. Si lo tienes "
                    "abierto en Excel, ciérralo y reabre la aplicación (después se "
                    "usará la última versión leída aunque esté abierto).")
        config = self.app._tarjeta(
            "1. Banco y datos del archivo",
            ft.Column(
                [
                    ft.Row([self.dd_banco, self.dd_empresa],
                           wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=16),
                    ft.Row([self.dd_origen, self.tf_num_cuenta, self.cfg_banregio, self.cfg_bancomer],
                           wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=16),
                    ft.Text(nota, color=ROJO, size=12, visible=bool(nota)),
                ],
                spacing=12,
            ),
        )

        self.tabla = ft.DataTable(
            columns=[
                ft.DataColumn(label=_encabezado_col("CLABE", W_CLABE)),
                ft.DataColumn(label=_encabezado_col("Monto", W_MONTO), numeric=True),
                ft.DataColumn(label=_encabezado_col("Beneficiario", W_NOMBRE)),
                ft.DataColumn(label=_encabezado_col("Concepto / Referencia", W_NOMBRE)),
                ft.DataColumn(label=_encabezado_col("Fecha devol. (día)", W_MONTO)),
                ft.DataColumn(label=_encabezado_col("", W_ACCIONES)),
            ],
            rows=[],
            column_spacing=14,
            heading_row_color=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            heading_row_height=46,
            data_row_min_height=48,
            data_row_max_height=48,
            divider_thickness=1,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=10,
        )
        tabla = self.app._tarjeta(
            "2. Movimientos",
            ft.Column(
                [
                    ft.Row([
                        ft.OutlinedButton(content="Agregar movimiento", icon=ft.Icons.ADD,
                                          on_click=lambda e: self._agregar_y_redibujar()),
                        ft.FilledButton(content="Generar TXT", icon=ft.Icons.DESCRIPTION_OUTLINED,
                                        on_click=self._generar),
                        ft.OutlinedButton(content="Generar Excel", icon=ft.Icons.TABLE_VIEW,
                                          on_click=self._generar_excel),
                    ], spacing=10, wrap=True),
                    ft.Row([self.tabla], scroll=ft.ScrollMode.AUTO),
                ],
                spacing=12,
            ),
        )
        return ft.Column([config, tabla], spacing=14, scroll=ft.ScrollMode.AUTO, expand=True)

    def _cambio_banco(self, _e) -> None:
        es_banregio = self.dd_banco.value == "Banregio"
        self.cfg_banregio.visible = es_banregio
        self.cfg_bancomer.visible = not es_banregio
        self._actualizar_cuentas()

    def _actualizar_cuentas(self, _e=None) -> None:
        """Llena la cuenta origen (CLABE) y el número de cuenta según la empresa
        y el banco seleccionados."""
        empresa = self.dd_empresa.value
        cuentas = self.catalogo.cuentas(empresa, self.dd_banco.value) if empresa else []
        self.dd_origen.options = [
            ft.dropdown.Option(key=clabe, text=f"{clabe}  ({divisa})")
            for clabe, divisa, _num in cuentas
        ]
        self._mapa_num_cuenta = {clabe: num for clabe, _divisa, num in cuentas}
        # Preselecciona la primera (las PESOS/MXP vienen primero).
        self.dd_origen.value = cuentas[0][0] if cuentas else None
        self._mostrar_num_cuenta()
        self.page.update()

    def _mostrar_num_cuenta(self, _e=None) -> None:
        self.tf_num_cuenta.value = self._mapa_num_cuenta.get(self.dd_origen.value, "")
        self.page.update()

    def _redibujar(self) -> None:
        self.tabla.rows = [f.fila for f in self.filas]
        self.page.update()

    def _agregar_fila(self) -> None:
        self.filas.append(FilaDevolucion(self))

    def _agregar_y_redibujar(self) -> None:
        self._agregar_fila()
        self._redibujar()

    def eliminar_fila(self, fila: FilaDevolucion) -> None:
        self.filas.remove(fila)
        self._redibujar()

    # ------------------------------------------------------- generación
    def _recolectar(self):
        """Valida y devuelve los movimientos como [(clabe, monto, benef,
        concepto, dia), ...]; o None (tras avisar) si hay un dato inválido."""
        registros = []
        for fila in self.filas:
            clabe, monto_txt, benef, concepto, dia = fila.valores()
            if not (clabe or monto_txt or benef or concepto or dia):
                continue  # ignora filas totalmente vacías
            if len(clabe) != 18:
                self.app.avisar("Hay CLABE(s) que no tienen 18 dígitos.", ROJO)
                return None
            try:
                monto = _parse_monto(monto_txt)
            except ValueError:
                self.app.avisar("Hay un monto inválido (usa solo números).", ROJO)
                return None
            if monto is None:
                self.app.avisar("Falta capturar algún monto.", ROJO)
                return None
            registros.append((clabe, monto, benef, concepto, dia))
        # TODO: volver a exigir mínimo 2 movimientos cuando se active el candado.
        if len(registros) < 1:
            self.app.avisar("Captura al menos 1 movimiento válido.", ROJO)
            return None
        return registros

    def _contexto(self) -> dict:
        return {
            "empresa": self.dd_empresa.value or "",
            "banco": self.dd_banco.value or "",
            "cuenta_origen": self.dd_origen.value or "",
            "num_cuenta": self.tf_num_cuenta.value or "",
            "fecha": (self.tf_fecha.value or "") if self.dd_banco.value == "Banregio" else "",
        }

    async def _generar(self, _e) -> None:
        registros = self._recolectar()
        if registros is None:
            return
        if not self.dd_empresa.value:
            self.app.avisar("Elige la empresa que dispersa.", ROJO)
            return
        origen = _solo_digitos(self.dd_origen.value)
        if len(origen) != 18:
            self.app.avisar(
                "No hay cuenta origen para esa empresa y banco. Elige otra empresa "
                "o revisa el Excel de cuentas.", ROJO)
            return

        # El TXT no incluye el día de devolución (solo es para el Excel).
        movimientos = [(c, m, b, co) for c, m, b, co, _dia in registros]
        banco = self.dd_banco.value
        if banco == "Banregio":
            fecha = _solo_digitos(self.tf_fecha.value)
            if len(fecha) != 8:
                self.app.avisar("La fecha debe tener 8 dígitos (DDMMAAAA).", ROJO)
                return
            contenido = exportador_devoluciones.generar_banregio(movimientos, fecha)
            nombre_def = "devolucion_banregio.txt"
        else:
            folio = (self.tf_folio.value or "").strip()
            contenido = exportador_devoluciones.generar_bancomer(movimientos, origen, folio)
            nombre_def = "devolucion_bancomer.txt"

        ruta = await self.app.picker.save_file(
            dialog_title=f"Guardar TXT de devoluciones ({banco})",
            file_name=nombre_def, allowed_extensions=["txt"],
        )
        if not ruta:
            return
        if not ruta.lower().endswith(".txt"):
            ruta += ".txt"
        try:
            with open(ruta, "w", encoding="latin-1", newline="") as fh:
                fh.write(contenido)
        except Exception as exc:  # noqa: BLE001 — se reporta al usuario
            self.app.avisar(f"No se pudo guardar el archivo: {exc}", ROJO)
            return
        self.app.avisar(f"TXT de {banco} generado con {len(movimientos)} movimiento(s).", VERDE)

    async def _generar_excel(self, _e) -> None:
        registros = self._recolectar()
        if registros is None:
            return
        ruta = await self.app.picker.save_file(
            dialog_title="Guardar reporte Excel de devoluciones",
            file_name="reporte_devoluciones.xlsx", allowed_extensions=["xlsx"],
        )
        if not ruta:
            return
        if not ruta.lower().endswith(".xlsx"):
            ruta += ".xlsx"
        try:
            reporte_excel.generar(ruta, self._contexto(), registros)
        except Exception as exc:  # noqa: BLE001 — se reporta al usuario
            self.app.avisar(f"No se pudo generar el Excel: {exc}", ROJO)
            return
        self.app.avisar(f"Reporte Excel generado con {len(registros)} movimiento(s).", VERDE)


class AppTesoreria:
    """Estado y comportamiento de la aplicación de tesorería."""

    def __init__(self, page: ft.Page):
        self.page = page
        self.filas: list[FilaBeneficiario] = []

        self.picker = ft.FilePicker()
        page.services.append(self.picker)

        self._construir()
        self._cargar_desde_db()

    # ===================================================== construcción UI
    def _construir(self) -> None:
        # --- Sección 1: carga de archivos (uno o varios) ---
        self.txt_estado = ft.Text("", color=GRIS, size=12)
        self.anillo = ft.ProgressRing(width=18, height=18, stroke_width=2, visible=False)
        self.btn_cargar = ft.FilledButton(
            content="Seleccionar estados de cuenta",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=self._seleccionar,
        )
        seccion_carga = self._tarjeta(
            "1. Cargar estados de cuenta",
            ft.Column(
                [
                    ft.Row(
                        [
                            self.btn_cargar,
                            self.anillo,
                            ft.Text("Puedes seleccionar varios archivos a la vez.", color=GRIS, size=12, italic=True),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                    ),
                    self.txt_estado,
                ],
                spacing=8,
            ),
        )

        # --- Sección 2: tabla editable con todos los registros ---
        # Encabezados centrados con el mismo ancho que sus celdas. Se guardan
        # referencias de Beneficiario/Alias/Email para ajustarlos al cambiar de
        # tamaño la ventana (igual que sus campos).
        self.enc_benef = _encabezado_col("Beneficiario", W_NOMBRE)
        self.enc_alias = _encabezado_col("Alias", W_NOMBRE)
        self.enc_email = _encabezado_col("Email de notificación", W_NOMBRE)
        self.tabla = ft.DataTable(
            columns=[
                ft.DataColumn(label=_encabezado_col("Estado", W_ESTADO)),
                ft.DataColumn(label=_encabezado_col("CLABE", W_CLABE)),
                ft.DataColumn(label=_encabezado_col("Monto", W_MONTO), numeric=True),
                ft.DataColumn(label=_encabezado_col("Banco", W_BANCO)),
                ft.DataColumn(label=self.enc_benef),
                ft.DataColumn(label=self.enc_alias),
                ft.DataColumn(label=self.enc_email),
                ft.DataColumn(label=_encabezado_col("Acciones", W_ACCIONES)),
            ],
            rows=[],
            show_checkbox_column=True,
            column_spacing=14,
            heading_row_color=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            heading_row_height=46,
            data_row_min_height=48,
            data_row_max_height=48,
            divider_thickness=1,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=10,
            vertical_lines=ft.BorderSide(1, ft.Colors.with_opacity(0.4, ft.Colors.OUTLINE_VARIANT)),
        )
        self.txt_resumen = ft.Text("", color=GRIS, size=12)
        # Formato/banco de exportación: Bancomer -> TXT (dispersión) ;
        # Banregio -> Excel de alta de cuentas.
        self.dd_formato = ft.Dropdown(
            label="Exportar para", width=210, value="Bancomer",
            options=[
                ft.dropdown.Option(key="Bancomer", text="Bancomer (TXT)"),
                ft.dropdown.Option(key="Banregio", text="Banregio (Excel)"),
            ],
            on_select=self._cambio_formato_export,
        )
        self.btn_export = ft.FilledButton(
            content="Exportar TXT (Bancomer)", icon=ft.Icons.DOWNLOAD,
            on_click=self._exportar,
        )
        barra = ft.Row(
            [
                ft.OutlinedButton(
                    content="Seleccionar todos", icon=ft.Icons.CHECKLIST,
                    on_click=self._seleccionar_todos,
                ),
                ft.OutlinedButton(
                    content="Asignar monto", icon=ft.Icons.ATTACH_MONEY,
                    on_click=self._asignar_monto_seleccionados,
                ),
                ft.FilledButton(
                    content="Guardar seleccionados", icon=ft.Icons.SAVE,
                    on_click=self._guardar_seleccionados,
                ),
                ft.OutlinedButton(
                    content="Guardar pendientes", icon=ft.Icons.SAVE_OUTLINED,
                    on_click=self._guardar_pendientes,
                ),
                self.dd_formato,
                self.btn_export,
                ft.OutlinedButton(
                    content="Eliminar seleccionados", icon=ft.Icons.DELETE_SWEEP_OUTLINED,
                    on_click=self._eliminar_seleccionados,
                    style=ft.ButtonStyle(color=ROJO),
                ),
                self.txt_resumen,
            ],
            spacing=10,
            wrap=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        seccion_tabla = self._tarjeta(
            "2. Revisión y edición de beneficiarios",
            ft.Column(
                [
                    barra,
                    self._leyenda(),
                    ft.Row([self.tabla], scroll=ft.ScrollMode.AUTO),
                ],
                spacing=12,
            ),
        )

        contenido_alta = ft.Column(
            [seccion_carga, seccion_tabla],
            spacing=14,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        self.seccion_devoluciones = SeccionDevoluciones(self)
        tabs = ft.Tabs(
            length=2,
            expand=True,
            content=ft.Column(
                [
                    ft.TabBar(
                        tabs=[
                            ft.Tab(label="Alta de beneficiarios", icon=ft.Icons.ACCOUNT_BALANCE),
                            ft.Tab(label="Generar dispersión devoluciones",
                                   icon=ft.Icons.CURRENCY_EXCHANGE),
                        ]
                    ),
                    ft.TabBarView(
                        controls=[contenido_alta, self.seccion_devoluciones.contenido],
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
        self.btn_tema = ft.IconButton(
            icon=ft.Icons.DARK_MODE, tooltip="Modo oscuro", on_click=self._alternar_tema,
        )
        encabezado = ft.Row(
            [self.logo, self.btn_tema],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.page.add(encabezado, tabs)
        self.page.on_resize = self._on_resize

    def _leyenda(self) -> ft.Control:
        """Leyenda de los íconos de la columna Estado (mismos íconos/colores
        que usa cada fila en _actualizar_estado)."""
        items = [
            (ft.Icons.CHECK_CIRCLE, VERDE, "Guardado"),
            (ft.Icons.RADIO_BUTTON_UNCHECKED, NARANJA, "Pendiente de guardar"),
            (ft.Icons.EDIT, NARANJA, "Cambios sin guardar"),
            (ft.Icons.ERROR, ROJO, "CLABE inválida (requiere atención)"),
        ]
        chips = [
            ft.Row(
                [ft.Icon(ico, color=color, size=16), ft.Text(txt, size=12, color=GRIS)],
                spacing=5,
                tight=True,
            )
            for ico, color, txt in items
        ]
        return ft.Row(
            [ft.Text("Leyenda:", size=12, weight=ft.FontWeight.BOLD, color=GRIS), *chips],
            spacing=18,
            wrap=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _tarjeta(self, titulo: str, cuerpo: ft.Control) -> ft.Card:
        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [ft.Text(titulo, weight=ft.FontWeight.BOLD, size=15), cuerpo],
                    spacing=10,
                ),
                padding=16,
            )
        )

    # ========================================================= utilidades
    def avisar(self, mensaje: str, color: str | None = None) -> None:
        self.page.show_dialog(
            ft.SnackBar(content=ft.Text(mensaje, color=ft.Colors.WHITE), bgcolor=color)
        )

    def _redibujar_tabla(self) -> None:
        self.tabla.rows = [f.fila for f in self.filas]
        self._ajustar_anchos()
        self._actualizar_resumen()
        self._refrescar_candado_export()
        self.page.update()

    def _cambio_formato_export(self, _e=None) -> None:
        """Ajusta el botón de exportar según el formato/banco elegido."""
        if self.dd_formato.value == "Banregio":
            self.btn_export.content = "Exportar Excel (Banregio)"
            self.btn_export.icon = ft.Icons.TABLE_VIEW
        else:
            self.btn_export.content = "Exportar TXT (Bancomer)"
            self.btn_export.icon = ft.Icons.DOWNLOAD
        self._refrescar_candado_export()

    def _refrescar_candado_export(self) -> None:
        """Bloquea la exportación si falta un monto. El candado SOLO aplica al
        formato Bancomer (TXT de dispersión); el alta Banregio no usa montos."""
        if self.dd_formato.value == "Banregio":
            self.btn_export.disabled = False
            self.btn_export.tooltip = "Genera el archivo Excel de alta para Banregio"
            self.page.update()
            return
        sin_monto = sum(1 for b in db.listar() if b.monto is None)
        self.btn_export.disabled = sin_monto > 0
        self.btn_export.tooltip = (
            f"Hay {sin_monto} registro(s) guardado(s) sin monto. Captura el monto "
            "y guarda para poder exportar."
            if sin_monto else "Genera el archivo TXT de dispersión"
        )
        self.page.update()

    def _ajustar_anchos(self) -> None:
        """Reparte el ancho disponible entre los campos de texto largos
        (beneficiario, alias, email) para que crezcan al agrandar la ventana."""
        ancho = self.page.width or 1180
        # Columnas de ancho fijo: estado, CLABE, monto, banco, acciones.
        fijo = W_ESTADO + W_CLABE + W_MONTO + W_BANCO + W_ACCIONES
        overhead = 170  # paddings de la tarjeta y espaciamiento entre columnas
        disponible = ancho - fijo - overhead
        w = max(W_NOMBRE, int(disponible / 3))
        for f in self.filas:
            f.tf_benef.width = w
            f.tf_alias.width = w
            f.tf_email.width = w
        # Los encabezados acompañan el ancho de sus columnas.
        self.enc_benef.width = w
        self.enc_alias.width = w
        self.enc_email.width = w

    def _on_resize(self, _e) -> None:
        self._ajustar_anchos()
        self.page.update()

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

    def _actualizar_resumen(self) -> None:
        total = len(self.filas)
        pendientes = sum(1 for f in self.filas if f.pendiente)
        self.txt_resumen.value = (
            f"{total} registro(s) · {pendientes} pendiente(s) de guardar"
            if total else "Sin registros todavía."
        )

    # ============================================================ datos DB
    def _cargar_desde_db(self) -> None:
        for b in db.listar():
            self.filas.append(
                FilaBeneficiario(self, b.id, b.clabe, b.beneficiario, b.alias,
                                 b.email or "", monto=b.monto, ruta_archivo=b.ruta_archivo)
            )
        self._redibujar_tabla()

    # ======================================================= carga archivos
    async def _seleccionar(self, _e) -> None:
        archivos = await self.picker.pick_files(
            dialog_title="Selecciona uno o varios estados de cuenta",
            allowed_extensions=_EXTENSIONES,
            allow_multiple=True,
        )
        if not archivos:
            return

        self.btn_cargar.disabled = True
        self.anillo.visible = True
        identificados = 0
        errores: list[str] = []

        for i, archivo in enumerate(archivos, start=1):
            nombre = os.path.basename(archivo.path)
            self.txt_estado.value = f"Procesando {i}/{len(archivos)}: {nombre}…"
            self.page.update()
            try:
                texto, uso_ocr = await asyncio.to_thread(ocr.extraer_texto, archivo.path)
                datos = extraer_datos(texto)
                # Si la capa de texto no dio nada útil (p. ej. impresión de un
                # correo de Outlook con el estado como imagen), forzar OCR.
                if not datos.clabe and not datos.beneficiario and not uso_ocr:
                    texto, _ = await asyncio.to_thread(ocr.extraer_texto, archivo.path, True)
                    datos = extraer_datos(texto)
                # El nombre del archivo (si parece nombre de persona) es la
                # fuente más confiable del beneficiario; tiene prioridad sobre
                # el OCR. Si no, se usa lo identificado en el documento.
                beneficiario = nombre_desde_archivo(nombre) or datos.beneficiario
                self.filas.append(
                    FilaBeneficiario(
                        self, None, datos.clabe, beneficiario, beneficiario,
                        datos.email, origen=nombre, ruta_archivo=archivo.path,
                    )
                )
                identificados += 1
                self._redibujar_tabla()
            except Exception as exc:  # noqa: BLE001 — se reporta al usuario
                errores.append(f"{nombre}: {exc}")

        self.btn_cargar.disabled = False
        self.anillo.visible = False
        resumen = f"{identificados} de {len(archivos)} archivo(s) identificado(s) y agregado(s) a la tabla."
        if errores:
            resumen += " Con error: " + "; ".join(errores)
        self.txt_estado.value = resumen
        self._actualizar_resumen()
        self.page.update()

    # =========================================================== acciones
    def _seleccionar_todos(self, _e) -> None:
        """Selecciona todas las filas; si ya estaban todas, las deselecciona."""
        if not self.filas:
            return
        nuevo = not all(f.fila.selected for f in self.filas)
        for f in self.filas:
            f.fila.selected = nuevo
        self.page.update()

    def _asignar_monto_seleccionados(self, _e) -> None:
        """Aplica un mismo monto a todas las filas seleccionadas, para no
        capturarlo uno por uno."""
        seleccionados = [f for f in self.filas if f.fila.selected]
        if not seleccionados:
            self.avisar("No hay registros seleccionados (marca las casillas).", GRIS)
            return

        tf = ft.TextField(
            label="Monto", hint_text="0.00", autofocus=True,
            text_align=ft.TextAlign.RIGHT, prefix_icon=ft.Icons.ATTACH_MONEY,
        )

        def aplicar(_ev):
            try:
                monto = _parse_monto(tf.value)
            except ValueError:
                self.avisar("Monto inválido. Usa solo números (ej. 1500.00).", ROJO)
                return
            if monto is None:
                self.avisar("Captura un monto.", ROJO)
                return
            for fila in seleccionados:
                fila.tf_monto.value = _fmt_monto(monto)
                fila._actualizar_estado()  # queda como cambio pendiente de guardar
            self.page.pop_dialog()
            self.page.update()
            self.avisar(
                f"Monto asignado a {len(seleccionados)} registro(s). "
                "Usa 'Guardar seleccionados' para aplicarlo.",
                VERDE,
            )

        self.page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text(f"Asignar monto a {len(seleccionados)} seleccionado(s)"),
                content=ft.Container(content=tf, width=300),
                actions=[
                    ft.TextButton(content="Cancelar", on_click=lambda e: self.page.pop_dialog()),
                    ft.FilledButton(content="Aplicar", on_click=aplicar),
                ],
            )
        )

    def _guardar_varias(self, filas, etiqueta_vacia: str) -> None:
        if not filas:
            self.avisar(etiqueta_vacia, GRIS)
            return
        guardados = sum(1 for f in filas if f.guardar(silencioso=True))
        fallidos = len(filas) - guardados
        self._actualizar_resumen()
        self._refrescar_candado_export()
        self.page.update()
        if fallidos:
            self.avisar(
                f"{guardados} guardado(s). {fallidos} con datos inválidos o CLABE "
                "duplicada (revisa las filas en rojo/naranja).",
                NARANJA,
            )
        else:
            self.avisar(f"{guardados} beneficiario(s) guardado(s).", VERDE)

    def _guardar_seleccionados(self, _e) -> None:
        self._guardar_varias(
            [f for f in self.filas if f.fila.selected],
            "No hay registros seleccionados (marca las casillas o usa 'Seleccionar todos').",
        )

    def _guardar_pendientes(self, _e) -> None:
        self._guardar_varias(
            [f for f in self.filas if f.pendiente],
            "No hay registros pendientes de guardar.",
        )

    async def _exportar(self, _e) -> None:
        """Exporta los registros guardados en el formato del banco elegido:
        Bancomer -> TXT de dispersión ; Banregio -> Excel de alta de cuentas."""
        guardados = db.listar()
        if not guardados:
            self.avisar("No hay registros guardados para exportar.", ROJO)
            return

        if self.dd_formato.value == "Banregio":
            await self._exportar_alta_banregio(guardados)
        else:
            await self._exportar_dispersion_bancomer(guardados)

    async def _exportar_dispersion_bancomer(self, guardados) -> None:
        # Candado: no se exporta si algún registro guardado no tiene monto.
        sin_monto = sum(1 for b in guardados if b.monto is None)
        if sin_monto:
            self.avisar(
                f"No se puede exportar: {sin_monto} registro(s) guardado(s) sin monto. "
                "Captura el monto y guárdalo.",
                ROJO,
            )
            return
        registros = [
            (b.clabe, b.monto, b.beneficiario, b.alias)
            for b in guardados
            if validar_clabe(b.clabe)
        ]
        ruta = await self.picker.save_file(
            dialog_title="Guardar archivo de dispersión TXT (Bancomer)",
            file_name="dispersion.txt", allowed_extensions=["txt"],
        )
        if not ruta:
            return
        if not ruta.lower().endswith(".txt"):
            ruta += ".txt"
        try:
            contenido = exportador.generar_txt(registros)
            with open(ruta, "w", encoding="latin-1", newline="") as fh:
                fh.write(contenido)
        except Exception as exc:  # noqa: BLE001 — se reporta al usuario
            self.avisar(f"No se pudo guardar el archivo: {exc}", ROJO)
            return
        self.avisar(f"TXT generado con {len(registros)} registro(s) guardado(s).", VERDE)

    async def _exportar_alta_banregio(self, guardados) -> None:
        registros = [
            (b.clabe, b.beneficiario, b.email or "")
            for b in guardados
            if validar_clabe(b.clabe)
        ]
        if not registros:
            self.avisar("No hay registros con CLABE válida para exportar.", ROJO)
            return
        ruta = await self.picker.save_file(
            dialog_title="Guardar archivo de alta (Banregio)",
            file_name="alta_banregio.xls", allowed_extensions=["xls"],
        )
        if not ruta:
            return
        if not ruta.lower().endswith(".xls"):
            ruta += ".xls"
        try:
            exportador_alta_banregio.generar(ruta, registros)
        except Exception as exc:  # noqa: BLE001 — se reporta al usuario
            self.avisar(f"No se pudo guardar el archivo: {exc}", ROJO)
            return
        self.avisar(f"Excel de alta (Banregio) generado con {len(registros)} registro(s).", VERDE)

    def _eliminar_seleccionados(self, _e) -> None:
        """Elimina todas las filas seleccionadas (con confirmación)."""
        seleccionados = [f for f in self.filas if f.fila.selected]
        if not seleccionados:
            self.avisar("No hay registros seleccionados (marca las casillas).", GRIS)
            return

        def confirmar(_ev):
            for fila in seleccionados:
                if fila.id is not None:
                    db.eliminar(fila.id)
                self.filas.remove(fila)
            self.page.pop_dialog()
            self._redibujar_tabla()  # refresca resumen y candado de exportación
            self.avisar(f"{len(seleccionados)} registro(s) eliminado(s).", GRIS)

        self.page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Confirmar eliminación"),
                content=ft.Text(
                    f"¿Eliminar {len(seleccionados)} registro(s) seleccionado(s)? "
                    "Esta acción no se puede deshacer."
                ),
                actions=[
                    ft.TextButton(content="Cancelar", on_click=lambda e: self.page.pop_dialog()),
                    ft.FilledButton(content="Eliminar", on_click=confirmar,
                                    color=ft.Colors.WHITE, bgcolor=ROJO),
                ],
            )
        )

    def eliminar_fila(self, fila: FilaBeneficiario) -> None:
        def confirmar(_e):
            if fila.id is not None:
                db.eliminar(fila.id)
            self.filas.remove(fila)
            self.page.pop_dialog()
            self._redibujar_tabla()
            self.avisar("Registro eliminado.", GRIS)

        # Si la fila aún no se guarda, se quita directo sin confirmar.
        if fila.id is None:
            self.filas.remove(fila)
            self._redibujar_tabla()
            return

        self.page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Confirmar eliminación"),
                content=ft.Text("¿Eliminar este beneficiario de la base? Esta acción no se puede deshacer."),
                actions=[
                    ft.TextButton(content="Cancelar", on_click=lambda e: self.page.pop_dialog()),
                    ft.FilledButton(content="Eliminar", on_click=confirmar, color=ft.Colors.WHITE, bgcolor=ROJO),
                ],
            )
        )


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
    ft.run(main, assets_dir=os.path.dirname(os.path.abspath(__file__)))
