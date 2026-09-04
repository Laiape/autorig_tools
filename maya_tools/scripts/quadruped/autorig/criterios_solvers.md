# Criterios: solvers, pole vector y valores medidos del cuadrupedo

Parent: `maya_tools/scripts/quadruped/autorig/como_funciona.md`.
Codigo: `maya_tools/scripts/quadruped/autorig/leg_module_self.py`, `maya_tools/scripts/quadruped/autorig/spine_module.py`,
`LEG_SOLVER_OPTIONS` y `resolve_leg_solvers` en `maya_tools/scripts/utils/rig_manager.py`.
Fuente de los numeros: docstrings de las clases y mensajes de commit de `quadruped/`
(septiembre 2026), medidos con `maya_tools/scripts/tools/tests/test_build_horse_leg_self.py`
y con `measure_bend_distribution` / `measure_fk_ik_drift`, en el caballo y el chihuahua.

Este fichero es el sitio para cambiar un criterio de solver o un valor medido.
Cuando cambie, en la misma tarea: el flag o la constante en `leg_module_self.py`
(o `spine_module.py`), el `.build` de la especie si es un valor por especie, el
docstring que lo cita, y volver a pasar la suite.

Convencion de medida: pose de referencia "plegado recogido del galope" = control
del pie a `translateY +25`, `translateZ -8` (default de `measure_bend_distribution`);
los angulos son el angulo interior en cada articulacion; "fuga lateral" es el
desplazamiento fuera del plano sagital, en unidades de escena.

---

## 1. Solvers (`LEG_SOLVER_OPTIONS`)

| Preset | Ficha `IK_CONFIGS` (start, end, solver) | Que hace | Resultado medido | Estado |
|---|---|---|---|---|
| `spring` | (0, 3, ikSpringSolver) | un spring sobre los tres segmentos funcionales; reparte el doblez | reparto natural babilla/corvejon 84.8/90.2 y codo/carpo 78.8/95.3 (cap. 8); fuga lateral en pliegue profundo 2.36 con PV craneal, 0.55 con PV caudal | DEFAULT. Necesita `ik_calibration` (twist horneado) porque el plano del spring nace de una captura interna que el poleVectorConstraint no siempre corrige |
| `rp` | (0, 2, ikRPsolver) + (2, 3, ikSCsolver) | el port del bipedo | fuga 2.29 -> 0.51 con PV caudal; en la trasera del caballo NO reposa (11-16 u de error) | inutilizable en la trasera |
| `nodes` | sin handles: `_ik_nodes` (dos triangulos encadenados por teorema del coseno; cuerda viva) | IK analitico por nodos, cacheable, sin plugin de solver; carga `matrixNodes` y `lookdevKit`; borra las cadenas IK al terminar | fuga 1.45 -> 0.11 (delantera); 1.29 -> 0.18 en chihuahua y 0.74 -> 0.27 en caballo (trasera); `Twist` 45 grados mueve el codo 7.6 u con el pie quieto; el UNICO que hace los dos extremos del galope canino (colapso del carpo y extension total) | activo; `Bend_Bias` y `Twist` en el master |
| `sc_rp_sc` | (0, 1, SC) + (1, 3, RP) + (3, 4, SC) | SC humero->codo, RP codo->fetlock, SC fetlock->cuartilla | reposo exacto, switch sin salto, roll correcto; PERO el carpo queda bloqueado a 180 en el galope recogido porque el SC alto sigue al pie; fuga 0.31 -> 0.02 | ficha valida; carpo muerto |
| `sc_rp_sc_carpus` | (0, 1, SC, ancla `root`) + (1, 3, RP) + (3, 4, SC) | el SC alto ancla a la RAIZ: el codo queda rigido al cuerpo y el RP dobla el carpo | carpo 65.7 en galope recogido (180 con `sc_rp_sc`) | activo |
| `rp_rp` | (0, 2, RP) + (2, 4, RP), un solo PV | dos rotate plane encadenados; el carpo articula en la union | RESULTADO NEGATIVO: el pie pierde el objetivo ~0.9 u constante (el menudillo es el joint medio del segundo RP y su plano lo dicta un PV puesto para el codo); con PV craneal fuga 2.31 y codo invertido; con PV caudal codo limpio (0.48) pero el carpo muere (142-173 grados); reparto invertido al del perro real (codo 65 / carpo 112; Muybridge pide el carpo dominante). Arreglarlo exige DOS pole vectors: un control mas sin ganancia | queda en `IK_CONFIGS` como resultado negativo documentado; no usar |
| `spring_rp` | sin ficha | esta en `LEG_SOLVER_OPTIONS` pero no en `IK_CONFIGS`: `ik_setup` avisa y cae a `spring` | - | fantasma: quitar de la lista o darle ficha |

Prioridad de eleccion en el build: menu SELF MATH (`nodes`) > `solver_mode`
custom (`nodes` en ambos trenes) > `solver_front_leg` / `solver_back_leg` >
`leg_solver` de builds viejos > `spring`.

## 2. Pole vector

- `PV_SIGN = -1` (caudal) en delantera y trasera. Matriz 6 solvers x 2 lados
  del PV, en chihuahua y caballo, poses reposo / recogida media / profunda /
  extension: los ANGULOS por articulacion son identicos con el PV delante o
  detras (el lado no cambia el reparto); la FUGA LATERAL baja o iguala en
  todos los presets con el PV detras (numeros de la tabla); nada empeora y
  los pies siguen exactos. Anatomia: la bisagra real es el codo y el
  corvejon, que doblan caudal; el craneal se derivaba del apex del carpo y
  era el origen de la fuga.
- Apex `PV_APEX_INDEX = 2`: la articulacion media del zigzag, maxima
  separacion de la linea raiz->MTP. Posicion del PV = apex + `bend_dir` *
  (longitud raiz->MTP * 0.5) * `PV_SIGN`; con preferred angles puestos no
  mueve el reposo. Todos los handles RP de una ficha comparten el PV (el
  plano sagital es uno).
- El PV sigue al pie por defecto (space switch foot / root) con el
  masterwalk como espacio maestro.

## 3. Reparto del doblez (`Bend_Bias`)

- Una cadena de tres huesos con raiz y pie clavados tiene UN grado de
  libertad redundante; `Bend_Bias` es ese DOF (0.5 = reparto natural del
  solver, reposo intacto). Spring: `springAngleBias` con los dos slots
  complementarios (b, 1-b); el bias uniforme es un no-op medido (codo 81.74 /
  carpo 95.45 en 0.0, 0.25, 0.5, 0.75 y 1.0): lo que mueve el reparto es la
  razon entre slots. Medido en la delantera (galope recogido): bias 0.0 ->
  codo 105.9 / carpo 75.8; 0.5 -> 81.7 / 95.5; 1.0 -> 70.4 / 126.9 (unos 35
  grados de autoridad en el codo y 51 en el carpo, monotono).
- Nodes: la cuerda babilla->objetivo es viva (escala con la distancia
  raiz->objetivo y se clampa al rango fisico de tibia + cana). Con cuerda
  fija el corvejon se congela y la config degenera a RP + SC.

## 4. Acoplamiento reciproco (trasera)

- Hecho anatomico: peroneo tercero + flexor digital superficial acoplan
  babilla y corvejon en el equido (tendinoso, obligatorio). En el canido el
  peroneo tercero es muscular: no obliga.
- En IK sale gratis (el spring reparte); en FK hay que imponerlo:
  `reciprocal_coupling` acopla el corvejon a la babilla en el lado FK con un
  ratio MEDIDO del propio solver en el barrido del galope: babilla 51.8
  grados, corvejon 55.0 -> `HOCK_PER_STIFLE = -1.062` (signo por
  comportamiento: ambos angulos interiores cierran juntos). Verificado:
  25 -> 26.5. En reposo suma cero. Attr `Coupling` (0-1) en el CONDUCTOR (la
  babilla), nunca en el conducido.
- Valor por especie: clave `reciprocal_coupling` del `.build` (1 ungulado,
  0 canido); el flag de clase `RECIPROCAL_COUPLING = True` en `BackLegModule`
  es solo el fallback. Hoy ningun `.build` del repo lleva la clave: manda el
  fallback.

## 5. Calibracion y reposo

- `ik_calibration`: barrido grueso de 360 grados y refinado del twist del
  handle principal hasta que la deriva de las articulaciones interiores
  contra sus guias es menor que 0.002. Criterio: delta IK frente a guias = 0
  y match FK/IK = 0 (drift maximo medido 0.0016, residuo del spring). Sin
  esto cada solver da un reposo distinto y la comparacion no es limpia.
- El pre-bend que siembra el doblez se hace sobre una COPIA de las guias:
  mutar las guias contamina FK, calibracion y skinning (trampa medida).
- `blend_setup`: el FK entra por offset relativo al reposo (`FkFrame_MMX` =
  guia de reposo x ctl de reposo^-1 x ctl.worldMatrix); sin eso el lado R
  salia reflejado (punta a 25 u en la delantera, 18 u en la trasera).
  Verificado: punta 0.000 en las ocho patas, det +1, simetria L/R menor que
  0.001.

## 6. Pie

- `HoofFoot.fetlock_spring`: hundimiento del menudillo por carga (aparato de
  estay equido, no del cuadrupedo generico). Attr `Load` 0-1 en el master;
  muelle que endurece: theta = R * (1 - (1 - L)^2); rango R = -22 grados
  (excursion del angulo MCP paso->galope, datos de marcha); pivote en la
  CUARTILLA; inyectado en el manager del IK, no en el ball (moveria el casco,
  que debe quedar plantado). Medido: Roll -20 mueve el fetlock 1.42 u sin
  carga y 1.13 u con carga 1; load 0.5 -> 89 % del recorrido.
- `PawFoot`: fetlock->pastern y pastern->tip por `aimMatrix` rigidos al Foot;
  dedos con SDK (curl -70/-55/-45 proximal->distal a Curl 10; spread solo en
  la proximal con abanico simetrico respecto al eje funcional III-IV, externos
  a tope y centrales un tercio; twist +-15; espolon aparte), IK de dedos por
  triangulo en el espacio local de la falange raiz (sin PV), `Toes_IK` 0-1.
  Verificado en chihuahua: 13 joints de skin, reposo 0.000 / 0.0001.
- Roll del pie: el tramo negativo se aisla con un `min` antes de darle su
  pivote; un `remapValue` con inputMin 0 clampa a cero y no hace nada.

## 7. Escapula (delantera)

- Sinsarcosis: el omoplato se une al tronco solo por musculo y su centro de
  rotacion cambia durante la zancada. Solucion: la escapula DESLIZA sobre una
  superficie que aproxima el torax (elipsoide desde tres guias chest /
  clavicula / root, resuelto en forma cerrada, cero calibracion a ojo);
  posicion = switch master<->chest (50 %) + proyeccion + renormalizacion a la
  longitud del hueso; orientacion por aim al master; residuo de la NURBS
  (~0.06 %) horneado como delta -> reposo 0.000.
- Elevacion por compresion de la pata: rampa que satura en la compresion del
  galope recogido, `GALLOP_COMPRESSION = 0.73` (dist / reposo = 0.732
  medido); excursion declarada = (L / 2) * sin(20 grados).
- Thoracic sling (`Sling` 0-1, default 1): el torax cuelga entre las
  escapulas; al bajar el chest con el pie plantado la pata NO se pliega
  (stay apparatus). El ANM del master contrarresta solo el delta Y del chest,
  saturado en +-EXCURSION_MAX (~5.1 cm a escala real; referencias Payne 2005
  ~42 mm y Hartpury 2023 +5.3 / +6.2 cm de sternum lift). Medido: chest -6 ->
  pie plantado 0.0, codo -1.4 grados con sling frente a -23.5 sin el;
  horizontal 1:1; L/R identicos.
- Honestidad metodologica (va en el docstring): no hay valor publicado de
  excursion escapular; la superficie esta calibrada contra referencia
  cualitativa y se dice.

## 8. Spine (`SAGITTAL_BIAS`)

- Reparto de la flexion sagital: peso de reposo de cada control =
  (i / (n - 1))^SAGITTAL_BIAS. 1.0 = uniforme (firma felina); mayor =
  concentrado en la union lumbosacra (equino). Objetivo ex vivo: lumbosacra
  26.3 grados frente a 5.4 toracolumbar -> ratio 4.87.
- Barrido (guia en la lumbosacra, span 85.8 u, respuesta unitaria +5 u
  dorsal en el control caudal): 1.10 -> 3.89; 1.20 -> 4.35; 1.25 -> 4.59;
  1.30 -> 4.84; 1.35 -> 5.09; 1.50 -> 5.87; 2.00 -> 8.18; 2.40 -> 8.78
  (maximo); 3.20 -> 6.84; 4.50 -> 4.92. La curva NO es monotona (con los CVs
  apinados mover el caudal arrastra a los vecinos): dos valores dan el ratio
  (~1.3 y ~4.6) y se elige 1.3 porque deja los controles mejor separados
  para el animador. Reparto por joint con 1.3: 10.52, 6.16, 3.57, 1.95, 0.95,
  0.36, 0.07.
- `SAGITTAL_BIAS = 1.3` en la clase; `giraffe` a 1.0 desde `rig_manager`
  (`UNIFORM_SPINE_CHARS`). Si diverge mas, sube al `.build` (y a
  `create_rig_settings`, que hoy solo admite int y enum).
- La guia `C_spine00` se movio de z -55.84 a z -75.0 para que el extremo
  caudal caiga en la lumbosacra real (cadera z -74.93, primera caudal
  z -91.54). Eso cambia el espaciado de los joints de skin (9.52 -> 12.26) y
  obliga a REIMPORTAR PESOS.

## 9. Constants cheat sheet

```
LEG_SOLVER_OPTIONS       spring, rp, spring_rp, nodes, sc_rp_sc, sc_rp_sc_carpus, rp_rp
solver por defecto       spring
PV_SIGN                  -1 (caudal), delantera y trasera
PV_APEX_INDEX            2
STANDARD_JOINT_COUNT     6
REPOSITION_IK_TO_GUIDES  True trasera / False delantera (pre-bend desplazado)
HOCK_PER_STIFLE          -1.062 (reciprocal_coupling, trasera)
reciprocal_coupling      1 ungulado, 0 canido (.build; hoy sin clave en ningun personaje)
foot_type                0 hoof, 1 paw (.build; hoy sin clave en ningun personaje)
fetlock_spring           R = -22 grados, theta = R * (1 - (1 - L)^2)
GALLOP_COMPRESSION       0.73
EXCURSION_MAX (sling)    (L / 2) * sin(20 grados)
ik_calibration           deriva < 0.002
SAGITTAL_BIAS            1.3 (horse), 1.0 (giraffe)
pose de medida           pie translateY +25, translateZ -8
suite                    test_build_horse_leg_self.py (203 checks en el ultimo commit que lo cita)
```

Nota sobre el chihuahua: su `.build` tiene `Rig_Type` 0 y no lleva claves de
especie; la suite y los commits lo construyen directamente con
`leg_module_self` sobre sus guias, no por `build_rig`.
