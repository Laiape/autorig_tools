"""
Check de _fit_rows del fingers_module: python scripts/tools/tests/test_fingers_fit_rows.py

Pura tabla, sin escena: solo comprueba que un dedo con menos guias de las
canonicas coge las filas desde la primera falange (el 00 se anima como el 01) y
que uno con mas repite la fila de la ultima, y que una rama comparte la fila
de su profundidad con sus hermanos.
"""
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))

import importlib
importlib.reload = lambda m: m  # los stubs no son recargables

# maya y los utils del repo no pintan nada aqui: se stubean para poder importar.
for mod in ["maya", "maya.cmds", "maya.api", "maya.api.OpenMaya",
            "maya_tools.scripts.utils.data_manager",
            "maya_tools.scripts.utils.guides_manager",
            "maya_tools.scripts.utils.curve_tool",
            "maya_tools.scripts.utils.matrix_manager"]:
    sys.modules.setdefault(mod, types.ModuleType(mod))

from maya_tools.scripts.biped.autorig import fingers_module as fm

P1, P2, P3 = fm._SDK_ROWS["index"][1:]

# cadena completa: metacarpiano + tres falanges, tal cual
assert fm._fit_rows(fm._SDK_ROWS["index"], 4) == [None, P1, P2, P3]
# una sola guia -> se anima como la primera falange
assert fm._fit_rows(fm._SDK_ROWS["index"], 1) == [P1]
assert fm._fit_rows(fm._SDK_ROWS["thumb"], 1) == [fm._SDK_ROWS["thumb"][1]]
# dos y tres guias: siguen arrancando en la primera falange
assert fm._fit_rows(fm._SDK_ROWS["index"], 2) == [P1, P2]
assert fm._fit_rows(fm._SDK_ROWS["index"], 3) == [P1, P2, P3]
# de mas: la ultima falange repite fila, nunca se queda sin SDK
assert fm._fit_rows(fm._SDK_ROWS["index"], 6) == [None, P1, P2, P3, P3, P3]
# ningun dedo corto se queda con la fila del metacarpiano (None) delante
for name, rows in fm._SDK_ROWS.items():
    for n in range(1, len(rows) + 3):
        fitted = fm._fit_rows(rows, n)
        assert len(fitted) == n, (name, n, fitted)
        assert None not in fitted or n >= len(rows), (name, n, fitted)

# bifurcacion: L_thumb00-01-02-03 + L_thumb13 colgando del 02.
T0, T1, T2 = fm._SDK_ROWS["thumb"]
assert fm._rows_for_depths(fm._SDK_ROWS["thumb"], [0, 1, 2, 3, 3]) == [T0, T1, T2, T2, T2]
# las dos ramas terminales comparten fila, y la rama no desplaza a sus hermanos
assert fm._rows_for_depths(fm._SDK_ROWS["index"], [0, 1, 2, 3, 3]) == [None, P1, P2, P3, P3]
# dedo corto que ademas se bifurca: sigue arrancando en la primera falange
assert fm._rows_for_depths(fm._SDK_ROWS["index"], [0, 1, 1]) == [P1, P2, P2]

print("OK")

# _is_corrective vive dentro de skeleton_hierarchy y rig_manager arrastra medio
# Maya (y PySide) al importarse, asi que se extrae del fuente y se ejecuta: asi
# el check corre el codigo real y no una copia que puede envejecer.
import io
import textwrap

_src = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "..", "utils", "rig_manager.py"), encoding="utf-8").read()
_block = _src[_src.index("    def _is_corrective(j):"):]
_ns = {}
exec(textwrap.dedent(_block[:_block.index(chr(10) * 2)]), _ns)
_is_corrective = _ns["_is_corrective"]

# el anular NO es una correctiva: en minusculas "ring" casaba y el dedo entero
# se caia del esqueleto de export
assert not _is_corrective("|skel_GRP|L_ringSkinning_GRP|L_ring00Skinning_JNT")
assert not _is_corrective("R_ring02Skinning_JNT")
assert _is_corrective("L_elbowRing00_JNT")
assert _is_corrective("C_jawCorrective_JNT")

print("OK _is_corrective")
