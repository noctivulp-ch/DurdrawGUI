"""
Sistema de pinceles para DurdrawGUI.

Dos formatos de pincel de usuario, ambos en ~/.config/durdrawgui/brushes/:

── .json — pincel estático ────────────────────────────────────────────────
  {
    "version": 1,
    "name":        "Nombre del pincel",
    "description": "Descripción opcional",
    "author":      "Autor opcional",
    "cells":       [[-1, -1], [-1, 0], [0, 0]]   <- offsets [dr, dc] desde centro
  }

── .py — pincel con lógica (SmartBrush) ───────────────────────────────────
El archivo debe definir EXACTAMENTE una subclase de SmartBrush. Se instancia
sin argumentos y su método paint(ctx) decide, celda por celda, qué estampar
— con acceso de lectura al lienzo alrededor del cursor vía BrushContext.
Ejemplo mínimo (pinta solo si la celda está vacía, para no pisar dibujo
existente):

    from core.brush import SmartBrush

    class NoOverwrite(SmartBrush):
        name        = "No pisar"
        description = "Pinta solo sobre celdas vacías"
        author      = "vos"

        def paint(self, ctx):
            if ctx.is_empty():
                return [(0, 0, None, None, None)]
            return []

paint() devuelve una lista de (dr, dc, ch, fg, bg) relativos al cursor;
ch/fg/bg en None usan el carácter/color activos (ctx.fg_char/fg_color/bg_color).

BrushContext también da: neighbors4/8, count_neighbors (autómata celular),
scan (leer un bloque rectangular para analizar un patrón), flood_region/
is_interior (detectar si un hueco vacío está encerrado o abierto al exterior).
Nada impide usar el resto de la stdlib desde el script (random para spray,
etc.) — no hay restricciones, ver la nota de seguridad más abajo.

Ver brush_examples/ en la raíz del repo — 5 pinceles de ejemplo (bordes,
interior/exterior, spray, patrón, crecimiento) con README de referencia
completa de BrushContext.

── Seguridad — leer antes de usar pinceles .py de terceros ────────────────
Un pincel .py se carga con `exec` de módulo completo: corre con los mismos
privilegios que el resto de la aplicación (sin sandbox, acceso total a
disco/red/proceso). No hay aislamiento real posible en Python puro sin
infraestructura pesada (subproceso con jail de SO o WASM), así que no se
intenta fingir una — sería peor que no tener ninguna. Tratalo como cualquier
plugin de Blender/Krita: usá solo scripts propios o de fuentes en las que
confiés, bajo tu propio criterio. Los documentos (.dur/.durg) NUNCA
referencian ni auto-cargan un script de pincel — la selección de pincel es
estado local de la UI, así que abrir un archivo ajeno no ejecuta código.
"""

import importlib.util
import inspect
import json
import os
import shutil
from abc import ABC, abstractmethod
from collections import deque

import core.log as log

_log = log.get("tools")


# ── Contrato de pinceles ────────────────────────────────────────────────────

class BrushContext:
    """Vista de solo lectura del lienzo alrededor del cursor, para que un
    SmartBrush pueda decidir qué pintar. No mutar frame directamente — el
    historial de deshacer depende de que las escrituras pasen únicamente por
    los offsets devueltos en paint()."""

    def __init__(self, frame, col, row, fg_char, fg_color, bg_color):
        self.frame    = frame
        self.col      = col
        self.row      = row
        self.fg_char  = fg_char
        self.fg_color = fg_color
        self.bg_color = bg_color

    def in_bounds(self, dc: int = 0, dr: int = 0) -> bool:
        c, r = self.col + dc, self.row + dr
        return 0 <= c < self.frame.width and 0 <= r < self.frame.height

    def char_at(self, dc: int = 0, dr: int = 0) -> str:
        if not self.in_bounds(dc, dr):
            return " "
        return self.frame.content[self.row + dr][self.col + dc]

    def colors_at(self, dc: int = 0, dr: int = 0) -> tuple:
        if not self.in_bounds(dc, dr):
            return (7, 0)
        fg, bg = self.frame.newColorMap[self.row + dr][self.col + dc]
        return (fg, bg)

    def is_empty(self, dc: int = 0, dr: int = 0) -> bool:
        """True si la celda está vacía (espacio o sin bg) — igual criterio
        de transparencia que usa la composición de capas."""
        ch = self.char_at(dc, dr)
        _fg, bg = self.colors_at(dc, dr)
        return ch in (" ", "\x00") and bg == 0

    def neighbors4(self, dc: int = 0, dr: int = 0):
        """(dc,dr) de las 4 celdas ortogonales vecinas a la posición dada."""
        return ((dc + 1, dr), (dc - 1, dr), (dc, dr + 1), (dc, dr - 1))

    def is_edge(self, dc: int = 0, dr: int = 0) -> bool:
        """True si la celda y algún vecino ortogonal difieren en 'vacío' —
        borde entre contenido y espacio en blanco (texto, formas, etc.)."""
        here_empty = self.is_empty(dc, dr)
        return any(self.is_empty(ndc, ndr) != here_empty
                   for ndc, ndr in self.neighbors4(dc, dr))

    def neighbors8(self, dc: int = 0, dr: int = 0):
        """(dc,dr) de las 8 celdas vecinas (incluye diagonales)."""
        return [(dc + ndc, dr + ndr)
                for ndc in (-1, 0, 1) for ndr in (-1, 0, 1)
                if not (ndc == 0 and ndr == 0)]

    def count_neighbors(self, predicate, dc: int = 0, dr: int = 0, diagonal: bool = False) -> int:
        """Cuenta vecinos que cumplen predicate(ch, fg, bg) — 4 direcciones,
        u 8 con diagonal=True. Base para pinceles tipo autómata celular
        (crecimiento orgánico, suavizado, etc.)."""
        offsets = self.neighbors8(dc, dr) if diagonal else self.neighbors4(dc, dr)
        return sum(1 for ndc, ndr in offsets
                   if predicate(self.char_at(ndc, ndr), *self.colors_at(ndc, ndr)))

    def scan(self, dc0: int, dr0: int, dc1: int, dr1: int):
        """Bloque rectangular [dc0..dc1] × [dr0..dr1] (inclusive) de
        (ch, fg, bg), relativo al cursor — para analizar un patrón antes de
        decidir qué pintar (ej: carácter dominante, textura repetida)."""
        return [[(self.char_at(dc, dr), *self.colors_at(dc, dr))
                for dc in range(dc0, dc1 + 1)]
                for dr in range(dr0, dr1 + 1)]

    def flood_region(self, dc: int = 0, dr: int = 0, max_cells: int = 4000):
        """BFS de celdas vacías conectadas (4-dir) desde (dc,dr). Devuelve
        (offsets, reached_edge): offsets es el conjunto de (dc,dr) visitados
        (acotado a max_cells), reached_edge es True si la exploración tocó el
        borde del frame — o si se alcanzó max_cells sin cerrarse, en cuyo
        caso se asume exterior (heurística: un hueco genuinamente encerrado
        es casi siempre mucho más chico que ese tope)."""
        if not self.is_empty(dc, dr):
            return set(), False
        start = (dc, dr)
        seen  = {start}
        queue = deque([start])
        reached_edge = False
        while queue:
            cdc, cdr = queue.popleft()
            c, r = self.col + cdc, self.row + cdr
            if c == 0 or r == 0 or c == self.frame.width - 1 or r == self.frame.height - 1:
                reached_edge = True
            for ndc, ndr in self.neighbors4(cdc, cdr):
                if (ndc, ndr) in seen:
                    continue
                if not self.in_bounds(ndc, ndr):
                    reached_edge = True
                    continue
                if not self.is_empty(ndc, ndr):
                    continue
                seen.add((ndc, ndr))
                queue.append((ndc, ndr))
                if len(seen) >= max_cells:
                    return seen, True
        return seen, reached_edge

    def is_interior(self, dc: int = 0, dr: int = 0, max_cells: int = 4000) -> bool:
        """True si la celda vacía en (dc,dr) está encerrada por contenido
        (no llega al borde del frame al explorar el hueco conectado)."""
        if not self.is_empty(dc, dr):
            return False
        _offsets, reached_edge = self.flood_region(dc, dr, max_cells)
        return not reached_edge


class BrushBase:
    name: str = "Sin nombre"
    description: str = ""
    author: str = ""

    @property
    def footprint(self):
        """Offsets (dr, dc) usados SOLO para la previsualización del cursor
        (rectángulo/hueco que se dibuja bajo el ratón) — en un SmartBrush no
        necesita coincidir exactamente con lo que paint() termine pintando."""
        raise NotImplementedError

    def paint(self, ctx: BrushContext):
        """Devuelve [(dr, dc, ch, fg, bg), ...] a estampar, relativos al
        cursor. ch/fg/bg en None usan ctx.fg_char/fg_color/bg_color."""
        raise NotImplementedError


class Brush(BrushBase):
    """Pincel estático (.json): offsets fijos desde el centro del cursor."""

    def __init__(self, name, cells, description="", author=""):
        self.name        = name
        self.cells       = list(cells)   # [(dr, dc), ...]
        self.description = description
        self.author      = author
        self.source_path: str | None = None   # ruta en disco, si vino de un archivo

    def to_dict(self):
        return {
            "version":     1,
            "name":        self.name,
            "description": self.description,
            "author":      self.author,
            "cells":       [list(c) for c in self.cells],
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            name        = d["name"],
            cells       = [tuple(c) for c in d["cells"]],
            description = d.get("description", ""),
            author      = d.get("author", ""),
        )

    @property
    def footprint(self):
        return self.cells

    def paint(self, ctx: BrushContext):
        return [(dr, dc, None, None, None) for dr, dc in self.cells]

    @property
    def bbox(self):
        """(rmin, cmin, rmax, cmax) relativo al centro."""
        rs = [dr for dr, _ in self.cells]
        cs = [dc for _, dc in self.cells]
        return min(rs), min(cs), max(rs), max(cs)

    @property
    def size(self):
        """(filas, columnas) del bounding box."""
        r0, c0, r1, c1 = self.bbox
        return r1 - r0 + 1, c1 - c0 + 1


class SmartBrush(BrushBase, ABC):
    """Contrato para pinceles con lógica en Python (.py) — ver docstring del
    módulo. Instanciada sin argumentos; source_path se asigna al cargar."""

    source_path: str | None = None

    @property
    def footprint(self):
        return [(0, 0)]

    @abstractmethod
    def paint(self, ctx: BrushContext):
        ...


# ── Helpers de geometría ───────────────────────────────────────────────────────

def _square(n):
    half = n // 2
    return tuple((dr, dc)
                 for dr in range(-half, n - half)
                 for dc in range(-half, n - half))

def _diamond(r):
    return tuple((dr, dc)
                 for dr in range(-r, r + 1)
                 for dc in range(-r, r + 1)
                 if abs(dr) + abs(dc) <= r)

def _circle(r):
    return tuple((dr, dc)
                 for dr in range(-r, r + 1)
                 for dc in range(-r, r + 1)
                 if dr * dr + dc * dc <= r * r + 0.5)


# ── Pinceles built-in ──────────────────────────────────────────────────────────

_BUILTIN: list = [
    Brush("Punto 1×1",         _square(1),
          "Un solo carácter", "built-in"),
    Brush("Cuadrado 2×2",      _square(2),
          "Cuadrado 2×2 centrado", "built-in"),
    Brush("Cuadrado 3×3",      _square(3),
          "Cuadrado 3×3", "built-in"),
    Brush("Cuadrado 4×4",      _square(4),
          "Cuadrado 4×4", "built-in"),
    Brush("Cuadrado 5×5",      _square(5),
          "Cuadrado 5×5", "built-in"),
    Brush("Diamante 3×3",      _diamond(1),
          "Cruz de 5 celdas", "built-in"),
    Brush("Diamante 5×5",      _diamond(2),
          "Diamante de 13 celdas", "built-in"),
    Brush("Círculo r=1",       _circle(1),
          "Círculo relleno radio 1", "built-in"),
    Brush("Círculo r=2",       _circle(2),
          "Círculo relleno radio 2", "built-in"),
    Brush("Círculo r=3",       _circle(3),
          "Círculo relleno radio 3", "built-in"),
    Brush("Línea vertical 5",  ((-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0)),
          "5 celdas verticales", "built-in"),
    Brush("Línea horizontal 5",(( 0,-2), (0,-1), (0, 0), (0, 1), (0, 2)),
          "5 celdas horizontales", "built-in"),
    Brush("Diagonal \\",       ((-1,-1), (0, 0), (1, 1)),
          "Diagonal izquierda 3", "built-in"),
    Brush("Diagonal /",        (( 1,-1), (0, 0), (-1, 1)),
          "Diagonal derecha 3", "built-in"),
    Brush("Cruz 5",            ((-2, 0),(-1, 0),(0,-2),(0,-1),(0, 0),(0, 1),(0, 2),(1, 0),(2, 0)),
          "Cruz de 9 celdas", "built-in"),
]

# Conjunto de nombres built-in para distinguirlos en la UI
BUILTIN_NAMES: frozenset = frozenset(b.name for b in _BUILTIN)


# ── Carga de pinceles .py ───────────────────────────────────────────────────

def _load_python_brush(path: str) -> SmartBrush:
    """Ejecuta el módulo (privilegios completos, sin sandbox — ver docstring
    del módulo) y busca exactamente una subclase de SmartBrush."""
    mod_name = f"durdrawgui_brush_{os.path.splitext(os.path.basename(path))[0]}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    candidates = [
        obj for _, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, SmartBrush) and obj is not SmartBrush
    ]
    if len(candidates) != 1:
        raise ValueError(
            f"se esperaba exactamente 1 subclase de SmartBrush en {path}, "
            f"se encontraron {len(candidates)}"
        )
    instance = candidates[0]()
    if not instance.name or instance.name == "Sin nombre":
        instance.name = os.path.splitext(os.path.basename(path))[0]
    instance.source_path = path
    return instance


class BrushLibrary:
    """Catálogo de pinceles built-in + usuario (.json y .py).
    Los pinceles de usuario persisten en ~/.config/durdrawgui/brushes/."""

    _DIR = os.path.expanduser("~/.config/durdrawgui/brushes")

    def __init__(self):
        self._user: list = []
        self._load_user()

    # ── Acceso ────────────────────────────────────────────────────────────────

    @property
    def all(self) -> list:
        return list(_BUILTIN) + self._user

    @property
    def names(self) -> list:
        return [b.name for b in self.all]

    def get(self, name: str):
        for b in self.all:
            if b.name == name:
                return b
        return _BUILTIN[0]

    # ── Persistencia ──────────────────────────────────────────────────────────

    def _load_user(self):
        if not os.path.isdir(self._DIR):
            return
        for fname in sorted(os.listdir(self._DIR)):
            path = os.path.join(self._DIR, fname)
            try:
                if fname.endswith(".json"):
                    with open(path, encoding="utf-8") as f:
                        brush = Brush.from_dict(json.load(f))
                    brush.source_path = path
                    self._user.append(brush)
                elif fname.endswith(".py"):
                    self._user.append(_load_python_brush(path))
            except Exception as exc:
                _log.warning(f"pincel '{fname}' no se pudo cargar: {exc}")

    def _safe_filename(self, name: str, ext: str = ".json") -> str:
        safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name)
        return os.path.join(self._DIR, f"{safe}{ext}")

    def add(self, brush: Brush):
        """Agrega un pincel JSON de usuario y lo guarda en disco."""
        os.makedirs(self._DIR, exist_ok=True)
        self._user = [b for b in self._user if b.name != brush.name]
        dest = self._safe_filename(brush.name)
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(brush.to_dict(), f, ensure_ascii=False, indent=2)
        brush.source_path = dest
        self._user.append(brush)

    def delete(self, name: str) -> bool:
        """Elimina un pincel de usuario (.json o .py). Devuelve True si se eliminó."""
        for i, b in enumerate(self._user):
            if b.name == name:
                self._user.pop(i)
                src = getattr(b, "source_path", None)
                if src and os.path.exists(src):
                    os.remove(src)
                return True
        return False

    def export_to(self, name: str, path: str) -> bool:
        """Exporta un pincel: los .json se serializan, los .py se copian tal cual
        (source_path) porque son código, no datos."""
        b = self.get(name)
        if not b:
            return False
        if isinstance(b, Brush):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(b.to_dict(), f, ensure_ascii=False, indent=2)
            return True
        src = getattr(b, "source_path", None)
        if not src or not os.path.exists(src):
            raise ValueError(f"'{name}' no tiene archivo fuente disponible para exportar.")
        shutil.copyfile(src, path)
        return True

    def import_from(self, path: str):
        """Importa un pincel desde .json (datos) o .py (SmartBrush, se copia
        el script a la carpeta de usuario). Lo agrega a la librería."""
        if path.endswith(".py"):
            brush = _load_python_brush(path)   # validar que carga ANTES de copiar
            os.makedirs(self._DIR, exist_ok=True)
            dest = os.path.join(self._DIR, os.path.basename(path))
            shutil.copyfile(path, dest)
            brush.source_path = dest
            self._user = [b for b in self._user if b.name != brush.name]
            self._user.append(brush)
            return brush
        with open(path, encoding="utf-8") as f:
            brush = Brush.from_dict(json.load(f))
        self.add(brush)
        return brush
