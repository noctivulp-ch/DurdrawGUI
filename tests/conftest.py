"""Aísla las pruebas de la configuración y los logs reales del usuario.

core.config, core.shortcuts y core.log resuelven sus rutas al importarse, así
que las variables tienen que estar puestas antes de que cualquier módulo de
prueba los importe. conftest.py se carga antes que los módulos de prueba.
"""

import os
import sys
import tempfile

_tmp = tempfile.mkdtemp(prefix="durdrawgui-tests-")
os.environ.setdefault("DURDRAW_CONFIG_DIR", os.path.join(_tmp, "config"))
os.environ.setdefault("DURDRAW_LOG_DIR", os.path.join(_tmp, "logs"))
os.environ["QT_QPA_PLATFORM"] = "offscreen"   # el entorno de escritorio trae wayland

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
