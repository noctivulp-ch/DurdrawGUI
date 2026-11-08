"""Drivers de input de AsciiCanvas — un dispositivo por módulo.

Cada driver traduce los eventos crudos de UN dispositivo (mouse, teclado,
tableta) a acciones sobre canvas/app; AsciiCanvas solo delega. Meta: que
agregar o modificar el comportamiento de un dispositivo no obligue a leer
los otros — mouse.py no sabe nada de teclado.py ni de tablet.py.

El estado que paintEvent() necesita leer cada frame (cursor, guías de cel,
selección, brush cursor, cursor de modo teclado) sigue viviendo en
AsciiCanvas — los drivers lo escriben, no lo esconden detrás de getters.
Solo el estado puramente de gesto/interacción (qué botón está sostenido, la
máquina de estados dibujar/scrollear) vive dentro de cada driver.
"""
