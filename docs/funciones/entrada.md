# Entrada: ratón, teclado y tableta

Decisión y motivos: [ADR 0001](../decisiones/0001-entrada-por-dispositivo.md).

| Módulo | Qué traduce |
|---|---|
| `ui/input/base.py` | `InputDriver`: acceso al canvas y a la app, y comprobación de bindings `Mouse:X` |
| `ui/input/mouse.py` | Clic, arrastre y rueda. Estados `standby → drawing / scrolling`. Space sostenido = desplazar |
| `ui/input/keyboard.py` | Space, Ctrl (guías de cel), tecla de cuentagotas sostenida y el modo cursor de teclado |
| `ui/input/tablet.py` | `QTabletEvent`: trazo, borrador de hardware y botones laterales |

## Bindings de ratón y tableta

En Preferencias → Atajos → «Ratón y tableta». Se asignan con un clic.

| Acción | Por defecto |
|---|---|
| Borrar | botón derecho |
| Recoger color | sin asignar (Alt+clic y la tecla F sostenida funcionan siempre) |
| Desplazar el lienzo | botón central |

El botón izquierdo no se puede asignar: es el que dibuja.

## Modo cursor de teclado

`Ctrl+Tab` lo activa o lo desactiva, y `Esc` lo apaga. Mientras está activo se desactivan las
acciones de una sola tecla (herramientas, frames), para que esas teclas muevan el cursor y dibujen.
Teclas por defecto: flechas = cursor, Space = ejecutar la herramienta, Q = borrar, E = alternar
frente y fondo, F = recoger, I/J/K/L = paleta, Ctrl+flechas = caracteres, 1–0 = carácter de la fila.
