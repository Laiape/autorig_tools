"""
Módulo de pierna de cuadrúpedo — PLANTILLA (rellenar).

═══════════════════════════════════════════════════════════════════════════════
ARQUITECTURA — el porqué antes del qué
═══════════════════════════════════════════════════════════════════════════════
Tres niveles, y cada cosa vive en el que le toca:

  1. SUPERCLASE (LegModule)  Todo lo que es igual en cualquier cuadrúpedo:
                             guías, cadena IK, controles, blend FK/IK, stretch,
                             skinning.
  2. SUBCLASES               SOLO cuando cambia la TOPOLOGÍA o el ALGORITMO.
                             Aquí eso es el rol anatómico: delantera (escápula,
                             sin cadera) vs trasera (cadera, doblez caudal).
                             NO subclases por animal.
  3. CONFIGURACIÓN (datos)   Cuando solo cambia el VALOR. Los parámetros por
                             especie salen del .build, no de una clase.

Por qué NO subclase por animal:
  · Explosión combinatoria — front/back existe siempre, así que por animal daría
    HorseFront, HorseBack, DogFront, DogBack. Cuatro clases para dos animales,
    seis para tres, y la mitad duplicada.
  · Estarías subclasificando VALORES. La diferencia real caballo/perro en la
    pierna son números, no comportamiento. Para valores, datos.
  · Esconde tu comparación. El TFG defiende que la anatomía determina los
    parámetros: te interesa verlos JUNTOS en una tabla, no repartidos en clases.

───────────────────────────────────────────────────────────────────────────────
REGLA DE ORO DE LOS FLAGS
───────────────────────────────────────────────────────────────────────────────
    Un flag codifica un HECHO ANATÓMICO, no una preferencia de implementación.

    BIEN  RECIPROCAL_COUPLING = True
          -> el peroneo tercero équido es tendinoso, el acoplamiento
             corvejón-babilla es obligatorio. Citable.
    MAL   USE_LAYERED_IK = True
          -> "cómo prefiero construirlo". Ese flag ya se probó y era peor que
             el nativo.

Si cada flag se remonta a una afirmación anatómica citable, la clase no se pudre
Y la tabla "dato anatómico -> parámetro -> valor" del TFG sale sola del código.

───────────────────────────────────────────────────────────────────────────────
EL PIE VA COMPUESTO, NO HEREDADO
───────────────────────────────────────────────────────────────────────────────
Casco (un dedo, cadena lineal) y pata (varios dedos, se bifurca) son estructuras
distintas -> clases distintas. Pero si las metes como eje de HERENCIA de la
pierna vuelves a la explosión (FrontHoof, BackHoof, FrontPaw, BackPaw). El pie es
una PIEZA que la pierna COMPONE. Dos subclases de pierna x dos de pie, y un
tercer animal se añade con datos.
"""

import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import math

from utils import data_manager
from utils import guides_manager
from utils import curve_tool
from utils import matrix_manager
from utils import ribbon

reload(data_manager)
reload(guides_manager)
reload(curve_tool)
reload(matrix_manager)
reload(ribbon)


# ═════════════════════════════════════════════════════════════════════════════
# SOLVERS — la variable independiente de tu experimento (cap. 8)
# ═════════════════════════════════════════════════════════════════════════════
# Que sea un ARGUMENTO y no un flag de clase ni una subclase es deliberado: el
# experimento lo varía sobre el MISMO personaje y las MISMAS guías, así que tiene
# que poder cambiarse en la llamada sin tocar código ni datos.
SOLVER_RP     = "rp"       # RP de 2 huesos + SC para el resto (el port del bípedo)
SOLVER_SPRING = "spring"   # ikSpringSolver sobre los 3 segmentos funcionales
SOLVER_NODES  = "nodes"    # IK analítico por nodos (teorema del coseno)


class LegModule(object):

    """
    Sistema base de pierna. No se instancia directa: se usan las subclases.
    """

    # ─────────────────────────────────────────────────────────────────────────
    # FLAGS DE CLASE — rol anatómico (topología), NO especie
    # ─────────────────────────────────────────────────────────────────────────
    # Cada flag lleva al lado el hecho anatómico que lo justifica. Si no puedes
    # escribir ese comentario, el flag probablemente no debería existir.

    LEG_PREFIX = "backLeg"       # prefijo de las guías: backLeg / frontLeg
    ROOT_JOINT = "Hip"           # primera guía de la cadena (Hip / Shoulder)

    FORWARD_AXIS = (0, 0, 1)     # hacia dónde dobla la articulación intermedia.
                                 # Trasera: caudal (corvejón atrás).
                                 # Delantera: cranial (carpo adelante). ANATOMÍA.

    PV_SIGN = -1                 # lado del pole vector respecto al plano.

    REPOSITION_IK_TO_GUIDES = True
                                 # Si la cadena IK reposa EXACTAMENTE sobre las
                                 # guías. Trasera sí (el corvejón ya marca el
                                 # doblez). Delantera NO: su guía es casi recta y
                                 # necesita el pre-bend desplazado para doblar
                                 # en el sentido correcto.

    RECIPROCAL_COUPLING = False  # Aparato recíproco: peroneo tercero + flexor
                                 # digital superficial acoplan corvejón y babilla
                                 # obligatoriamente. Trasera de ungulado: True.
                                 # Cánido: el peroneo tercero es MUSCULAR, no
                                 # obliga -> False. Delantera: no existe.

    FOOT_CLASS = None            # clase de pie compuesta (HoofFoot / PawFoot).

    # ─────────────────────────────────────────────────────────────────────────
    def __init__(self):
        """
        Lee del build lo que necesita del resto del rig. NO hardcodees nombres:
        todo por data_manager, que es el estándar del repo.
            modules_GRP · skel_GRP · masterwalk_ctl

        Guarda aquí también la convención de ejes (primary = aim, secondary = up).
        """

        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")

        
    # ═════════════════════════════════════════════════════════════════════════
    # ORQUESTACIÓN
    # ═════════════════════════════════════════════════════════════════════════
    def make(self, side, solver=SOLVER_SPRING, skinning_joints_number=5,
             bendys=True, config=None):
        """
        Punto de entrada. Construye la pierna entera.

        Args:
            side (str): 'L' | 'R'.
            solver (str): SOLVER_RP | SOLVER_SPRING | SOLVER_NODES.
                          Es la variable del experimento del cap. 8.
            skinning_joints_number (int): joints de skinning por segmento bendy.
            bendys (bool): ribbons por segmento.
            config (dict|None): parámetros POR ESPECIE leídos del .build
                          (muelle sí/no, acoplamiento, calibración…).
                          None -> defaults de clase.

        Crea los tres grupos del módulo como el resto del repo:
            module_trn      (bajo modules_GRP)
            skeleton_grp    (bajo skel_GRP)
            controllers_grp (bajo masterwalk_ctl)

        ORDEN DE CONSTRUCCIÓN (importa; el porqué está en cada método):
            load_guides          las guías definen proporciones; nada hardcodeado
            orient_guides        frames a partir de las posiciones
            setup_chain          índices y matrices; genérico por índice
            create_chains        cadena IK
            controllers_creation FK + IK + pole vector + settings
            ik_setup             <- AQUÍ conmuta el solver (el experimento)
            ik_stretch_soft
            ik_calibration       el reposo debe quedar en identidad
            fk_setup
            reciprocal_coupling  (si el flag lo pide)
            foot.build           el pie COMPUESTO
            bendys_setup         (si bendys)
            skinning_setup
            publish              data_manager, para que otros módulos consuman
        """

        self.side = side
        self.solver = solver
        self.skinning_joints_number = skinning_joints_number
        self.bendys = bendys
        self.config = config or {}

        self.module_name = f"{self.side}_{self.LEG_PREFIX}{self.ROOT_JOINT}"
        self.module_trn = cmds.group(n=f"{self.module_name}_module_GRP", ss=True, r=True, p=self.modules)
        self.skeleton_grp = cmds.group(n=f"{self.module_name}_skel_GRP", ss=True, r=True, p=self.skel_grp)
        self.controllers_grp = cmds.group(n=f"{self.module_name}_controllers_GRP", ss=True, r=True, p=self.masterwalk_ctl)

        # Llamar a los métodos
        self.load_guides()
        self.orient_guides()
        self.setup_chain()
        self.create_chains()
        self.controllers_creation()
        self.ik_setup()
        self.ik_stretch_soft()
        self.ik_calibration()
        self.fk_setup()
        if self.RECIPROCAL_COUPLING:
            self.reciprocal_coupling()
        self.foot = self.FOOT_CLASS()
        self.foot.build(self)
        if self.bendys:
            self.bendys_setup()
        self.skinning_setup()
        self.publish()

    # ═════════════════════════════════════════════════════════════════════════
    # GUÍAS Y CADENA
    # ═════════════════════════════════════════════════════════════════════════
    def load_guides(self):
        """
        Trae la cadena de guías del .guides del personaje y la parenta al módulo.

        OJO: guides_manager.get_guides() CREA los joints leyendo el fichero JSON;
        NO busca en la escena. Para comprobar si una guía existe usa
        read_guides_info(character, guide_name), nunca cmds.objExists().
        """

        self.guides_chain = guides_manager.get_guides(f"{self.side}_{self.LEG_PREFIX}{self.ROOT_JOINT}_JNT")
        cmds.parent(self.guides_chain[0], self.module_trn)
        
    def orient_guides(self):
        """
        Construye los frames (matrices) de cada guía a partir de sus POSICIONES.

        Patrón del repo que conviene mantener: red de orientación TEMPORAL
        (transforms + aimMatrix), se hornean los valores porque las guías son
        estáticas, y se borra. Así el rig no arrastra nodos aimMatrix vivos ni
        transforms _GUIDE.

        Convención de ejes: un eje baja por el hueso (aim, hacia la guía
        siguiente) y otro se alinea al lateral del personaje. El tercero sale del
        producto cruzado. Alinear el lateral a una referencia FIJA (y no al
        siguiente joint) es lo que evita que la cadena se retuerza.

        DIFERENCIA CON EL LIMB: aquí NO puedes descartar la última guía. En la
        pierna es la punta del casco / la uña, y de ella salen los pivotes del
        pie reverso. Guarda su matriz aunque no genere control FK.
        """
        guides_manager.orient_guides(self.guides_chain, self.side, self.LEG_PREFIX, self.ROOT_JOINT)

    def setup_chain(self):
        """
        Índices y matrices de la cadena. GENÉRICO POR ÍNDICE — no hardcodees
        números de hueso: trasera y delantera tienen distinta longitud, y el
        perro y el caballo también.

        Debe calcular al menos:
            leg_joints     la cadena menos la punta
            plant_index    la pisada (cuartilla / falange proximal)
            leg_end_index  fin del IK principal = la articulación MTP
                           (metacarpo/metatarsofalángica). ES EL MISMO HUESO en
                           el ungulado y en el digitígrado — lo que el équido
                           llama menudillo. A partir de ahí el caballo tiene un
                           dedo y el perro cuatro.
            plane_normal   plano real de la cadena (para el pole vector)
            bend_dir       sentido del doblez, derivado de FORWARD_AXIS

        TRAMPA MEDIDA: el pre-bend que siembra el doblez NO debe mutar las
        posiciones de guía. Si lo hace, se propaga a los FK, a la calibración y
        al skinning, y acabas con una pose de REPOSO doblada por dentro del
        hueso. Siembra sobre una COPIA que solo alimente al solver.
        """
        for i, guide in enumerate(self.guides_chain):
            # Aquí va tu código para calcular los índices y matrices
            pass

    def create_chains(self):
        """
        Cadena de joints IK a partir de los frames, encadenada por parentesco y
        con las transformaciones congeladas (makeIdentity) para que las
        rotaciones locales arranquen limpias.
        """
        pass

    # ═════════════════════════════════════════════════════════════════════════
    # CONTROLES
    # ═════════════════════════════════════════════════════════════════════════
    def controllers_creation(self):
        """
        Controles FK (uno por joint) + controles IK del pie + pole vector +
        settings (con el switch Ik_Fk y su reverse para la visibilidad).

        Convención del repo: rig por MATRICES, no constraints. Grupos offset
        (create_controller con offset=["GRP","ANM"]) y conexión a
        offsetParentMatrix. Nada de parentConstraint.

        Bloquea lo que el animador no debe tocar: escala y visibilidad siempre;
        en FK también la traslación.
        """
        pass

    def fk_setup(self):
        """
        Lado FK del blend. En este repo el FK no tiene cadena de joints propia:
        el blendMatrix lee directamente el worldMatrix del control.

        Cada control cuelga del anterior con un opm RELATIVO (multMatrix del
        frame por la inversa del padre) y un xform a identidad para dejar los
        canales limpios.

        SI AÑADES FK STRETCH — la trampa que costó un bug de 175 unidades en el
        lado R: la longitud de reposo debe salir de LA MISMA CELDA de la matriz
        que estás reconstruyendo, no recalcularse aparte. Y si te tienta aplicar
        un signo "porque el lado derecho es espejo", comprueba antes que el eje
        aim REALMENTE está espejado — puede que el espejo viva solo en los otros
        dos ejes y estés negando algo que no toca. Sacar el valor de la propia
        matriz elimina la clase entera de bug.
        """
        pass

    # ═════════════════════════════════════════════════════════════════════════
    # IK — el corazón del experimento
    # ═════════════════════════════════════════════════════════════════════════
    def ik_setup(self):
        """
        Conmuta al solver pedido. Este método es lo que hace que el capítulo 8
        sea un EXPERIMENTO y no una demo: misma pierna, mismas guías, misma
        pose, solo cambia esto.

        ANTES de crear cualquier handle:
            cmds.joint(chain[0], e=True, setPreferredAngles=True, children=True)
        Sin preferred angles el spring no codifica el zigzag de reposo y la
        cadena SALTA al conmutar a IK. (Medido: drift ~10u -> 0 al ponerlo.)

        DESPUÉS de crear los handles: parentarlos al grupo del módulo, ocultarlos
        y congelar sus canales (un floatConstant a 0 conectado a t/r) para que
        nada los mueva por accidente.

        Despacha a _ik_rp / _ik_spring / _ik_nodes según self.solver.
        """
        pass

    def _ik_rp(self):
        """
        CONFIG A — RP de 2 huesos + SC para el resto. Es el port directo del
        bípedo, y la solución "ingenua" que quieres tener en la comparativa.

        Hipótesis a contrastar: una cadena de 3 segmentos funcionales no cabe en
        un solver de 2 huesos, así que el tercer segmento queda fuera del IK y
        hay que compensarlo en otro sitio. MIDE DÓNDE ACABA EL DOBLEZ.
        """
        pass

    def _ik_spring(self):
        """
        CONFIG B — ikSpringSolver sobre los 3 segmentos (raíz -> MTP), + SC para
        el pie.

        Requiere cargar el plugin: cmds.loadPlugin("ikSpringSolver", quiet=True).
        Con cadena de 2 huesos el spring no aporta nada: cae a RP.

        El reparto del doblez entre las dos articulaciones lo expone el propio
        solver por springAngleBias. Una cadena de 3 huesos con raíz y pie
        clavados tiene EXACTAMENTE UN grado de libertad redundante, así que el
        control correcto es UN escalar (los dos slots del bias, complementarios:
        b y 1-b). No hace falta ni un control extra ni un joint más.

        LECCIÓN CARA, no la repitas: pinchar la articulación intermedia con un
        control de 3 GDL SOBRE-RESTRINGE la cadena, y entonces el único sitio
        donde puede meterse el grado de libertad que falta es DENTRO de un hueso.
        Eso es lo que produce joints a media diáfisis. El radio y el metacarpo
        son huesos únicos y sólidos: no flexionan.
        """
        pass

    def _ik_nodes(self):
        """
        CONFIG C — IK analítico por nodos (teorema del coseno).

        Es tu aportación del cap. 6.2. Ventaja teórica: cacheable, paralelizable,
        sin plugin. Coste: el polo vector y el up vector hay que resolverlos a
        mano.

        Mídelo honestamente. El resultado puede perfectamente ser que el nativo
        ya lo resuelve mejor — y eso, MEDIDO, es un resultado publicable, no un
        fracaso. Un TFG que reporta un resultado negativo con datos es más
        sólido que uno que solo enseña lo que le salió bien.
        """
        pass

    def ik_stretch_soft(self):
        """
        Stretch (escala del segmento por ratio distancia/longitud, normalizado
        por globalScale) y soft IK (amortiguación exponencial al acercarse a la
        extensión máxima).

        Ambos APAGADOS por defecto: son decisión del animador, no del rig.

        Nota para el cap. 8: el stretch es también el escape cuando la cadena se
        queda sin alcance. Si mides un pivote o un muelle y "no llega",
        comprueba si es ALCANCE antes de culpar al mecanismo.
        """
        pass

    def ik_calibration(self):
        """
        Hornea la corrección para que la cadena IK repose EXACTAMENTE sobre las
        guías, sea cual sea el solver.

        Sin esto cada solver da un reposo distinto y la comparación del
        experimento no es limpia — estarías midiendo la diferencia de reposo, no
        la del solver.

        Criterio de éxito: en reposo, delta IK vs guías = 0 y match FK/IK = 0.
        """
        pass

    def reciprocal_coupling(self):
        """
        Solo si RECIPROCAL_COUPLING. Acopla la articulación intermedia a la
        anterior EN EL LADO FK.

        Por qué hace falta explícitamente: en IK el acoplamiento sale GRATIS —
        un spring de 3 huesos reparte el doblez entre las dos articulaciones y
        ningún control puede desacoplarlas. Pero al conmutar a FK cada control
        recupera rotación libre y se pueden posar combinaciones mecánicamente
        imposibles (babilla flexionada con corvejón extendido).

        EL RATIO NO TE LO INVENTES: mídelo del propio solver barriendo el pie y
        leyendo cómo se reparten los ángulos. Si sale constante, el acoplamiento
        lineal REPRODUCE lo que el IK ya hace en vez de aproximarlo — y eso es
        defendible ante un tribunal, que es más de lo que puede decirse de un
        número elegido a ojo.

        Expón un atributo (0-1) para poder apagarlo, y ponlo en el control
        CONDUCTOR, nunca en el conducido (sería un ciclo de dependencia).
        """
        pass

    # ═════════════════════════════════════════════════════════════════════════
    # SALIDA
    # ═════════════════════════════════════════════════════════════════════════
    def bendys_setup(self):
        """
        Ribbons por segmento para deformación suave (utils/ribbon + de_boor_core).
        Ojo al twist: extráelo por swing-twist (cuaternión) para que no flipee.
        """
        pass

    def skinning_setup(self):
        """
        Joints de deformación finales.

        Publica también QUÉ joints deforman el pie y de qué plug sale su world,
        para que un offset posterior pueda componerse encima sin adivinar nombres.
        """
        pass

    def publish(self):
        """
        data_manager.append_data(). Todo lo que otro módulo pueda necesitar:
        controles principales, switch IK/FK, pole vector, y el joint MTP (del que
        cuelgan los dedos en una pata digitígrada).

        Data-driven: los módulos NO se pasan nombres a mano.
        """
        pass

    # ═════════════════════════════════════════════════════════════════════════
    # INSTRUMENTACIÓN — para el capítulo 8
    # ═════════════════════════════════════════════════════════════════════════
    def measure_bend_distribution(self, pose=None):
        """
        Devuelve cuántos grados se lleva CADA articulación en una pose dada,
        p. ej. {joint: angulo_interior}.

        Es tu métrica estrella y ningún framework comercial la publica: dice si
        el doblez cae en articulaciones REALES o dentro de un hueso. Úsala para
        comparar las tres configuraciones de solver sobre la MISMA pose extrema
        (el plegado recogido del galope).
        """
        pass

    def measure_fk_ik_drift(self):
        """
        Distancia que salta cada joint al conmutar el switch en reposo.
        Criterio: 0.0. Cualquier otra cosa es un bug, no una tolerancia.
        """
        pass


# ═════════════════════════════════════════════════════════════════════════════
# SUBCLASES POR ROL ANATÓMICO (topología distinta -> clase distinta)
# ═════════════════════════════════════════════════════════════════════════════
class BackLegModule(LegModule):
    """
    Tren trasero: cadera -> babilla -> corvejón -> MTP -> pisada -> punta.
    El corvejón dobla CAUDAL. Es donde vive el aparato recíproco (si la especie
    lo tiene).
    """
    LEG_PREFIX = "backLeg"
    ROOT_JOINT = "Hip"
    # Sobrescribe aquí: FORWARD_AXIS · PV_SIGN · REPOSITION_IK_TO_GUIDES ·
    # RECIPROCAL_COUPLING · FOOT_CLASS


class FrontLegModule(LegModule):
    """
    Tren delantero: escápula -> hombro -> codo -> carpo -> MTP -> …
    El carpo dobla CRANIAL. No hay cadera: hay escápula, y eso es una diferencia
    de TOPOLOGÍA, no de valor -> por eso es subclase y no un flag.
    """
    LEG_PREFIX = "frontLeg"
    ROOT_JOINT = "Shoulder"

    def make(self, side, **kwargs):
        """Llama al padre y añade la escápula."""
        pass

    def scapula_setup(self):
        """
        Escápula flotante. El cuadrúpedo no tiene clavícula articulada
        (sinsarcosis: el omóplato se une al tronco solo por músculo) y su centro
        instantáneo de rotación CAMBIA durante la zancada.

        Un joint con pivote fijo no puede representar eso. La solución es que la
        escápula DESLICE sobre una superficie que aproxime el tórax, con el
        pivote emergiendo del contacto (closestPointOnSurface + frame de
        superficie).

        HONESTIDAD METODOLÓGICA (esto va tal cual en la memoria): no existe
        ningún valor publicado de excursión escapular — todas las fuentes son
        cualitativas. Así que la superficie está calibrada A OJO contra
        referencia, y hay que DECIRLO, no presentarlo como si reprodujera un dato
        medido. Nombrar el hueco es una aportación; fingir que no existe es lo
        que un tribunal tumba.
        """
        pass


# ═════════════════════════════════════════════════════════════════════════════
# PIE — COMPUESTO, no heredado
# ═════════════════════════════════════════════════════════════════════════════
class FootBase(object):
    """
    Interfaz común del pie. La pierna COMPONE una de estas, no hereda de ellas.

    Contrato: la pierna entrega el MTP y las matrices de reposo; el pie construye
    sus pivotes y expone sus atributos en el control del pie.
    """

    def build(self, leg):
        """leg = el LegModule que compone este pie (para leer índices y matrices)."""
        pass

    def pivots(self, leg):
        """
        Matrices de reposo de los pivotes del pie reverso.

        Los pivotes del bípedo (talón y planta) NO aplican tal cual a un
        cuadrúpedo: hay que derivarlos de la anatomía de cada tipo de pisada.
        """
        pass

    def roll_attributes(self, leg, foot_ctl):
        """
        Roll y twist. Arquitectura en dos tramos: hasta el break angle levanta la
        pisada; del break al straight angle rueda la punta.

        TRAMPA: si construyes el tramo negativo con un remapValue de inputMin=0,
        el roll negativo CLAMPA A CERO y no hace absolutamente nada. Aísla el
        tramo negativo (un min) antes de darle su propio pivote.
        """
        pass


class HoofFoot(FootBase):
    """
    UNGULADO. Apoya solo el casco (un dedo, el III, con el metacarpo fusionado
    en la caña).

    Pivotes válidos: punta del casco (breakover), talón del casco, y bordes
    lateral/medial. El MTP (menudillo) NO es un pivote: es el MUELLE — se hunde
    por CARGA contra el ligamento suspensor, y el tendón flexor devuelve el 93%
    del trabajo. Confundirlo con un pivote es el error más fácil al portar un pie
    de bípedo.
    """

    def fetlock_spring(self, leg, foot_ctl):
        """
        Hundimiento del menudillo por carga. Característica de ESTA clase, no del
        cuadrúpedo genérico: viene del aparato de estay équido (dormir de pie).

        Curva NO lineal: el aparato suspensor ENDURECE al cargarse. Los datos de
        marcha calibran el RANGO (~22° de excursión del ángulo MCP de paso a
        galope); la FORMA la pone el muelle.

        El pivote va en la CUARTILLA, no en el menudillo: el casco está plantado
        y el menudillo baja girando alrededor de ella.

        Default 0. Con carga en reposo la cadena queda en su tope de alcance y el
        ball-roll se aplasta (medido: el menudillo sube 7.45u con carga 0 y solo
        2.25u con carga 1).
        """
        pass


class PawFoot(FootBase):
    """
    DIGITÍGRADO. Apoya varios dedos (II-V) con almohadilla; el I queda elevado
    como espolón. Sin aparato de estay -> SIN muelle de menudillo.

    DIFERENCIA ESTRUCTURAL (y la razón de que esto sea una clase y no un flag):
    a partir del MTP la cadena se BIFURCA. La pierna es lineal e indexa por
    posición; los dedos son N cadenas. Van en su propio módulo, colgados del MTP
    por parentMatrix — NO por DAG: el MTP ya viene dirigido por el blend, así que
    colgar por DAG heredaría su transform dos veces.

    TRAMPA DEL TALÓN, verifícala: derivar el talón proyectando la PISADA a la
    altura de la punta funciona en el casco porque la cuartilla está ELEVADA
    sobre el suelo. En una pata digitígrada la almohadilla YA está en el suelo,
    así que la proyección no mueve nada y el talón COINCIDE con el pivote de la
    almohadilla: pivote degenerado. Además el calcáneo del digitígrado está
    arriba, en el corvejón — no es un contacto. El contacto trasero real es el
    borde posterior de la almohadilla.
    """

    def digits_setup(self, leg):
        """Delega en el módulo de dedos (cadenas FK + curl/spread/twist)."""
        pass


# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN POR ESPECIE — datos, no clases
# ═════════════════════════════════════════════════════════════════════════════
# Esto es la TABLA de tu TFG hecha código: dato anatómico -> parámetro -> valor.
# Su sitio definitivo es el .build de cada personaje (junto al resto de
# rig_settings), NO un dict aquí. Se deja como referencia de qué forma tiene.
#
# OJO al meterlo en el .build: get_rig_data() reescribe el fichero desde los
# atributos de C_guides_GRP, así que una clave suelta se la come. Hay que
# añadirla también a create_rig_settings.
#
# SPECIES_CONFIG = {
#     "horse": {
#         "solver":              SOLVER_SPRING,
#         "foot":                HoofFoot,
#         "reciprocal_coupling": True,   # peroneo tercero tendinoso -> obligatorio
#         "fetlock_spring":      True,   # aparato de estay
#         "sagittal_bias":       2.4,    # flexión concentrada en la lumbosacra
#     },
#     "chihuahua": {
#         "solver":              SOLVER_SPRING,
#         "foot":                PawFoot,
#         "reciprocal_coupling": False,  # peroneo tercero muscular -> no obliga
#         "fetlock_spring":      False,  # sin aparato de estay
#         "sagittal_bias":       1.3,    # flexión más repartida
#     },
# }
