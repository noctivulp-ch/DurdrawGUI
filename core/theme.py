"""Sistema de temas de la aplicación — tres modos: sistema, oscuro, claro."""

from __future__ import annotations
import os
from pathlib import Path
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication
import core.log as log

_QT6CT_CONF = Path.home() / ".config" / "qt6ct" / "qt6ct.conf"

_log = log.get("theme")

SYSTEM = "system"
DARK   = "dark"
LIGHT  = "light"

NAMES: dict[str, str] = {SYSTEM: "Sistema", DARK: "Oscuro", LIGHT: "Claro"}

# ── Paletas de tokens ──────────────────────────────────────────────────────────

_DARK: dict[str, str] = {
    # Superficies — cinco niveles de elevación, del más profundo al más elevado
    "bg_deep":   "#0e0e10",   # profundo: fondo de scroll, track de scrollbar
    "bg_base":   "#16161a",   # ventana principal
    "bg_panel":  "#1d1d22",   # panels, sidebar, menubar, statusbar
    "bg_widget": "#242429",   # inputs, listas, tablas
    "bg_select": "#35291a",   # selección — ámbar oscuro
    # Texto
    "fg_base":   "#dedad4",   # texto principal — ligeramente cálido
    "fg_dim":    "#5e5c66",   # etiquetas, texto secundario
    "fg_accent": "#c09050",   # ámbar — acento principal
    # Controles
    "border":    "#27272d",   # separadores y bordes de widget
    "btn_bg":    "#26262c",   # botón en reposo — casi igual al panel
    "btn_hover": "#32323a",   # botón hover
    "btn_check": "#35291a",   # botón checked/activo
    # Canvas
    "canvas_bg": "#1d1d22",   # área fuera del documento (igual al panel)
}

_LIGHT: dict[str, str] = {
    # Superficies
    "bg_deep":   "#d8d5ce",   # profundo — inputs/listas
    "bg_base":   "#f0ede8",   # ventana principal — papel cálido
    "bg_panel":  "#e6e3dc",   # panels, sidebar, bars
    "bg_widget": "#dedad3",   # inputs y listas
    "bg_select": "#e8d8a0",   # selección ámbar claro
    # Texto
    "fg_base":   "#1e1b16",   # casi negro cálido
    "fg_dim":    "#7a7870",   # etiquetas secundarias
    "fg_accent": "#7a5530",   # ámbar para luz
    # Controles
    "border":    "#cac7c0",   # borde suave
    "btn_bg":    "#e0ddd6",   # botón
    "btn_hover": "#d4d1ca",   # hover
    "btn_check": "#e8d8a0",   # checked
    # Canvas
    "canvas_bg": "#cac7c0",   # área fuera del documento
}


def _tokens_from_palette(palette: QPalette) -> dict[str, str]:
    """
    Deriva tokens de diseño desde la paleta Qt activa (qt6ct / sistema).

    Estrategia central — desaturar las superficies:
    Los colores de sistema (Window, Button) pueden ser muy saturados (ej: teal
    #0d2c37). Usarlos directamente como fondos del chrome produce una UI
    "chillona" dominada por ese color. En su lugar los desaturamos ≈65% hacia
    su gris perceptual equivalente, dejando solo un tinte sutil del hue.
    El acento (Highlight) se preserva vivaz y se usa SOLO en detalles pequeños
    (indicadores de tab, focus ring, checked) — nunca en fondos.

    Resultado: misma sobriedad y armonía que los presets Oscuro/Claro, pero
    con el matiz de color del sistema del usuario en lugar de gris puro.

    Roles de QPalette: Window, Base, Button, WindowText, Highlight.
    """
    def _c(role: QPalette.ColorRole) -> str:
        return palette.color(QPalette.ColorGroup.Normal, role).name()

    def _lum(h: str) -> float:
        r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def _off(h: str, n: int) -> str:
        r = max(0, min(255, int(h[1:3], 16) + n))
        g = max(0, min(255, int(h[3:5], 16) + n))
        b = max(0, min(255, int(h[5:7], 16) + n))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _mix(a: str, b: str, t: float) -> str:
        ar, ag, ab = int(a[1:3], 16), int(a[3:5], 16), int(a[5:7], 16)
        br, bg, bb = int(b[1:3], 16), int(b[3:5], 16), int(b[5:7], 16)
        return (f"#{int(ar + (br - ar) * t):02x}"
                f"{int(ag + (bg - ag) * t):02x}"
                f"{int(ab + (bb - ab) * t):02x}")

    def _desat(h: str, amount: float) -> str:
        """Mezcla h con su equivalente en escala de grises. amount=1.0 → gris puro."""
        r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
        gray = int(0.2126 * r + 0.7152 * g + 0.0722 * b)
        return (f"#{max(0, min(255, int(r + (gray - r) * amount))):02x}"
                f"{max(0, min(255, int(g + (gray - g) * amount))):02x}"
                f"{max(0, min(255, int(b + (gray - b) * amount))):02x}")

    window = _c(QPalette.ColorRole.Window)
    base   = _c(QPalette.ColorRole.Base)
    button = _c(QPalette.ColorRole.Button)
    text   = _c(QPalette.ColorRole.WindowText)
    accent = _c(QPalette.ColorRole.Highlight)

    is_dark = _lum(window) < 128
    d       = 1 if is_dark else -1

    # Superficies desaturadas — conservan el hue pero como tinte, no color dominante.
    # Ej: teal #0d2c37 → #1d282c (dark neutral con apenas una nota fría)
    # Ej: teal #31505b → #414c50 (dark blue-gray neutral, no teal saturado)
    win_n  = _desat(window, 0.65)
    btn_n  = _desat(button, 0.65)

    spread = abs(_lum(btn_n) - _lum(win_n))

    # Panel: barely perceptible sobre el window neutral
    panel  = _off(win_n, d * max(8, int(spread * 0.22)))

    # Borde: visible pero sutil entre win_n y btn_n
    border = _mix(win_n, btn_n, 0.40)

    # Hover: un paso por encima del botón neutral
    hover  = _off(btn_n, d * max(8, int(spread * 0.20)))

    # Canvas: área del documento — diferencia mínima del win_n
    canvas = _off(win_n, d * max(5, int(spread * 0.14)))

    # Widget (QListWidget, QTableWidget, inputs elevados): superficie entre panel y btn_n.
    # En el preset Dark bg_widget está por ENCIMA de bg_panel — misma lógica aquí.
    # No usar base (negro puro de pywal) que hundiría el panel de capas.
    widget = _mix(win_n, btn_n, 0.55)

    # Dim text: atenuado hacia win_n, guarda hue del texto
    dim    = _mix(text, win_n, 0.52)

    # Selección: accent vivaz en fondos neutrales (40% accent, 60% base)
    sel_bg = _mix(accent, win_n, 0.60)

    _log.debug(
        f"tokens_from_palette  dark={is_dark}"
        f"  window={window}→{win_n}  button={button}→{btn_n}"
        f"  spread={spread:.0f}  panel={panel}  widget={widget}  accent={accent}"
    )

    return {
        "bg_deep":   base,
        "bg_base":   win_n,
        "bg_panel":  panel,
        "bg_widget": widget,
        "bg_select": sel_bg,
        "fg_base":   text,
        "fg_dim":    dim,
        "fg_accent": accent,
        "border":    border,
        "btn_bg":    btn_n,
        "btn_hover": hover,
        "btn_check": sel_bg,
        "canvas_bg": canvas,
    }


def _build_qss(t: dict[str, str]) -> str:
    return f"""
/* ── Base ─────────────────────────────────────────────────────────────────── */
QMainWindow, QDialog, QWidget {{
    background-color: {t['bg_base']};
    color: {t['fg_base']};
    font-size: 12px;
}}

/* ── Menu bar ─────────────────────────────────────────────────────────────── */
QMenuBar {{
    background-color: {t['bg_panel']};
    color: {t['fg_base']};
    border-bottom: 1px solid {t['border']};
    padding: 0 2px;
    spacing: 0;
}}
QMenuBar::item {{
    padding: 5px 10px;
    background: transparent;
    border-radius: 2px;
}}
QMenuBar::item:selected, QMenuBar::item:pressed {{
    background-color: {t['btn_hover']};
}}

/* ── Menus ────────────────────────────────────────────────────────────────── */
QMenu {{
    background-color: {t['bg_panel']};
    color: {t['fg_base']};
    border: 1px solid {t['border']};
    padding: 3px 2px;
}}
QMenu::item {{
    padding: 5px 28px 5px 14px;
    border-radius: 2px;
}}
QMenu::item:selected {{
    background-color: {t['btn_hover']};
}}
QMenu::item:disabled {{
    color: {t['fg_dim']};
}}
QMenu::separator {{
    height: 1px;
    background-color: {t['border']};
    margin: 3px 8px;
}}

/* ── Status bar ───────────────────────────────────────────────────────────── */
QStatusBar {{
    background-color: {t['bg_panel']};
    color: {t['fg_dim']};
    border-top: 1px solid {t['border']};
    font-size: 11px;
}}
QStatusBar::item {{ border: none; }}

/* ── Splitter ─────────────────────────────────────────────────────────────── */
QSplitter::handle {{
    background-color: {t['border']};
}}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical   {{ height: 1px; }}

/* ── Buttons ──────────────────────────────────────────────────────────────── */
QPushButton {{
    background-color: {t['btn_bg']};
    color: {t['fg_base']};
    border: 1px solid {t['border']};
    padding: 4px 10px;
    border-radius: 3px;
    min-height: 20px;
}}
QPushButton:hover {{
    background-color: {t['btn_hover']};
    border-color: {t['fg_dim']};
}}
QPushButton:pressed {{
    background-color: {t['bg_select']};
}}
QPushButton:checked {{
    background-color: {t['btn_check']};
    border-color: {t['fg_accent']};
    color: {t['fg_accent']};
}}
QPushButton:disabled {{
    color: {t['fg_dim']};
    background-color: {t['bg_base']};
    border-color: {t['border']};
}}
QPushButton:flat {{
    border: none;
    background: transparent;
    border-radius: 3px;
}}
QPushButton:flat:hover {{
    background-color: {t['btn_hover']};
}}

/* ── Tool buttons ─────────────────────────────────────────────────────────── */
QToolButton {{
    background-color: transparent;
    color: {t['fg_base']};
    border: 1px solid transparent;
    padding: 4px;
    border-radius: 3px;
}}
QToolButton:hover {{
    background-color: {t['btn_hover']};
    border-color: {t['border']};
}}
QToolButton:pressed, QToolButton:checked {{
    background-color: {t['bg_select']};
    border-color: {t['fg_accent']};
    color: {t['fg_accent']};
}}

/* ── GroupBox ─────────────────────────────────────────────────────────────── */
QGroupBox {{
    color: {t['fg_dim']};
    border: 1px solid {t['border']};
    border-radius: 3px;
    margin-top: 18px;
    padding: 6px 6px 6px 6px;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    background-color: {t['bg_base']};
}}

/* ── Lists ────────────────────────────────────────────────────────────────── */
QListWidget {{
    background-color: {t['bg_widget']};
    color: {t['fg_base']};
    border: 1px solid {t['border']};
    border-radius: 3px;
    outline: none;
    alternate-background-color: transparent;
}}
QListWidget::item {{
    padding: 4px 6px;
    border-radius: 2px;
}}
QListWidget::item:selected {{
    background-color: {t['bg_select']};
    color: {t['fg_base']};
}}
QListWidget::item:hover:!selected {{
    background-color: {t['btn_hover']};
}}

/* ── Tables ───────────────────────────────────────────────────────────────── */
QTableWidget {{
    background-color: {t['bg_widget']};
    color: {t['fg_base']};
    gridline-color: {t['border']};
    border: 1px solid {t['border']};
    border-radius: 3px;
    outline: none;
    alternate-background-color: {t['bg_base']};
}}
QTableWidget::item:selected {{
    background-color: {t['bg_select']};
    color: {t['fg_base']};
}}
QTableCornerButton::section {{
    background-color: {t['bg_panel']};
    border: none;
    border-right: 1px solid {t['border']};
    border-bottom: 1px solid {t['border']};
}}
QHeaderView::section {{
    background-color: {t['bg_panel']};
    color: {t['fg_dim']};
    border: none;
    border-right: 1px solid {t['border']};
    border-bottom: 1px solid {t['border']};
    padding: 4px 8px;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

/* ── Radio / Checkbox ─────────────────────────────────────────────────────── */
QRadioButton, QCheckBox {{
    color: {t['fg_base']};
    spacing: 7px;
    background: transparent;
}}
QRadioButton::indicator {{
    width: 13px;
    height: 13px;
    border-radius: 7px;
    border: 1px solid {t['fg_dim']};
    background-color: {t['bg_widget']};
}}
QRadioButton::indicator:checked {{
    background-color: {t['fg_accent']};
    border-color: {t['fg_accent']};
}}
QCheckBox::indicator {{
    width: 13px;
    height: 13px;
    border: 1px solid {t['fg_dim']};
    border-radius: 2px;
    background-color: {t['bg_widget']};
}}
QCheckBox::indicator:checked {{
    background-color: {t['fg_accent']};
    border-color: {t['fg_accent']};
}}

/* ── Scrollbars ───────────────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 7px;
    border: none;
    margin: 2px 0;
}}
QScrollBar::handle:vertical {{
    background: {t['btn_hover']};
    min-height: 28px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{
    background: {t['fg_dim']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 7px;
    border: none;
    margin: 0 2px;
}}
QScrollBar::handle:horizontal {{
    background: {t['btn_hover']};
    min-width: 28px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {t['fg_dim']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Tabs ─────────────────────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {t['border']};
    background-color: {t['bg_base']};
    border-radius: 0 0 3px 3px;
}}
QTabBar {{
    background: transparent;
    border-bottom: 1px solid {t['border']};
}}
QTabBar::tab {{
    background: transparent;
    color: {t['fg_dim']};
    padding: 5px 14px 4px 14px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-right: 1px;
}}
QTabBar::tab:selected {{
    color: {t['fg_base']};
    border-bottom: 2px solid {t['fg_accent']};
}}
QTabBar::tab:hover:!selected {{
    color: {t['fg_base']};
    background-color: {t['btn_hover']};
    border-radius: 2px 2px 0 0;
}}

/* ── ComboBox ─────────────────────────────────────────────────────────────── */
QComboBox {{
    background-color: {t['bg_widget']};
    color: {t['fg_base']};
    border: 1px solid {t['border']};
    padding: 3px 8px;
    border-radius: 3px;
    min-height: 20px;
}}
QComboBox:hover {{ border-color: {t['fg_dim']}; }}
QComboBox:focus {{ border-color: {t['fg_accent']}; }}
QComboBox::drop-down {{
    border: none;
    width: 20px;
    subcontrol-position: right center;
}}
QComboBox::down-arrow {{
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {t['fg_dim']};
    width: 0; height: 0;
}}
QComboBox QAbstractItemView {{
    background-color: {t['bg_panel']};
    color: {t['fg_base']};
    border: 1px solid {t['border']};
    selection-background-color: {t['bg_select']};
    selection-color: {t['fg_base']};
    outline: none;
    padding: 2px;
}}

/* ── Inputs ───────────────────────────────────────────────────────────────── */
QSpinBox, QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {t['bg_widget']};
    color: {t['fg_base']};
    border: 1px solid {t['border']};
    padding: 3px 6px;
    border-radius: 3px;
    selection-background-color: {t['bg_select']};
    min-height: 20px;
}}
QSpinBox:focus, QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {t['fg_accent']};
    outline: none;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background-color: {t['btn_bg']};
    border: none;
    border-left: 1px solid {t['border']};
    width: 16px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background-color: {t['btn_hover']};
}}

/* ── Slider ───────────────────────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    background: {t['border']};
    height: 2px;
    border-radius: 1px;
}}
QSlider::handle:horizontal {{
    background: {t['fg_accent']};
    width: 12px;
    height: 12px;
    border-radius: 6px;
    margin: -5px 0;
}}
QSlider::handle:horizontal:hover {{
    background: {t['fg_base']};
}}
QSlider::sub-page:horizontal {{
    background: {t['fg_accent']};
    height: 2px;
    border-radius: 1px;
}}

/* ── Labels ───────────────────────────────────────────────────────────────── */
QLabel {{
    color: {t['fg_base']};
    background: transparent;
}}

/* ── Dialogs ──────────────────────────────────────────────────────────────── */
QDialogButtonBox QPushButton {{ min-width: 80px; }}

/* ── Tooltips ─────────────────────────────────────────────────────────────── */
QToolTip {{
    background-color: {t['bg_panel']};
    color: {t['fg_base']};
    border: 1px solid {t['border']};
    padding: 4px 8px;
    border-radius: 3px;
}}

/* ── Font combo ───────────────────────────────────────────────────────────── */
QFontComboBox {{
    background-color: {t['bg_widget']};
    color: {t['fg_base']};
    border: 1px solid {t['border']};
    padding: 3px 6px;
    border-radius: 3px;
    min-height: 20px;
}}
QFontComboBox:focus {{ border-color: {t['fg_accent']}; }}
"""


class ThemeService:
    def __init__(self, config, bus):
        self._config  = config
        self._bus     = bus
        self._current = config.get("theme", DARK)
        app = QApplication.instance()
        self._orig_style: str = app.style().name() if app else "fusion"
        # Capturar la paleta del sistema ANTES de cualquier setStyle.
        # Una vez que cambiamos a Fusion se pierde la paleta de qt6ct.
        self._sys_palette = app.palette() if app else None
        self._sys_tokens:  dict[str, str] | None = None
        platform_theme = os.environ.get("QT_QPA_PLATFORMTHEME", "")
        _log.info(
            f"ThemeService init  tema={self._current}"
            f"  estilo_qt={self._orig_style}"
            f"  QT_QPA_PLATFORMTHEME={platform_theme or '<no definido>'}"
            f"  QT_QPA_PLATFORM={os.environ.get('QT_QPA_PLATFORM', '<no definido>')}"
        )
        if self._current == SYSTEM:
            if not _QT6CT_CONF.exists():
                _log.warning(
                    f"Tema Qt personal no encontrado: {_QT6CT_CONF}"
                    f" — usando Fusion como respaldo"
                )
            elif platform_theme != "qt6ct":
                _log.warning(
                    f"Configuración qt6ct encontrada en {_QT6CT_CONF}"
                    f" pero QT_QPA_PLATFORMTHEME='{platform_theme}'"
                    f" — el tema del sistema no se aplicará"
                )

    @property
    def current(self) -> str:
        return self._current

    def canvas_bg_color(self) -> str:
        if self._current == DARK:
            return _DARK["canvas_bg"]
        if self._current == LIGHT:
            return _LIGHT["canvas_bg"]
        # Sistema: usar canvas_bg derivado de los tokens del sistema
        if self._sys_tokens:
            return self._sys_tokens["canvas_bg"]
        app = QApplication.instance()
        if app:
            return app.palette().color(QPalette.ColorRole.Window).name()
        return ""

    def apply(self, name: str):
        app = QApplication.instance()
        _log.info(f"apply  {self._current} → {name}")

        if name == DARK:
            app.setStyle("Fusion")
            app.setStyleSheet(_build_qss(_DARK))
            self._sys_tokens = None
            _log.debug("apply dark: Fusion + QSS oscuro")
        elif name == LIGHT:
            app.setStyle("Fusion")
            app.setStyleSheet(_build_qss(_LIGHT))
            self._sys_tokens = None
            _log.debug("apply light: Fusion + QSS claro")
        else:
            # Sistema: restaurar el estilo original (qt6ct) y aplicar encima
            # nuestro lenguaje visual con los colores que qt6ct provee.
            # La paleta fue capturada al init, antes de que Fusion la pisara.
            app.setStyle(self._orig_style)
            palette = self._sys_palette or app.palette()
            self._sys_tokens = _tokens_from_palette(palette)
            app.setStyleSheet(_build_qss(self._sys_tokens))
            _log.info(
                f"apply system: '{self._orig_style}' + QSS dinámico"
                f"  base={self._sys_tokens['bg_base']}"
                f"  accent={self._sys_tokens['fg_accent']}"
            )

        self._current = name
        self._config.set("theme", name)
        self._bus.emit("theme_changed", name)

    def apply_current(self):
        self.apply(self._current)
