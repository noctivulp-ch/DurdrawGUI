"""
Sistema de pinceles para DurdrawGUI.

Un Brush define la forma del pincel como lista de offsets (dr, dc) desde el centro
del cursor. BrushLibrary gestiona los built-in y los pinceles de usuario.

Formato de archivo .json por pincel:
  {
    "version": 1,
    "name":        "Nombre del pincel",
    "description": "Descripción opcional",
    "author":      "Autor opcional",
    "cells":       [[-1, -1], [-1, 0], [0, 0]]   <- offsets [dr, dc] desde centro
  }
"""

import json
import os


class Brush:
    def __init__(self, name, cells, description="", author=""):
        self.name        = name
        self.cells       = list(cells)   # [(dr, dc), ...]
        self.description = description
        self.author      = author

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


class BrushLibrary:
    """Catálogo de pinceles built-in + usuario.
    Los pinceles de usuario persisten en ~/.config/durdraw/brushes/."""

    _DIR = os.path.expanduser("~/.config/durdraw/brushes")

    def __init__(self):
        self._user: list[Brush] = []
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
            if not fname.endswith(".json"):
                continue
            try:
                with open(os.path.join(self._DIR, fname), "r", encoding="utf-8") as f:
                    self._user.append(Brush.from_dict(json.load(f)))
            except Exception:
                pass

    def _safe_filename(self, name: str) -> str:
        safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name)
        return os.path.join(self._DIR, f"{safe}.json")

    def add(self, brush: Brush):
        """Agrega un pincel de usuario y lo guarda en disco."""
        os.makedirs(self._DIR, exist_ok=True)
        # Evitar duplicados de nombre
        self._user = [b for b in self._user if b.name != brush.name]
        self._user.append(brush)
        with open(self._safe_filename(brush.name), "w", encoding="utf-8") as f:
            json.dump(brush.to_dict(), f, ensure_ascii=False, indent=2)

    def delete(self, name: str) -> bool:
        """Elimina un pincel de usuario. Devuelve True si se eliminó."""
        for i, b in enumerate(self._user):
            if b.name == name:
                self._user.pop(i)
                p = self._safe_filename(name)
                if os.path.exists(p):
                    os.remove(p)
                return True
        return False

    def export_to(self, name: str, path: str) -> bool:
        b = self.get(name)
        if not b:
            return False
        with open(path, "w", encoding="utf-8") as f:
            json.dump(b.to_dict(), f, ensure_ascii=False, indent=2)
        return True

    def import_from(self, path: str):
        """Importa un pincel desde JSON. Lo agrega a la librería de usuario."""
        with open(path, "r", encoding="utf-8") as f:
            brush = Brush.from_dict(json.load(f))
        self.add(brush)
        return brush
