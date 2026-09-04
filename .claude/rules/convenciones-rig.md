# Convenciones de rig: naming, construccion, modulos

Este fichero es la unica politica de naming y construccion. Skills y docs
enlazan aqui; no repiten estas listas. Tabla completa de sufijos por tipo de
nodo, con los legacy: `maya_tools/scripts/criterios_naming.md`.

## Naming
- `{lado}_{descripcion}{indice}_{TIPO}`: `L_armUpper02_JNT`, `C_masterwalk_CTL`.
  Lado obligatorio (`C_`, `L_`, `R_`); indice de dos digitos (`00`).
- Sufijos en MAYUSCULAS, un solo caso en todo el repo. Basicos: `_GRP` transform,
  `_OFF` grupo offset de control, `_TRN` transform de settings, `_JNT` joint,
  `_CTL` control, `_ENV` joint de export, `_GUIDE` guia, `_CRV` curva, `_NRB`
  nurbs, `_LOC` locator, `_SEP` atributo separador.
- Joints de skin: `{lado}_{zona}Skinning_JNT` (sueltos) y `{lado}_{segmento}0{i}_JNT`
  (ribbon). `corrective` o `ring` en el nombre = joint correctiva: es lo que la
  cuelga del `_ENV` de su padre en el export.
- Los nombres derivados se construyen por `replace("_JNT", "_CTL")`: el sufijo
  tiene que ser identico en todo el repo. Restos en minusculas (`_jnt`, `_ctl`,
  `_grp`, 4 ficheros) son legacy: migrar al tocar, nunca extender.

## Construccion
- Rig por matrices: `offsetParentMatrix`, `multMatrix`, `blendMatrix`,
  `aimMatrix`, `parentMatrix`, `worldInverseMatrix`. Sin constraints clasicos.
- Grupo offset entre el padre y el nodo movido: canales de control y joint a 0.
- Nodos math/matrix de Maya 2024+ (`multiply`, `sum`, `subtract`, `divide`,
  `negate`, `clamp`, `remapValue`, `rowFromMatrix`...). Prohibidos en codigo
  nuevo: `multiplyDivide`, `plusMinusAverage`, `multDoubleLinear`, `addDoubleLinear`.
- `createNode(..., ss=True)` en todo nodo utilitario. Deformers por su comando.
- Escala global: lo que mida en unidades de mundo lee `C_masterwalk_CTL.globalScale`.
- Pose por matrices mundo (`bend_driver`, `bend_factor`, `extract_twist`). Nunca
  `rotate` local de un joint (vale 0) ni controles FK del cuerpo (mueren en IK).
  La cara es la excepcion: ahi el control es la fuente de la pose.
- Nodos nativos por defecto. Un plugin nuevo se justifica por escrito. Python
  solo para prototipos y tools one-shot, nunca evaluando por frame.

## Modulos y datos
- Un modulo = clase `XxxModule` con `make(side, ...)`. `__init__` lee
  `data_manager.DataExportBiped().get_data("basic_structure", ...)`; al final
  `append_data("<modulo>", {...})`. Nunca nombres de nodo a mano entre modulos.
- Todo lo que cambia entre personajes va en datos, no en codigo:
  `.claude/rules/datos-y-versionado.md`.
- Cabecera de modulo: `from maya_tools.scripts.utils import x` + `reload(x)`.
- Todo tunable por plug: cantidades y limites como atributos con `Enable`,
  defaults proporcionales al hueso. Separadores enum lockeados (`XXX_SEP`).
- Idempotente, sin depender de la seleccion; un rebuild parte de escena limpia.
