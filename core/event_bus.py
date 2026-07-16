class EventBus:
    """Bus de eventos pub/sub simple. Desacopla emisores de consumidores."""

    def __init__(self):
        self._h = {}  # event → [callback]

    def on(self, event, callback):
        self._h.setdefault(event, []).append(callback)

    def off(self, event, callback):
        if callback in self._h.get(event, []):
            self._h[event].remove(callback)

    def emit(self, event, data=None):
        for cb in list(self._h.get(event, [])):
            cb(data)
