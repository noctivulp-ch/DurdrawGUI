"""
Registro de herramientas. Decora cada clase con @register y el
ToolBar / ContextBar se construyen solos leyendo el registro.

Para añadir una herramienta nueva basta con crear su archivo en tools/
y usar @register — no hay que editar toolbar.py ni context_bar.py.
"""

_registry = {}  # name → class


def register(cls):
    """Decorador de clase: registra la herramienta en el registro global."""
    _registry[cls.name] = cls
    return cls


def get_all():
    return dict(_registry)


def get_ordered():
    """Lista de clases ordenada por .order; inserta None como separador
    antes de las que tengan separator_before = True."""
    sorted_cls = sorted(_registry.values(), key=lambda c: getattr(c, "order", 99))
    result = []
    for cls in sorted_cls:
        if getattr(cls, "separator_before", False) and result:
            result.append(None)
        result.append(cls)
    return result


def create_all(app):
    """Instancia todas las herramientas registradas y las devuelve en un dict."""
    return {name: cls(app) for name, cls in _registry.items()}
