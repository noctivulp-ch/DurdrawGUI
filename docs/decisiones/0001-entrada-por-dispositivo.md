# 0001 — Entrada repartida en un driver por dispositivo

- **Estado:** adoptada (2026-11-08). El trabajo empezó el 2026-09-28 y quedó sin commitear hasta esta fecha.
- **Ámbito:** `ui/input/`, `ui/canvas.py`, `core/shortcuts.py`, `ui/preferences.py`, `ui/app.py`.

## Contexto

`AsciiCanvas` (`ui/canvas.py`) tenía dentro toda la entrada: la máquina de estados del ratón
(dibujar, desplazar), la rueda, Space y Ctrl, y el modo cursor de teclado entero (unas 350 líneas de
`keyPressEvent` y ayudantes). Añadir la tableta obligaba a meter una tercera fuente de eventos en el
mismo archivo, que además pinta. Los botones del ratón estaban fijos en el código (derecho = borrar,
central = desplazar) y no se podían configurar.

## Decisión

1. **Un driver por dispositivo** en `ui/input/`: `MouseInput`, `KeyboardInput` y `TabletInput`,
   con una base común (`InputDriver`). `AsciiCanvas` solo delega cada evento Qt a su driver.
2. **El estado que lee `paintEvent` sigue en el canvas** (cursor, guías de cel, cursor de teclado).
   Los drivers lo escriben. Dentro de cada driver solo vive el estado del gesto (qué botón está
   pulsado, si se está dibujando o desplazando).
3. **Botones configurables**: categoría «Ratón y tableta» en `core/shortcuts.py`, con valores
   `Mouse:<Qt.MouseButton.name>`. Sirven igual para el ratón y para los botones laterales de una
   tableta, porque los dos llegan como `Qt.MouseButton`. No son `QAction`: los lee el driver.
4. **Tableta nativa** con `QTabletEvent`. Aceptar el evento suprime el `QMouseEvent` que Qt
   sintetizaría, así que el trazo no se pinta dos veces.
5. **El modo cursor de teclado pasa de `Tab` a `Ctrl+Tab`**, registrado como `QAction` de ventana:
   funciona tenga quien tenga el foco. Con `Tab` suelto, Qt lo usaba para mover el foco antes de que
   llegara a ninguna acción, y solo funcionaba si el lienzo ya tenía el foco.

## Lo que se corrigió al cerrar el trabajo (2026-11-08)

- La captura de Preferencias aceptaba un clic para **cualquier** acción. Un `Mouse:RightButton` en
  una acción de teclado acababa en `QKeySequence("Mouse:RightButton")`, que no significa nada.
  Ahora las acciones de «Ratón y tableta» solo admiten botones, y las demás solo teclas.
- También aceptaba el **botón izquierdo** para «borrar» o «desplazar». Como el driver consulta esos
  bindings antes de dibujar, la app se quedaba sin forma de dibujar. Ahora se rechaza.
- `core/shortcuts.py` ignoraba `--config-dir` y escribía siempre en `~/.config/durdrawgui`.

## Verificación

`tests/test_input_e2e.py` manda eventos Qt reales a la `App` completa (offscreen): clic y arrastre
con el lápiz, clic derecho para borrar, Alt+clic para el cuentagotas, el botón central para
desplazar, atajos de herramienta, Ctrl+Z, el modo cursor de teclado (una sola conmutación por cada
Ctrl+Tab), y trazo y botón lateral de la tableta. **No se ha probado con una tableta física.**

## Alternativas descartadas

- **Un único `InputController` con ramas por dispositivo**: vuelve a mezclar los tres en un archivo.
- **Esconder el estado de dibujo tras getters**: `paintEvent` lo lee en cada repintado y la
  indirección no aporta nada.
