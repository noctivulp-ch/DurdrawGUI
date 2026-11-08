"""Copias de las rejillas de un frame para los snapshots de deshacer.

deepcopy() recorría cada celda con su maquinaria genérica: unos 17 ms por
rejilla en un 240×67, y cada trazo hacía cuatro copias. Además, cada copia
creaba 16 080 listas [fg, bg] nuevas, y eso disparaba el recolector de basura,
que recorre el documento entero (millones de listas) en cada pasada. Cifras en
docs/pendientes/rust-modulos.md y ADR 0002.

Las copias son superficiales por fila, y es correcto porque los elementos no
se modifican en su sitio:

- content: filas de str, que son inmutables.
- newColorMap: filas de pares [fg, bg]. **Invariante:** un par nunca se
  modifica en su sitio (pair[0] = x); siempre se sustituye entero
  (fila[c] = [fg, bg]). Así una copia y el original pueden compartir los pares.
  Las funciones de core/durdraw/durdraw_movie.py que sí los modifican
  (search_and_replace_color*, change_palette_*, strip_backgrounds) no se usan;
  quien las integre tiene que copiar los pares antes.
  tests/test_document.py::test_deshacer_restaura_tras_cada_herramienta lo vigila.
"""


def copy_content(content):
    return [row[:] for row in content]


def copy_colors(color_map):
    return [row[:] for row in color_map]
