import core.log as log

_log = log.get("history")


class CommandHistory:
    def __init__(self, max_size=100, on_change=None):
        self._undo_stack = []
        self._redo_stack = []
        self._max        = max_size
        self._on_change  = on_change

    def push(self, undo_fn, redo_fn=None):
        self._undo_stack.append((undo_fn, redo_fn))
        if len(self._undo_stack) > self._max:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        _log.debug(f"push  undo={len(self._undo_stack)}  redo=0")
        if self._on_change:
            self._on_change()

    def undo(self):
        if not self._undo_stack:
            _log.debug("undo ignorado — pila vacía")
            return
        undo_fn, redo_fn = self._undo_stack.pop()
        undo_fn()
        self._redo_stack.append((undo_fn, redo_fn))
        _log.debug(f"undo  undo={len(self._undo_stack)}  redo={len(self._redo_stack)}")
        if self._on_change:
            self._on_change()

    def redo(self):
        if not self._redo_stack:
            _log.debug("redo ignorado — pila vacía")
            return
        undo_fn, redo_fn = self._redo_stack.pop()
        if redo_fn:
            redo_fn()
        self._undo_stack.append((undo_fn, redo_fn))
        _log.debug(f"redo  undo={len(self._undo_stack)}  redo={len(self._redo_stack)}")
        if self._on_change:
            self._on_change()

    def can_undo(self):
        return bool(self._undo_stack)

    def can_redo(self):
        return bool(self._redo_stack)
