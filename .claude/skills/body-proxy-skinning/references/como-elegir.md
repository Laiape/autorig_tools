# Cómo elegir cómo skinnear el cuerpo (proxy + refinado)

Del *"tengo este cuerpo que skinnear"* al *"usa esta cadena"*. Léela al empezar. La idea es
encuadrar con pocas preguntas y usar el árbol para elegir binding, flujo proxy, transferencia,
refinado y bake.

## 1. Preguntas de encuadre

Pregunta solo lo que el usuario **no** haya dicho:

| Variable | Por qué decide |
|---|---|
| **Densidad de la malla** | Muy densa → conviene **proxy** (pintar/afinar en low-res es mucho más rápido). Ligera → puedes skinnear directo. |
| **¿Hay proxy?** | Si ya existe un low-res que corresponde a la alta, aprovéchalo. Si no, valora crearlo (coste vs iteración que ahorra). |
| **Destino** | *Cine*: skin + Delta Mush + correctivos, sin miedo al coste. *Juego/tiempo real*: **skin lineal**, pocas influencias (≤4), hornear todo lo caro. |
| **Dónde falla el bind hoy** | ¿Qué zonas cruzan influencias (ingle, axila, dedos)? ¿Dónde colapsa el volumen (hombro, codo)? Cada síntoma lleva a una familia distinta (§3). |
| **Topología estable** | Si la malla aún cambia, prioriza métodos **robustos a cambio de topología** (transfer por UV, proxy) frente a pesos pintados a mano que se pierden. |

**Concretar "no es preciso".** El closest-joint falla de formas distintas; identifica cuál:

- **Cruza influencias** — un vértice recibe peso del joint equivocado por estar *cerca en línea
  recta* de otra parte anatómica (muslo interior ↔ otra pierna, axila ↔ pecho). → **binding
  volumétrico** (geodesic voxel), que mide por el interior del volumen.
- **Falloff duro / a saltos** — transiciones bruscas entre joints. → bind volumétrico + **ngSkin
  relax**, o **Delta Mush** de acabado.
- **Colapso de volumen** en flexión (candy-wrapper en muñeca, pinchado en codo/hombro). → **DQ**
  vs lineal, y **correctivos PSD** en esa pose.
- **Se pierde el trabajo al recambiar la malla** — repintas cada vez. → **proxy** + transfer por UV.

## 2. Ejes de comparación

Compara siempre sobre estos ejes (columnas del catálogo):

- **Calidad**: cuán bien deforma (sin cruces, sin colapsos, silueta correcta).
- **Eficiencia**: coste de evaluación en runtime (un skinCluster lineal con pocas influencias es lo
  más barato; Delta Mush y wraps cuestan por frame).
- **¿Cruza influencias?**: el criterio clave para la queja del usuario.
- **Esfuerzo**: autoría + setup + iteración.

**La calidad se sube por escalones.** Escalón 0 = closest-joint. No saltes a correctivos si el
problema se arregla un escalón antes (mejor bind, o Delta Mush).

## 3. Árbol de decisión

```
PASO 1 — BINDING (arranca bien, esto es lo que arregla el "cruza influencias"):
  Usa GEODESIC VOXEL BINDING (mide por el volumen, no cruza) como base por defecto.
  Alternativas: heat map, o transfer por UV/label desde un skin bueno. NUNCA closest-joint como
  base si la anatomía tiene partes próximas.

PASO 2 — ¿PROXY?
  ¿Malla densa / topología que aún cambia / quieres iterar rápido?
  ├── Sí → skinnea/afina en el PROXY low-res, luego transfiere a la alta (Paso 3).
  └── No → skinnea directo la alta.

PASO 3 — TRANSFERIR proxy -> alta (si hay proxy):
  Topología distinta o cambiante → transfer por UV independiente de topología (tu auto_skin_transfer)
  o Copy Skin Weights con -uvSpace + -influenceAssociation label.
  Misma topología → Copy Skin Weights index-for-index. Para seguir la superficie: cvWrap/proximityWrap.

PASO 4 — AFINAR:
  ngSkinTools2 por CAPAS (relax/smooth real, mirror, flood) sobre el bind volumétrico. (ngSkin es
  para AFINAR, no para inicializar con "assign closest joint".)

PASO 5 — REFINAR:
  DELTA MUSH de acabado (quita artefactos sin destruir detalle). Direct Delta Mush si lo quieres en
  tiempo real. Tension para modular por estiramiento.

PASO 6 — ¿EFICIENCIA FINAL? (juego / performance):
  Hornea Delta Mush/wrap/correctivos a un skin LINEAL: dm2skin (Delta-Mush-to-skin) o bakeDeformer,
  luego prune + maxInfluences + normalizar.

PASO 7 — ÚLTIMA MILLA (si "aún no queda bien"):
  Correctivos PSD/RBF (SHAPES/weightDriver) o combination shapes en hombros, caderas, codos, ingles.
```

La respuesta buena casi siempre es esta **cadena**, no un método suelto. Recomienda el punto de la
cadena donde está el problema y sube desde ahí.

## 4. Errores comunes al recomendar

- **Tapar un mal bind con Delta Mush.** Delta Mush suaviza; no reasigna el joint correcto. Si cruza
  influencias, arréglalo en el binding.
- **Usar "assign closest joint" como base.** Es un inicializador impreciso; parte de un bind
  volumétrico y deja ngSkin para afinar.
- **Pintar a mano sobre topología inestable.** Si la malla va a cambiar, el trabajo se pierde; usa
  proxy + transfer por UV.
- **Hornear lo dinámico.** bakeDeformer/dm2skin capturan deformación función-de-pose, no inercia ni
  colisión. No esperes secundario de un skin horneado.
- **Recomendar en el vacío.** Conecta con lo que ya tiene (ngSkinTools2, `auto_skin_transfer`,
  `skincluster_surface`, `SkinManager`, Delta Mush).
