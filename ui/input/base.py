from PySide6.QtCore import Qt


class InputDriver:
    """Base común: cada driver recibe el canvas (geometría/render/overlays) y
    la app (modelo/herramientas/atajos) de los que depende."""

    def __init__(self, canvas, app):
        self.canvas = canvas
        self.app = app

    # ── Bindings de ratón/tableta ("Mouse:<Qt.MouseButton.name>") ──────────
    # Compartido por MouseInput y TabletInput: ambos reciben botones como
    # Qt.MouseButton estándar (un lápiz con botón lateral mapeado a "clic
    # derecho" por el driver externo llega exactamente igual que un mouse).

    def matches_mouse_button(self, action_id: str, btn) -> bool:
        """True si btn (un solo Qt.MouseButton) es uno de los bindings
        'Mouse:X' configurados para la acción."""
        return f"Mouse:{btn.name}" in self.app.shortcut_mgr.keys(action_id)

    def matches_mouse_buttons_mask(self, action_id: str, buttons_mask) -> bool:
        """True si algún binding 'Mouse:X' de la acción está prendido en
        buttons_mask (máscara combinada, ej. QTabletEvent.buttons())."""
        for key_str in self.app.shortcut_mgr.keys(action_id):
            if not key_str.startswith("Mouse:"):
                continue
            btn = getattr(Qt.MouseButton, key_str[len("Mouse:"):], None)
            if btn is not None and (buttons_mask & btn):
                return True
        return False
