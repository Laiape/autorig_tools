"""
Módulo de pierna de cuadrúpedo — implementación propia (en construcción).

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
import maya.mel as mel
import maya.api.OpenMaya as om
from importlib import reload
import math

from maya_tools.scripts.utils import data_manager
from maya_tools.scripts.utils import guides_manager
from maya_tools.scripts.utils import curve_tool
from maya_tools.scripts.utils import matrix_manager
from maya_tools.scripts.utils import rig_manager
from maya_tools.scripts.utils import ribbon

reload(data_manager)
reload(guides_manager)
reload(curve_tool)
reload(matrix_manager)
reload(rig_manager)
reload(ribbon)


# ═════════════════════════════════════════════════════════════════════════════
# SOLVERS
# ═════════════════════════════════════════════════════════════════════════════

SOLVER_RP     = "rp"       # RP de 2 huesos + SC para el resto (el port del bípedo)
SOLVER_SPRING = "spring"   # ikSpringSolver sobre los 3 segmentos funcionales
SOLVER_NODES  = "nodes"    # IK analítico por nodos (teorema del coseno)
SOLVER_SC_RP_SC = "sc_rp_sc"  # SC húmero->codo + RP codo->fetlock + SC fetlock->cuartilla
SOLVER_SC_RP_SC_CARPUS = "sc_rp_sc_carpus"  # como sc_rp_sc pero el SC alto ANCLA a la raiz: el carpo dobla
_AXIS_VECTORS = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}
    

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

    PV_SIGN = 1                 # lado del pole vector respecto al plano.

    PV_APEX_INDEX = 2            # Apex del PV: la articulación MEDIA del zigzag
                                 # (corvejón/carpo), el punto de máxima
                                 # separación de la línea raíz->MTP — ahí el PV
                                 # define el plano sin ambigüedad. En el codo o
                                 # la babilla el plano cae a mitad del zigzag y
                                 # el solver reparte peor. setup_chain lo deriva
                                 # con fallback y clamp para otras cadenas.

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
    STANDARD_JOINT_COUNT = 6
    IK_CONFIGS = {
        SOLVER_RP: [
            (0, 2, "ikRPsolver"),
            (2, 3, "ikSCsolver"),
        ],
        SOLVER_SPRING: [
            (0, 3, "ikSpringSolver"),
        ],
        SOLVER_SC_RP_SC: [
            (0, 1, "ikSCsolver"),
            (1, 3, "ikRPsolver"),
            (3, 4, "ikSCsolver"),
        ],
        # como sc_rp_sc pero el SC alto ancla a la RAIZ ("root"): el codo no
        # sigue al pie, asi que al recoger la mano el tramo codo->fetlock se
        # comprime y el CARPO (medio del RP) dobla de verdad.
        SOLVER_SC_RP_SC_CARPUS: [
            (0, 1, "ikSCsolver", "root"),
            (1, 3, "ikRPsolver"),
            (3, 4, "ikSCsolver"),
        ],
    }

    

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

        self.primaryInputAxis = (1, 0, 0)
        self.secondaryInputAxis = (0, 1, 0)

        self.primaryInputAxisRibbon = (1, 0, 0)
        self.secondaryInputAxisRibbon = (0, 0, 1)

    # ═════════════════════════════════════════════════════════════════════════
    # ORQUESTACIÓN
    # ═════════════════════════════════════════════════════════════════════════
    def make(self, side, solver=SOLVER_SPRING, skinning_joints_number=5,
             bendys=True, config=None):
        """
        Punto de entrada. Construye la pierna entera.

        Args:
            side (str): 'L' | 'R'.
            solver (str): clave de IK_CONFIGS ("rp" | "spring"; "nodes" aún sin
                          integrar en el dispatch). Es la variable del
                          experimento del cap. 8; llega del .build (leg_solver).
            skinning_joints_number (int): joints de skinning por segmento bendy.
            bendys (bool): ribbons por segmento.
            config (dict|None): parámetros POR ESPECIE leídos del .build
                          (muelle sí/no, acoplamiento, calibración…).
                          None -> defaults de clase.

        Crea los tres grupos del módulo como el resto del repo:
            module_trn      (bajo modules_GRP)
            skeleton_grp    (bajo skel_GRP)
            controllers_grp (bajo masterwalk_ctl)

        ORDEN DE CONSTRUCCIÓN (el que ejecuta este método hoy):
            load_guides          guías de pierna + pivotes del pie + settings
            orient_guides        frames horneados (world/local) por guía
            setup_chain          índices, plano y bend_dir; genérico por índice
            create_chains        cadena de joints IK
            controllers_creation settings + FK + IK + pivotes del pie reverso
            ik_setup             <- AQUÍ conmuta el solver (fichas IK_CONFIGS)
            ik_stretch_soft      stretch + soft del lado IK
            ik_calibration       (pendiente) el reposo debe quedar en identidad
            fk_setup             FK stretch por matrices
            blend_setup          blend FK/IK por joint (salida = plugs)
            reciprocal_coupling  (pendiente; si el flag lo pide)
            foot.build           el pie COMPUESTO: pivotes reversos + roll
            bendys_setup         bendy ctl por segmento
            skinning_setup       ribbons + joints del pie
            publish              (pendiente)

        """

        self.side = side
        self.solver = solver
        self.skinning_joints_number = skinning_joints_number
        self.bendys = bendys
        self.config = config or {}

        self.module_name = f"{self.side}_{self.LEG_PREFIX}"
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_{self.LEG_PREFIX}Module_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_{self.LEG_PREFIX}Skinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_{self.LEG_PREFIX}Controllers_GRP", ss=True, p=self.masterwalk_ctl)

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
        self.blend_setup()
        if self.RECIPROCAL_COUPLING:
            self.reciprocal_coupling()
        self.foot = self.FOOT_CLASS()
        self.foot.build(self)
        if self.bendys:
            self.roll_and_non_roll_setup()
            self.bendys_setup()
        self.skinning_setup()
        self.publish()

    # ═════════════════════════════════════════════════════════════════════════
    # GUÍAS Y CADENA
    # ═════════════════════════════════════════════════════════════════════════
    def load_guides(self):
        """
        Carga del .guides del personaje: la cadena de la pierna (parentada al
        módulo), los locators de pivotes del pie reverso (bankOut/bankIn/heel,
        en self.reverse_foot_locators) y el locator del settings.

        OJO: guides_manager.get_guides() CREA los joints leyendo el fichero JSON;
        NO busca en la escena, y cuando falla NO lanza excepción — devuelve None
        (por eso los pivotes se comprueban por valor, no por try/except).
        """
        # Get the joint guides
        self.leg_chain = guides_manager.get_guides(f"{self.side}_{self.LEG_PREFIX}{self.ROOT_JOINT}_JNT")
        cmds.parent(self.leg_chain[0], self.module_trn)

        # Get the settings guide (opcional: el caballo no lo trae en sus guias)
        self.settings_guide = guides_manager.get_guides(f"{self.side}_{self.LEG_PREFIX}Settings_LOCShape")

        
    def orient_guides(self):
        """
        Frames de cada guía a partir de sus POSICIONES, vía
        guides_manager.orient_guides: los calcula en Python y los HORNEA en un
        nodo network (nada de aimMatrix vivos), con el eje primario espejado en
        el lado R. La última guía conserva la rotación de la anterior con su
        propia posición — necesaria para los pivotes del pie reverso aunque no
        genere control FK.

        Deja en self:
            guides_matrices / guides_world_matrices   plugs world por guía
            point_matrices                            plugs solo-posición
            guides_local_matrices                     MMatrix relativas al padre
                                                      (horneadas: guías estáticas)
            reverse_foot_world_matrices               matrices de los pivotes
            settings_world_matrix                     matriz del settings

        Convención de ejes: el primario baja por el hueso (aim a la guía
        siguiente), el secundario al lateral FIJO del personaje — referencia
        fija y no el siguiente joint, que es lo que evita que la cadena se
        retuerza.
        """

        self.primary_axis = self.primaryInputAxis if self.side == "L" else tuple(-v for v in self.primaryInputAxis)
        self.secondary_axis = self.secondaryInputAxis
        lat = om.MVector(*self.primary_axis) ^ om.MVector(*self.secondary_axis)
        self.lateral_axis = (lat.x, lat.y, lat.z)
        self.aim_letter = "xyz"[max(range(3), key=lambda k: abs(self.primary_axis[k]))]

        self.guides_matrices, self.point_matrices = guides_manager.orient_guides(
            guides=self.leg_chain,
            primaryInputAxis=self.primary_axis,
            secondaryInputAxis=self.secondary_axis,
        )

        # Set the guides matrices for the chain
        self.guides_world_matrices = self.guides_matrices

        self.ctl_world_matrices = [self.ctl_matrix(cmds.getAttr(m)) for m in self.guides_matrices]
        self.guides_local_matrices = []
        for i, w_matrix in enumerate(self.ctl_world_matrices):
            if i == 0:
                local_matrix = w_matrix
            else:
                local_matrix = w_matrix * self.ctl_world_matrices[i - 1].inverse()
            self.guides_local_matrices.append(local_matrix)

        # Set the settings guide matrix (None si el personaje no trae la guia)
        self.settings_world_matrix = (cmds.xform(self.settings_guide, q=True, ws=True, m=True)
                                      if self.settings_guide else None)

    def ctl_matrix(self, matrix, world_frame=False):
        """
        Frame de colocación de un control. En R los controles van ESPEJADOS
        (det -1, eje principal a -1): el mismo valor de canal produce el
        movimiento espejo del lado L.
          - frames de GUIA R (vienen autorados como rotación 180 de L): los
            tres ejes negados.
          - frames de MUNDO (point matrix, identidad): solo el eje X negado.
        La traslación no se toca.
        """
        m = om.MMatrix(matrix)
        if self.side != "R":
            return m
        if world_frame:
            return om.MMatrix([-m[0], -m[1], -m[2], 0, m[4], m[5], m[6], 0,
                               m[8], m[9], m[10], 0, m[12], m[13], m[14], 1])
        return om.MMatrix([-m[0], -m[1], -m[2], 0, -m[4], -m[5], -m[6], 0,
                           -m[8], -m[9], -m[10], 0, m[12], m[13], m[14], 1])

    def setup_chain(self):
        """
        Índices y matrices de la cadena. GENÉRICO POR ÍNDICE — no hardcodees
        números de hueso: trasera y delantera tienen distinta longitud, y el
        perro y el caballo también.

        Calcula:
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
        self.leg_joints = self.leg_chain[:-1]  # todo menos el Tip
        self.tip_joint = self.leg_chain[-1]
        self.plant_index = len(self.leg_chain) - 2  # Pastern (pisada)
        self.leg_end_index = max(2, len(self.leg_chain) - 3)  # Fetlock (fin del IK principal)

        self.pv_apex_index = self.PV_APEX_INDEX if len(self.leg_chain) == self.STANDARD_JOINT_COUNT else 1
        self.pv_apex_index = max(1, min(self.pv_apex_index, self.leg_end_index - 1))

        self.world_positions = [om.MVector(cmds.xform(j, q=True, ws=True, t=True)) for j in self.leg_chain]
        side_vec = om.MVector(1, 0, 0) if self.side == "L" else om.MVector(-1, 0, 0)
        self.lateral_ref = -side_vec

        root_m = om.MMatrix(cmds.getAttr(self.guides_matrices[0]))
        lat_world = om.MVector(*self.lateral_axis) * om.MMatrix([
            root_m[0], root_m[1], root_m[2], 0, root_m[4], root_m[5], root_m[6], 0,
            root_m[8], root_m[9], root_m[10], 0, 0, 0, 0, 1])
        if (lat_world * self.lateral_ref) < 0:
            self.lateral_axis = tuple(-v for v in self.lateral_axis)

        root_p = self.world_positions[0]
        mid_p = self.world_positions[1]
        end_p = self.world_positions[self.leg_end_index]
        normal = (mid_p - root_p) ^ (end_p - root_p)
        self.plane_normal = normal.normal() if normal.length() > 1e-4 else om.MVector(self.lateral_ref)

        line = end_p - root_p
        self.leg_line_len = line.length()
        line_dir = line.normal() if self.leg_line_len > 1e-6 else om.MVector(0.0, 0.0, 1.0)
        bend_dir = self.lateral_ref ^ line_dir
        if bend_dir.length() < 1e-4:
            bend_dir = self.plane_normal ^ line_dir
        bend_dir.normalize()
        if (bend_dir * om.MVector(*self.FORWARD_AXIS)) < 0:
            bend_dir = -bend_dir
        self.bend_dir = bend_dir  

    def create_chains(self):
        """
        Cadena de joints IK a partir de los frames, encadenada por parentesco y
        con las transformaciones congeladas (makeIdentity) para que las
        rotaciones locales arranquen limpias.
        """
        cmds.select(clear=True)
        self.ik_chain = []

        for i , jnt in enumerate(self.leg_chain):

            jnt_suffix = jnt.split("_")[-1]
            ik_name = jnt.replace(f"_{jnt_suffix}",f"Ik_{jnt_suffix}")
            ik_jnt = cmds.joint(name=ik_name)

            cmds.xform(ik_jnt, ws=True, m=cmds.getAttr(self.guides_matrices[i]))

            self.ik_chain.append(ik_jnt)
            cmds.makeIdentity(ik_jnt, apply=True, rotate=True)

        cmds.parent(self.ik_chain[0], self.module_trn)
        

    # ═════════════════════════════════════════════════════════════════════════
    # CONTROLES
    # ═════════════════════════════════════════════════════════════════════════
    def controllers_creation(self):
        """
        Todos los controles del módulo, por matrices (nada de constraints):

        - Settings: canales bloqueados + switchIkFk (0 = IK), que conduce la
          visibilidad de FK directa y la de IK por un reverse.
        - FK: uno por joint de la pierna (sin el Tip), en cascada, colocados
          con la matriz LOCAL de su guía en el offsetParentMatrix del grupo.
          Guarda fk_controllers / fk_grps / fk_offs en paralelo.
        - IK: el rol "ankle" es el MASTER del pie — el ctl del FETLOCK
          (point matrix = orientado a mundo): lleva los atributos del pie y
          contiene la pila de pivotes del pie reverso. No hay control en el
          carpo/corvejón. El ball (Foot, sintético) vive en el MISMO punto que
          el fetlock, dentro del master a través de los pivotes: es lo que lee
          el handle manager y lo que rota el casco. Pv aparte.
          Acceso por ROL: self.ik_ctl["ball"] / ik_grp["pv"].

        Bloquea lo que el animador no debe tocar: escala y visibilidad siempre;
        en FK también la traslación.
        """
        # _____ Settings controller ____________________________________________
        self.settings_grp, self.settings_ctl = curve_tool.create_controller(name=f"{self.side}_{self.LEG_PREFIX}Settings", offset=["GRP"], locked_attrs=["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"], parent=self.controllers_grp, matrix=self.settings_world_matrix)
        cmds.addAttr(self.settings_ctl, longName="switchIkFk", niceName="Switch IK ------> FK", attributeType="float", defaultValue=0, maxValue=1, minValue=0, keyable=True) # Ik default
        # cmds.setAttr(f"{self.settings_ctl}.switchIkFk", keyable=True, channelBox=True, lock=False)
        
        # _____ Fk controllers creation ____________________________________________
        fk_controllers_trn = cmds.createNode("transform", name=f"{self.side}_{self.LEG_PREFIX}FkControllers_GRP", ss=True, p=self.controllers_grp)

        cmds.connectAttr(f"{self.settings_ctl}.switchIkFk", f"{fk_controllers_trn}.visibility")

        self.fk_controllers = []
        self.fk_grps = []
        self.fk_offs = []

        for i, jnt in enumerate(self.leg_joints):

            fk_controller_name = jnt.replace("_JNT", "Fk")
            parent = fk_controllers_trn if i == 0 else self.fk_controllers[-1]
            fk_grp, fk_ctl = curve_tool.create_controller(name=fk_controller_name, offset=["GRP", "OFF", "ANM"], locked_attrs=["tx", "ty", "tz", "sx", "sy", "sz", "v"], parent=parent)
            cmds.setAttr(f"{fk_grp[0]}.offsetParentMatrix", list(self.guides_local_matrices[i]), type="matrix")

            self.fk_controllers.append(fk_ctl)
            self.fk_grps.append(fk_grp[0])
            self.fk_offs.append(fk_grp[1])
            # Freeze all controllers
            cmds.xform(fk_grp[0], m=om.MMatrix.kIdentity)

        # _____ Ik controllers creation ____________________________________________
        ik_controllers_trn = cmds.createNode("transform", name=f"{self.side}_{self.LEG_PREFIX}IkControllers_GRP", ss=True, p=self.controllers_grp)
        reverse_vis_ik = cmds.createNode("reverse", name=f"{self.side}_{self.LEG_PREFIX}Vis_REV")
        cmds.connectAttr(f"{self.settings_ctl}.switchIkFk", f"{reverse_vis_ik}.inputX")
        cmds.connectAttr(f"{reverse_vis_ik}.outputX", f"{ik_controllers_trn}.visibility")

        self.ik_controllers_trn = ik_controllers_trn
        self.ik_ctl = {}
        self.ik_grp = {}

        # root
        root_grps, root_ctl = curve_tool.create_controller(
            name=self.leg_chain[0].replace("_JNT", "Ik"),
            offset=["GRP", "OFF", "ANM"], locked_attrs=["v"],
            parent=ik_controllers_trn,
            matrix=self.ctl_world_matrices[0],
        )
        self.ik_ctl["root"] = root_ctl
        self.ik_grp["root"] = root_grps[0]

        # ankle
        ankle_grps, ankle_ctl = curve_tool.create_controller(
            name=self.leg_chain[self.leg_end_index].replace("_JNT", "Ik"),
            offset=["GRP", "OFF", "ANM"], locked_attrs=["sx", "sy", "sz", "v"],
            parent=ik_controllers_trn,
            matrix=self.ctl_matrix(cmds.getAttr(self.point_matrices[self.leg_end_index]), world_frame=True),
        )
        self.ik_ctl["ankle"] = ankle_ctl
        self.ik_grp["ankle"] = ankle_grps[0]

        # ball
        ball_grps, ball_ctl = curve_tool.create_controller(
            name=f"{self.side}_{self.LEG_PREFIX}Foot",
            offset=["GRP", "OFF", "ANM"], locked_attrs=["sx", "sy", "sz", "v"],
            parent=ankle_ctl,
            matrix=self.ctl_matrix(cmds.getAttr(self.point_matrices[self.leg_end_index]), world_frame=True),
        )
        self.ik_ctl["ball"] = ball_ctl
        self.ik_grp["ball"] = ball_grps[0]

        pv_grps, pv_ctl = curve_tool.create_controller(
            name=f"{self.side}_{self.LEG_PREFIX}Pv",
            offset=["GRP", "OFF", "ANM"], locked_attrs=["sx","sy","sz","v"],
            parent=ik_controllers_trn,
        )
        self.ik_ctl["pv"] = pv_ctl
        self.ik_grp["pv"] = pv_grps[0]


    def fk_setup(self):
        """
        FK STRETCH por matrices. La cascada FK en sí ya quedó montada en
        controllers_creation (el blend lee el worldMatrix del control — no hay
        cadena FK de joints); aquí cada control recibe un atributo Stretch que
        reescala la traslación del grupo del SIGUIENTE control, reconstruyendo
        su offsetParentMatrix con un fourByFourMatrix.

        APLICADO AQUÍ (la trampa que costó un bug de 175u en el lado R): la
        longitud de reposo sale de LA MISMA CELDA de la matriz que se
        reconstruye (relative[12] -> in30), no se recalcula aparte — así no hay
        signo "de espejo" que adivinar y esa clase de bug desaparece entera.
        """

        # Fk stretch
        for i, ctl in enumerate(self.fk_controllers[:-1]):

            cmds.addAttr(self.fk_controllers[i], longName="extraAttr", niceName="EXTRA ATTRIBUTES ------", attributeType="enum", enumName="------", keyable=True)
            cmds.setAttr(f"{self.fk_controllers[i]}.extraAttr", ch=True, lock=True)
            cmds.addAttr(self.fk_controllers[i], longName="Stretch", attributeType="float", defaultValue=1, minValue=1, keyable=True)

            target_node = self.fk_grps[i + 1]
            relative = cmds.getAttr(f"{target_node}.offsetParentMatrix")
            rest_length = relative[12]
            
            label = f"Fk0{i}"  # por indice: sin nombre de hueso y sin duplicar el prefijo
            mult_node = cmds.createNode("multiply", n=f"{self.side}_{self.LEG_PREFIX}{label}Stretch_MUL", ss=True)
            cmds.connectAttr(f"{ctl}.Stretch", f"{mult_node}.input[0]")
            cmds.setAttr(f"{mult_node}.input[1]", rest_length)

            fbf = cmds.createNode("fourByFourMatrix", name=f"{self.side}_{self.LEG_PREFIX}{label}Stretch_FBF", ss=True)
            for row in range(4):
                for col in range(3):
                    cmds.setAttr(f"{fbf}.in{row}{col}", relative[row * 4 + col])
            cmds.connectAttr(f"{mult_node}.output", f"{fbf}.in30", force=True)
            cmds.connectAttr(f"{fbf}.output", f"{target_node}.offsetParentMatrix", force=True)

    # ═════════════════════════════════════════════════════════════════════════
    # IK — el corazón del experimento
    # ═════════════════════════════════════════════════════════════════════════
    def ik_setup(self):
        """
        Monta el IK según la config pedida. Este método es lo que hace que el
        capítulo 8 sea un EXPERIMENTO y no una demo: misma pierna, mismas
        guías, misma pose, solo cambia esto.

        Hace dos cosas:
        1. IK Handle Manager — el objetivo REAL del IK, común a todas las
           configs: offset horneado ankle->ball en reposo x worldMatrix vivo
           del ball (mover ankle O ball mueve el objetivo).
        2. Despacha por FICHAS: recorre IK_CONFIGS[self.solver] y por cada
           (start, end, solver) llama a _create_handle. Una combinación nueva
           es una entrada más en el dict, cero código.

        PENDIENTE:
        - La config "nodes" (triangle_solver) aún no entra por el dispatch.
        """
        ball_ctl = self.ik_ctl["ball"]
        end_rest = om.MMatrix(cmds.getAttr(self.guides_matrices[self.leg_end_index]))
        ball_wm = om.MMatrix(cmds.getAttr(f"{ball_ctl}.worldMatrix[0]"))

        ik_handle_mmx = cmds.createNode("multMatrix", name=f"{self.side}_{self.LEG_PREFIX}IkHandleManager_MMX")
        cmds.setAttr(f"{ik_handle_mmx}.matrixIn[0]", list(end_rest * ball_wm.inverse()), type="matrix")
        cmds.connectAttr(f"{ball_ctl}.worldMatrix[0]", f"{ik_handle_mmx}.matrixIn[1]")
        self.ik_handle_target = f"{ik_handle_mmx}.matrixSum"
        self._end_targets = {(self.leg_end_index, "foot"): self.ik_handle_target}

        root_ctl = self.ik_ctl["root"]
        root_rest_inv = om.MMatrix(cmds.getAttr(f"{root_ctl}.worldMatrix[0]")).inverse()
        root_follow_mmx = cmds.createNode("multMatrix", name=f"{self.side}_{self.LEG_PREFIX}IkRootFollow_MMX", ss=True)
        cmds.setAttr(f"{root_follow_mmx}.matrixIn[0]", list(root_rest_inv), type="matrix")
        cmds.connectAttr(f"{root_ctl}.worldMatrix[0]", f"{root_follow_mmx}.matrixIn[1]")
        cmds.connectAttr(f"{root_follow_mmx}.matrixSum", f"{self.ik_chain[0]}.offsetParentMatrix")

        cmds.joint(self.ik_chain[0], e=True, setPreferredAngles=True, children=True)

        self.ik_handles = []

        # config de nodos: sin handles ni constraint
        if self.solver == SOLVER_NODES:
            cmds.setAttr(f"{self.ik_chain[0]}.visibility", 0)
            self.pole_vector_setup()
            self._ik_nodes()
            return

        # Create the solver based on the argument given
        layers = self.IK_CONFIGS.get(self.solver)
        if layers is None:
            cmds.warning(f"[leg_module_self] solver '{self.solver}' sin ficha en IK_CONFIGS; usando 'spring'.")
            layers = self.IK_CONFIGS[SOLVER_SPRING]
        self.ik_handle_solvers = []
        for layer in layers:
            start, end, solver = layer[0], layer[1], layer[2]
            anchor = layer[3] if len(layer) > 3 else "foot"
            self._create_handle(start, end, solver, self._end_target(end, anchor))
            self.ik_handle_solvers.append(solver)
        # handle PRINCIPAL (PV, twist, soft, bias): el primero que no sea SC
        self.main_handle = next((h for h, sol in zip(self.ik_handles, self.ik_handle_solvers)
                                 if sol != "ikSCsolver"), self.ik_handles[0])

        # primer solve sin constraint: el spring captura su referencia de
        # plano en la primera evaluacion, y debe hacerlo en el reposo limpio
        for jnt in self.ik_chain:
            cmds.getAttr(f"{jnt}.worldMatrix[0]")

        self.pole_vector_setup()

        # bias del doblez: los dos slots del springAngleBias complementarios
        main_hdl = self.main_handle
        if cmds.attributeQuery("springAngleBias", node=main_hdl, exists=True):
            idx = cmds.getAttr(f"{main_hdl}.springAngleBias", multiIndices=True) or []
            if len(idx) >= 2:
                bias_plug = self.bend_bias_attr()
                bias_rev = cmds.createNode("reverse", name=f"{self.module_name}BendBias_REV", ss=True)
                cmds.connectAttr(bias_plug, f"{bias_rev}.inputX")
                cmds.connectAttr(bias_plug, f"{main_hdl}.springAngleBias[{idx[0]}].springAngleBias_FloatValue")
                cmds.connectAttr(f"{bias_rev}.outputX", f"{main_hdl}.springAngleBias[{idx[-1]}].springAngleBias_FloatValue")

        # canales de los handles clavados a 0 por conexion
        cmds.loadPlugin("lookdevKit", quiet=True)  # floatConstant vive ahi
        freeze_fcn = cmds.createNode("floatConstant", name=f"{self.module_name}HandleFreeze_FCN", ss=True)
        cmds.setAttr(f"{freeze_fcn}.inFloat", 0)
        for handle in self.ik_handles:
            for attr in ("translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ"):
                cmds.connectAttr(f"{freeze_fcn}.outFloat", f"{handle}.{attr}")

    def bend_bias_attr(self):
        """
        Reparto del doblez entre las dos articulaciones interiores: una cadena
        de 3 huesos con raíz y pie clavados tiene UN grado de libertad
        redundante, y este atributo es ese DOF. 0.5 = reparto natural del
        solver (el reposo no se mueve); subirlo carga el doblez arriba
        (babilla/codo), bajarlo abajo (corvejón/carpo). Mismo dial en spring
        (springAngleBias) y en nodos (la cuerda).
        """
        foot_ctl = self.ik_ctl["ankle"]
        cmds.addAttr(foot_ctl, longName="BEND", niceName="BEND ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{foot_ctl}.BEND", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(foot_ctl, longName="Bend_Bias", attributeType="float", minValue=0, maxValue=1, defaultValue=0.5, keyable=True)
        return f"{foot_ctl}.Bend_Bias"

    def _end_target(self, end_index, anchor="foot"):
        """
        Objetivo de un handle segun de que cuelga su articulacion final:
          - "foot": reposo x ball_rest^-1 x ball vivo (sigue al pie). Para el
            handle principal y los SC del pie.
          - "root": reposo x root_rest^-1 x root vivo (sigue a la raiz de la
            pierna). Para un SC intermedio que debe quedar RIGIDO al cuerpo (no
            arrastrarse con el pie): asi el tramo de abajo puede comprimirse y
            doblar la articulacion del RP.
        En reposo ambos son exactos (los offsets se hornean sobre las guias).
        """
        key = (end_index, anchor)
        if key in self._end_targets:
            return self._end_targets[key]
        end_rest = om.MMatrix(cmds.getAttr(self.guides_matrices[end_index]))
        drive_ctl = self.ik_ctl["root"] if anchor == "root" else self.ik_ctl["ball"]
        drive_rest = om.MMatrix(cmds.getAttr(f"{drive_ctl}.worldMatrix[0]"))
        label = self.leg_chain[end_index].split("_")[1].replace(self.LEG_PREFIX, "")
        mmx = cmds.createNode("multMatrix", name=f"{self.module_name}{label}{anchor.capitalize()}Target_MMX", ss=True)
        cmds.setAttr(f"{mmx}.matrixIn[0]", list(end_rest * drive_rest.inverse()), type="matrix")
        cmds.connectAttr(f"{drive_ctl}.worldMatrix[0]", f"{mmx}.matrixIn[1]")
        self._end_targets[key] = f"{mmx}.matrixSum"
        return self._end_targets[key]

    def _create_handle(self, start_index, end_index, solver, target_plug):
        """
        Un ikHandle del joint start al end de la cadena IK, con el objetivo
        conectado a su offsetParentMatrix. Carga el plugin del spring si la
        ficha lo pide y acumula en self.ik_handles.

        El handle nace con la traslacion del efector en canales: se aparca y
        se ponen a 0 ANTES de conectar el objetivo al opm, o queda doblado y
        el spring cachea el plano con esa posicion.
        """
        if solver == "ikSpringSolver":
            cmds.loadPlugin("ikSpringSolver", quiet=True)
            if not cmds.objExists("ikSpringSolver"):
                mel.eval("ikSpringSolver;")

        start_joint = self.ik_chain[start_index]
        end_joint = self.ik_chain[end_index]

        label = end_joint.split("_")[1].replace("Ik", "")
        ik_handle = cmds.ikHandle(name=f"{self.side}_{label}Ik_HDL", startJoint=start_joint, endEffector=end_joint, solver=solver)[0]
        cmds.parent(ik_handle, self.module_trn)
        for attr in ("translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ"):
            cmds.setAttr(f"{ik_handle}.{attr}", 0)
        cmds.connectAttr(target_plug, f"{ik_handle}.offsetParentMatrix")

        self.ik_handles.append(ik_handle)
        return ik_handle

    def pole_vector_setup(self):
        """
        Pole vector del handle PRINCIPAL (ik_handles[0]) — solo uno: el SC del
        pie lo ignora y en RP el segundo handle no lo necesita.

        El control Pv se coloca geometricamente FUERA del plano, en el apex
        (pv_apex_index: la articulacion media del zigzag) + bend_dir * media
        longitud * PV_SIGN — sobre la direccion automatica del solver: con los
        preferred angles puestos, el poleVectorConstraint asi colocado no mueve
        el reposo (patron _place_pv de la referencia).

        La posicion va al offsetParentMatrix del GRUPO como CONEXION
        (composeMatrix): canales limpios, y space_switches la lee como base del
        sistema de espacios. El PV sigue al PIE por defecto (walk cycle sin
        perseguirlo a mano), con root como alternativa y el masterwalk como
        espacio maestro del propio switch.
        """
        apex_p = self.world_positions[self.pv_apex_index]
        pv_pos = apex_p + self.bend_dir * (self.leg_line_len * 0.5) * self.PV_SIGN

        pv_rest_cmx = cmds.createNode("composeMatrix", name=f"{self.side}_{self.LEG_PREFIX}PvRest_CMX", ss=True)
        cmds.setAttr(f"{pv_rest_cmx}.inputTranslate", pv_pos.x, pv_pos.y, pv_pos.z, type="double3")
        if self.side == "R":
            cmds.setAttr(f"{pv_rest_cmx}.inputScaleX", -1)
        cmds.connectAttr(f"{pv_rest_cmx}.outputMatrix", f"{self.ik_grp['pv']}.offsetParentMatrix")

        matrix_manager.space_switches(
            target=self.ik_ctl["pv"],
            sources=[self.ik_ctl["ankle"], self.ik_ctl["root"]],
            sources_names=["foot", "root"],
            default_rotate=1, default_translate=1,
            pv=True,
        )

        # el constraint el ultimo, con el PV ya en su red definitiva
        cmds.getAttr(f"{self.ik_ctl['pv']}.worldMatrix[0]")
        if self.ik_handles:
            cmds.poleVectorConstraint(self.ik_ctl["pv"], self.main_handle)
            self.pole_vector_line(f"{self.ik_chain[self.pv_apex_index]}.worldMatrix[0]")

    def pole_vector_line(self, apex_plug):
        """Línea de dos CVs del apex al Pv."""
        pv_ctl = self.ik_ctl["pv"]
        crv = cmds.curve(d=1, p=[(0, 0, 1), (0, 1, 0)], n=f"{self.side}_{self.LEG_PREFIX}Pv_CRV")
        row_apex = cmds.createNode("rowFromMatrix", name=f"{self.side}_{self.LEG_PREFIX}PvApex_RFM", ss=True)
        row_ctl = cmds.createNode("rowFromMatrix", name=f"{self.side}_{self.LEG_PREFIX}PvCtl_RFM", ss=True)
        cmds.setAttr(f"{row_apex}.input", 3)
        cmds.setAttr(f"{row_ctl}.input", 3)
        cmds.connectAttr(apex_plug, f"{row_apex}.matrix")
        cmds.connectAttr(f"{pv_ctl}.worldMatrix[0]", f"{row_ctl}.matrix")
        for axis, value in zip("XYZ", ("xValue", "yValue", "zValue")):
            cmds.connectAttr(f"{row_apex}.output{axis}", f"{crv}.controlPoints[0].{value}")
            cmds.connectAttr(f"{row_ctl}.output{axis}", f"{crv}.controlPoints[1].{value}")
        cmds.setAttr(f"{crv}.inheritsTransform", 0)
        cmds.setAttr(f"{crv}.overrideEnabled", 1)
        cmds.setAttr(f"{crv}.overrideDisplayType", 1)
        cmds.parent(crv, pv_ctl)
        cmds.setAttr(f"{crv}.hiddenInOutliner", 1)
        for shape in cmds.listRelatives(crv, shapes=True) or []:
            cmds.setAttr(f"{shape}.isHistoricallyInteresting", 0)

    def _ik_nodes(self):
        """
        CONFIG C — IK analítico por nodos (teorema del coseno).

        Es tu aportación del cap. 6.2. Ventaja teórica: cacheable, paralelizable,
        sin plugin. Coste: el polo vector y el up vector hay que resolverlos a
        mano.

        DOS TRIÁNGULOS ENCADENADOS al mismo objetivo, en el mismo plano (el
        del pole vector):
            1. lados (fémur, CUERDA) desde la raíz  -> coloca la babilla
            2. lados (tibia, caña) desde la babilla -> coloca el corvejón
        La CUERDA (babilla->objetivo) es la ley de reparto del doblez — el
        papel del springAngleBias en el spring nativo. Es VIVA: escala con la
        distancia raíz->objetivo (a distancia de reposo vale la cuerda de
        reposo -> reposo exacto sin calibración) y se clampa al rango físico
        de tibia+caña. Con cuerda FIJA el ángulo del corvejón queda congelado
        y la config se comporta como RP+SC, no como spring.

        Salida: self.nodes_ik_world (plugs de matriz world por joint) que el
        blend_setup consume en lugar de la cadena ik.

        Mídelo honestamente. El resultado puede perfectamente ser que el nativo
        ya lo resuelve mejor — y eso, MEDIDO, es un resultado publicable, no un
        fracaso. Un TFG que reporta un resultado negativo con datos es más
        sólido que uno que solo enseña lo que le salió bien.

        Stretch y soft los conduce ik_stretch_soft: las longitudes de la red
        son plugs (floatConstant) que el stretch multiplica, y el soft
        recoloca el objetivo que lee la red.

        PENDIENTE:
        - atributo de BIAS sobre la escala de la cuerda (reparto animable,
          comparable al springAngleBias)
        - twist alrededor de la línea raíz->objetivo (atributo en el master)
        - verificar el signo del doblez del corvejón en una pose extrema
        """
        cmds.loadPlugin("matrixNodes", quiet=True)
        cmds.loadPlugin("lookdevKit", quiet=True)

        n = self.module_name
        p = self.world_positions
        end = self.leg_end_index
        a_len = (p[1] - p[0]).length()            # fémur / húmero+radio según cadena
        b_len = (p[2] - p[1]).length()            # tibia
        c_len = (p[end] - p[2]).length()          # caña
        q_len = (p[end] - p[1]).length()          # cuerda de reposo
        d_rest = (p[end] - p[0]).length()         # distancia raíz->objetivo de reposo

        # ── helpers de red ──────────────────────────────────────────────────
        def _dcm(label, matrix_plug):
            node = cmds.createNode("decomposeMatrix", name=f"{n}{label}_DCM", ss=True)
            cmds.connectAttr(matrix_plug, f"{node}.inputMatrix")
            return f"{node}.outputTranslate"

        def _f(label, op, in_a, in_b):
            # floatMath
            node = cmds.createNode("floatMath", name=f"{n}{label}_FLM", ss=True)
            cmds.setAttr(f"{node}.operation", op)
            for attr, v in (("floatA", in_a), ("floatB", in_b)):
                if isinstance(v, str):
                    cmds.connectAttr(v, f"{node}.{attr}")
                else:
                    cmds.setAttr(f"{node}.{attr}", v)
            return f"{node}.outFloat"

        def _sub(label, va, vb):
            node = cmds.createNode("plusMinusAverage", name=f"{n}{label}_PMA", ss=True)
            cmds.setAttr(f"{node}.operation", 2)
            cmds.connectAttr(va, f"{node}.input3D[0]")
            cmds.connectAttr(vb, f"{node}.input3D[1]")
            return f"{node}.output3D"

        def _add(label, vectors):
            node = cmds.createNode("plusMinusAverage", name=f"{n}{label}_PMA", ss=True)
            for i, v in enumerate(vectors):
                cmds.connectAttr(v, f"{node}.input3D[{i}]")
            return f"{node}.output3D"

        def _dist(label, va, vb):
            node = cmds.createNode("distanceBetween", name=f"{n}{label}_DBT", ss=True)
            cmds.connectAttr(va, f"{node}.point1")
            cmds.connectAttr(vb, f"{node}.point2")
            return f"{node}.distance"

        def _scale(label, vec, scalar):
            node = cmds.createNode("multiplyDivide", name=f"{n}{label}_MDV", ss=True)
            cmds.connectAttr(vec, f"{node}.input1")
            for ax in "XYZ":
                cmds.connectAttr(scalar, f"{node}.input2{ax}")
            return f"{node}.output"

        def _cross(label, va, vb):
            node = cmds.createNode("vectorProduct", name=f"{n}{label}_VCP", ss=True)
            cmds.setAttr(f"{node}.operation", 2)
            cmds.setAttr(f"{node}.normalizeOutput", 1)
            cmds.connectAttr(va, f"{node}.input1")
            cmds.connectAttr(vb, f"{node}.input2")
            return f"{node}.output"

        A = _dcm("NodesRoot", f"{self.ik_ctl['root']}.worldMatrix[0]")
        D = _dcm("NodesTarget", self.ik_handle_target)
        self.nodes_target_dcm = f"{n}NodesTarget_DCM"
        P = _dcm("NodesPole", f"{self.ik_ctl['pv']}.worldMatrix[0]")

        def _lenc(label, value):
            node = cmds.createNode("floatConstant", name=f"{n}{label}_FCN", ss=True)
            cmds.setAttr(f"{node}.inFloat", value)
            return f"{node}.outFloat"

        len_a = _lenc("NodesLenA", a_len)
        len_b = _lenc("NodesLenB", b_len)
        len_c = _lenc("NodesLenC", c_len)
        self.nodes_length_inputs = [plug.replace(".outFloat", ".inFloat")
                                    for plug in (len_a, len_b, len_c)]

        d1_raw = _dist("NodesD1", A, D)

        bc_sum = _f("NodesLenBC", 0, len_b, len_c)
        bc_hi = _f("NodesChordHi", 1, bc_sum, 1e-3)
        bc_lo = _f("NodesChordLo", 0,
                   _f("NodesLenBCDifAbs", 5, _f("NodesLenBCDif1", 1, len_b, len_c),
                      _f("NodesLenBCDif2", 1, len_c, len_b)), 1e-3)

        chord_fold = _f("NodesChordScale", 2, d1_raw, q_len / d_rest)

        total_live = _f("NodesLenTotal", 0, len_a, bc_sum)
        ext_den = _f("NodesChordExtDen", 5, _f("NodesChordExtRange", 1, total_live, d_rest), 1e-3)
        ext_t_raw = _f("NodesChordExtT", 3, _f("NodesChordExtNum", 1, d1_raw, d_rest), ext_den)
        ext_t = _f("NodesChordExtTHi", 4, _f("NodesChordExtTLo", 5, ext_t_raw, 0.0), 1.0)
        chord_ext = _f("NodesChordExt", 0, q_len,
                       _f("NodesChordExtGain", 2, ext_t, _f("NodesChordExtSpan", 1, bc_sum, q_len)))

        chord_cnd = cmds.createNode("condition", name=f"{n}NodesChord_CND", ss=True)
        cmds.setAttr(f"{chord_cnd}.operation", 2)  # d > d_rest -> tramo de extensión
        cmds.connectAttr(d1_raw, f"{chord_cnd}.firstTerm")
        cmds.setAttr(f"{chord_cnd}.secondTerm", d_rest)
        cmds.connectAttr(chord_ext, f"{chord_cnd}.colorIfTrueR")
        cmds.connectAttr(chord_fold, f"{chord_cnd}.colorIfFalseR")

        chord = _f("NodesChordClampHi", 4, _f("NodesChordClampLo", 5, f"{chord_cnd}.outColorR", bc_lo), bc_hi)

        # bias
        bias_plug = self.bend_bias_attr()
        up_t = _f("NodesBiasUpT", 2, _f("NodesBiasUpMax", 5, _f("NodesBiasUp", 1, bias_plug, 0.5), 0.0), 2.0)
        dn_t = _f("NodesBiasDnT", 2, _f("NodesBiasDnMax", 5, _f("NodesBiasDn", 1, 0.5, bias_plug), 0.0), 2.0)
        hi_gain = _f("NodesBiasHiGain", 2, up_t, _f("NodesBiasHiSpan", 1, bc_hi, chord))
        lo_gain = _f("NodesBiasLoGain", 2, dn_t, _f("NodesBiasLoSpan", 1, chord, bc_lo))
        chord = _f("NodesBiasChord", 1, _f("NodesBiasChordUp", 0, chord, hi_gain), lo_gain)

        reach_lo = _f("NodesBiasReachLo", 0,
                      _f("NodesBiasDAbs", 5, _f("NodesBiasDA1", 1, d1_raw, len_a),
                         _f("NodesBiasDA2", 1, len_a, d1_raw)), 1e-3)
        reach_hi = _f("NodesBiasReachHi", 1, _f("NodesBiasDA3", 0, d1_raw, len_a), 1e-3)
        chord = _f("NodesBiasReachMax", 5, _f("NodesBiasReachMin", 4, chord, reach_hi), reach_lo)

        # alcance del triángulo 1: |a-q| < d < a+q
        aq_hi = _f("NodesD1Hi", 1, _f("NodesLenAQ", 0, len_a, chord), 1e-3)
        aq_lo = _f("NodesD1Lo", 0,
                   _f("NodesLenAQDifAbs", 5, _f("NodesLenAQDif1", 1, len_a, chord),
                      _f("NodesLenAQDif2", 1, chord, len_a)), 1e-3)
        d1 = _f("NodesD1Max", 4, _f("NodesD1Min", 5, d1_raw, aq_lo), aq_hi)
        u1 = _scale("NodesU1", _sub("NodesAD", D, A), _f("NodesD1Inv", 3, 1.0, d1_raw))
        n_hat = _cross("NodesN", u1, _sub("NodesAP", P, A))
        v1 = _cross("NodesV1", n_hat, u1)

        def _bend_point(label, root_pt, dist_plug, u_dir, v_dir, side_a, side_b, bend_sign):
            """Ley de cosenos: punto doblado a side_a del root, en el plano (û,v̂).
            side_a/side_b aceptan valor o plug (las longitudes vienen del stretch)."""
            d2 = _f(f"{label}DistSq", 2, dist_plug, dist_plug)
            a2 = _f(f"{label}ASq", 2, side_a, side_a)
            b2 = _f(f"{label}BSq", 2, side_b, side_b)
            num = _f(f"{label}Num", 0, d2, _f(f"{label}ASqMinusBSq", 1, a2, b2))
            den = _f(f"{label}Den", 2, _f(f"{label}DenAD", 2, dist_plug, side_a), 2.0)
            cos_raw = _f(f"{label}Cos", 3, num, den)
            cos_cl = _f(f"{label}CosMax", 5, _f(f"{label}CosMin", 4, cos_raw, 1.0), -1.0)
            sin_sq = _f(f"{label}SinSq", 5, _f(f"{label}OneMinus", 1, 1.0, _f(f"{label}CosSq", 2, cos_cl, cos_cl)), 0.0)
            sin_v = _f(f"{label}Sin", 6, sin_sq, 0.5)
            along = _scale(f"{label}Along", u_dir, _f(f"{label}AlongLen", 2, cos_cl, side_a))
            lift_len = _f(f"{label}LiftLen", 2, sin_v, side_a)
            if bend_sign < 0:
                lift_len = _f(f"{label}LiftNeg", 2, lift_len, -1.0)
            lift = _scale(f"{label}Lift", v_dir, lift_len)
            return _add(f"{label}Point", [root_pt, along, lift])

        # signo de cada doblez medido en las guías (lado de la línea en el
        # plano del Pv)
        line_u = (p[end] - p[0]).normal()
        pv_p = om.MVector(cmds.xform(self.ik_ctl["pv"], q=True, ws=True, t=True))
        plane_v = (line_u ^ (pv_p - p[0])) ^ line_u
        plane_v.normalize()
        sign_1 = 1.0 if ((p[1] - p[0]) * plane_v) >= 0 else -1.0
        line_u2 = (p[end] - p[1]).normal()
        plane_v2 = (line_u2 ^ plane_v) ^ line_u2
        plane_v2.normalize()
        sign_2 = 1.0 if ((p[2] - p[1]) * plane_v2) >= 0 else -1.0

        # triángulo 1
        B = _bend_point("NodesT1", A, d1, u1, v1, len_a, chord, sign_1)
        
        # triángulo 2
        d2_raw = _dist("NodesD2", B, D)
        d2 = _f("NodesD2Max", 4, _f("NodesD2Min", 5, d2_raw, bc_lo), bc_hi)
        u2 = _scale("NodesU2", _sub("NodesBD", D, B), _f("NodesD2Inv", 3, 1.0, d2_raw))
        v2 = _cross("NodesV2", n_hat, u2)
        C = _bend_point("NodesT2", B, d2, u2, v2, len_b, len_c, sign_2)

        def _cmp(label, vec):
            node = cmds.createNode("composeMatrix", name=f"{n}{label}_CMX", ss=True)
            cmds.connectAttr(vec, f"{node}.inputTranslate")
            return f"{node}.outputMatrix"

        cmp_a, cmp_b, cmp_c, cmp_d = (_cmp(l, v) for l, v in
                                      (("NodesA", A), ("NodesB", B), ("NodesC", C), ("NodesD", D)))
        root_guide = om.MMatrix(cmds.getAttr(self.guides_matrices[0]))
        lat_local = om.MVector(*self.lateral_axis)
        guide_lat = om.MVector(
            lat_local.x * root_guide[0] + lat_local.y * root_guide[4] + lat_local.z * root_guide[8],
            lat_local.x * root_guide[1] + lat_local.y * root_guide[5] + lat_local.z * root_guide[9],
            lat_local.x * root_guide[2] + lat_local.y * root_guide[6] + lat_local.z * root_guide[10])
        n_rest = (line_u ^ (pv_p - p[0])).normal()
        lat_sign = 1.0 if (guide_lat * n_rest) >= 0 else -1.0
        sec_axis_lat = tuple(v * lat_sign for v in self.lateral_axis)

        def _aim(label, base_mtx, target_mtx):
            node = cmds.createNode("aimMatrix", name=f"{n}{label}_AMX", ss=True)
            cmds.connectAttr(base_mtx, f"{node}.inputMatrix")
            cmds.connectAttr(target_mtx, f"{node}.primaryTargetMatrix")
            cmds.setAttr(f"{node}.primaryInputAxis", *self.primary_axis, type="double3")
            cmds.connectAttr(n_hat, f"{node}.secondaryTargetVector")
            cmds.setAttr(f"{node}.secondaryInputAxis", *sec_axis_lat, type="double3")
            cmds.setAttr(f"{node}.secondaryMode", 2)
            return f"{node}.outputMatrix"

        aim_a = _aim("NodesRootFrame", cmp_a, cmp_b)
        aim_b = _aim("NodesMidFrame", cmp_b, cmp_c)
        aim_c = _aim("NodesLowFrame", cmp_c, cmp_d)

        c_rest = om.MMatrix(cmds.getAttr(aim_c))
        d_guide_rest = om.MMatrix(cmds.getAttr(self.guides_matrices[end]))
        d_mmx = cmds.createNode("multMatrix", name=f"{n}NodesEndFrame_MMX", ss=True)
        cmds.setAttr(f"{d_mmx}.matrixIn[0]", list(d_guide_rest * c_rest.inverse()), type="matrix")
        cmds.connectAttr(aim_c, f"{d_mmx}.matrixIn[1]")

        dcd = _dist("NodesDC", C, D)
        u_cd = _scale("NodesUCD", _sub("NodesCD", D, C), _f("NodesDCInv", 3, 1.0, dcd))
        end_pt = _add("NodesEndPoint", [C, _scale("NodesEndOff", u_cd, len_c)])
        end_rot = cmds.createNode("pickMatrix", name=f"{n}NodesEndRot_PMX", ss=True)
        for at in ("useTranslate", "useScale", "useShear"):
            cmds.setAttr(f"{end_rot}.{at}", 0)
        cmds.connectAttr(f"{d_mmx}.matrixSum", f"{end_rot}.inputMatrix")
        end_mmx = cmds.createNode("multMatrix", name=f"{n}NodesEndPos_MMX", ss=True)
        cmds.connectAttr(f"{end_rot}.outputMatrix", f"{end_mmx}.matrixIn[0]")
        cmds.connectAttr(_cmp("NodesEnd", end_pt), f"{end_mmx}.matrixIn[1]")

        plant_rest = om.MMatrix(cmds.getAttr(self.guides_matrices[self.plant_index]))
        plant_mmx = cmds.createNode("multMatrix", name=f"{n}NodesPlantFrame_MMX", ss=True)
        cmds.setAttr(f"{plant_mmx}.matrixIn[0]", list(plant_rest * d_guide_rest.inverse()), type="matrix")
        cmds.connectAttr(f"{end_mmx}.matrixSum", f"{plant_mmx}.matrixIn[1]")

        self.nodes_ik_world = [aim_a, aim_b, aim_c,
                               f"{end_mmx}.matrixSum", f"{plant_mmx}.matrixSum"]
        self.pole_vector_line(self.nodes_ik_world[self.pv_apex_index])

    def ik_stretch_soft(self):
        """
        Stretch (escala del segmento por ratio distancia/longitud, normalizado
        por globalScale) y soft IK (amortiguación exponencial al acercarse a la
        extensión máxima).

        Ambos APAGADOS por defecto: son decisión del animador, no del rig.

        Expone en el control del pie: Stretch (0-1), un length mult por
        segmento, Soft (0-1) y Soft_Start. La distancia va normalizada por el
        globalScale del masterwalk; el stretch reescala el translateX de cada
        joint IK; el soft recoloca el PRIMER handle (composeMatrix x aimMatrix,
        sin DAG).

        Contrato con ik_setup: usa self.ik_handle_target si existe; si no, cae
        al worldMatrix del control del pie (peor: ignora el pie reverso).

        Nota para el cap. 8: el stretch es también el escape cuando la cadena se
        queda sin alcance. Si mides un pivote o un muelle y "no llega",
        comprueba si es ALCANCE antes de culpar al mecanismo.

        En la config de nodos no hay handle: el stretch conduce las longitudes
        de la red (plugs) y el soft recoloca el OBJETIVO que lee la red.
        """
        foot_ctl = self.ik_ctl["ankle"]
        root_ctl = self.ik_ctl["root"]
        ik_target_plug = getattr(self, "ik_handle_target", f"{foot_ctl}.worldMatrix[0]")
        segment_count = self.leg_end_index
        rest_lengths = [
            (self.world_positions[i + 1] - self.world_positions[i]).length()
            for i in range(segment_count)
        ]

        if segment_count == 2:
            mult_names = ["upperLengthMult", "lowerLengthMult"]
        elif segment_count == 3:
            mult_names = ["upperLengthMult", "middleLengthMult", "lowerLengthMult"]
        else:
            mult_names = [f"segment0{i}LengthMult" for i in range(segment_count)]

        cmds.addAttr(foot_ctl, longName="STRETCHY", niceName="STRETCHY ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{foot_ctl}.STRETCHY", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(foot_ctl, longName="Stretch", attributeType="float", minValue=0, maxValue=1, defaultValue=0, keyable=True)
        for name in mult_names:
            cmds.addAttr(foot_ctl, longName=name, attributeType="float", minValue=0.001, defaultValue=1, keyable=True)

        cmds.addAttr(foot_ctl, longName="SOFT", niceName="SOFT ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{foot_ctl}.SOFT", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(foot_ctl, longName="Soft", attributeType="float", minValue=0, maxValue=1, defaultValue=0, keyable=True)
        cmds.addAttr(foot_ctl, longName="Soft_Start", attributeType="float", minValue=0.001, maxValue=1, defaultValue=0.8, keyable=True)

        # ----- Distancia normalizada por globalScale -----
        current_dbt = cmds.createNode("distanceBetween", name=f"{self.module_name}CurrentLength_DBT", ss=True)
        cmds.connectAttr(f"{root_ctl}.worldMatrix[0]", f"{current_dbt}.inMatrix1")
        cmds.connectAttr(ik_target_plug, f"{current_dbt}.inMatrix2")

        distance_div = cmds.createNode("divide", name=f"{self.module_name}GlobalScale_DIV", ss=True)
        cmds.connectAttr(f"{current_dbt}.distance", f"{distance_div}.input1")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{distance_div}.input2")
        distance_plug = f"{distance_div}.output"

        # ----- Longitud total -----
        length_sum = cmds.createNode("sum", name=f"{self.module_name}TotalLength_SUM", ss=True)
        for i, (rest, mult_name) in enumerate(zip(rest_lengths, mult_names)):
            segment_mul = cmds.createNode("multiply", name=f"{self.module_name}Segment0{i}Length_MUL", ss=True)
            cmds.setAttr(f"{segment_mul}.input[0]", rest)
            cmds.connectAttr(f"{foot_ctl}.{mult_name}", f"{segment_mul}.input[1]")
            cmds.connectAttr(f"{segment_mul}.output", f"{length_sum}.input[{i}]")
        length_plug = f"{length_sum}.output"

        # ----- Stretch -----
        ratio_div = cmds.createNode("divide", name=f"{self.module_name}LengthRatio_DIV", ss=True)
        cmds.connectAttr(distance_plug, f"{ratio_div}.input1")
        cmds.connectAttr(length_plug, f"{ratio_div}.input2")

        ratio_max = cmds.createNode("max", name=f"{self.module_name}LengthRatio_MAX", ss=True)
        cmds.setAttr(f"{ratio_max}.input[0]", 1)
        cmds.connectAttr(f"{ratio_div}.output", f"{ratio_max}.input[1]")

        stretch_remap = cmds.createNode("remapValue", name=f"{self.module_name}Stretch_RMV", ss=True)
        cmds.connectAttr(f"{foot_ctl}.Stretch", f"{stretch_remap}.inputValue")
        cmds.setAttr(f"{stretch_remap}.outputMin", 1)
        cmds.connectAttr(f"{ratio_max}.output", f"{stretch_remap}.outputMax")

        for i in range(1, segment_count + 1):
            rest_tx = cmds.getAttr(f"{self.ik_chain[i]}.translateX")
            joint_mul = cmds.createNode("multiply", name=f"{self.module_name}Stretch0{i}_MUL", ss=True)
            cmds.setAttr(f"{joint_mul}.input[0]", rest_tx)
            cmds.connectAttr(f"{stretch_remap}.outValue", f"{joint_mul}.input[1]")
            cmds.connectAttr(f"{foot_ctl}.{mult_names[i - 1]}", f"{joint_mul}.input[2]")
            cmds.connectAttr(f"{joint_mul}.output", f"{self.ik_chain[i]}.translateX")

        if getattr(self, "nodes_length_inputs", None):
            for i, len_input in enumerate(self.nodes_length_inputs):
                len_mul = cmds.createNode("multiply", name=f"{self.module_name}NodesLen0{i}Stretch_MUL", ss=True)
                cmds.setAttr(f"{len_mul}.input[0]", rest_lengths[i])
                cmds.connectAttr(f"{stretch_remap}.outValue", f"{len_mul}.input[1]")
                cmds.connectAttr(f"{foot_ctl}.{mult_names[i]}", f"{len_mul}.input[2]")
                cmds.connectAttr(f"{len_mul}.output", len_input, force=True)

        # ----- Soft -----
        soft_start_mul = cmds.createNode("multiply", name=f"{self.module_name}SoftStart_MUL", ss=True)
        cmds.connectAttr(f"{foot_ctl}.Soft_Start", f"{soft_start_mul}.input[0]")
        cmds.connectAttr(length_plug, f"{soft_start_mul}.input[1]")

        soft_range_sub = cmds.createNode("subtract", name=f"{self.module_name}SoftRange_SUB", ss=True)
        cmds.connectAttr(length_plug, f"{soft_range_sub}.input1")
        cmds.connectAttr(f"{soft_start_mul}.output", f"{soft_range_sub}.input2")

        soft_delta_sub = cmds.createNode("subtract", name=f"{self.module_name}SoftDelta_SUB", ss=True)
        cmds.connectAttr(distance_plug, f"{soft_delta_sub}.input1")
        cmds.connectAttr(f"{soft_start_mul}.output", f"{soft_delta_sub}.input2")

        soft_exponent_div = cmds.createNode("divide", name=f"{self.module_name}SoftExponent_DIV", ss=True)
        cmds.connectAttr(f"{soft_delta_sub}.output", f"{soft_exponent_div}.input1")
        cmds.connectAttr(f"{soft_range_sub}.output", f"{soft_exponent_div}.input2")

        soft_exponent_neg = cmds.createNode("negate", name=f"{self.module_name}SoftExponent_NEG", ss=True)
        cmds.connectAttr(f"{soft_exponent_div}.output", f"{soft_exponent_neg}.input")

        soft_exp_pow = cmds.createNode("power", name=f"{self.module_name}SoftExp_POW", ss=True)
        cmds.setAttr(f"{soft_exp_pow}.input", math.e)
        cmds.connectAttr(f"{soft_exponent_neg}.output", f"{soft_exp_pow}.exponent")

        soft_one_minus = cmds.createNode("subtract", name=f"{self.module_name}SoftOneMinusExp_SUB", ss=True)
        cmds.setAttr(f"{soft_one_minus}.input1", 1)
        cmds.connectAttr(f"{soft_exp_pow}.output", f"{soft_one_minus}.input2")

        soft_falloff_mul = cmds.createNode("multiply", name=f"{self.module_name}SoftFalloff_MUL", ss=True)
        cmds.connectAttr(f"{soft_range_sub}.output", f"{soft_falloff_mul}.input[0]")
        cmds.connectAttr(f"{soft_one_minus}.output", f"{soft_falloff_mul}.input[1]")

        soft_distance_sum = cmds.createNode("sum", name=f"{self.module_name}SoftDistance_SUM", ss=True)
        cmds.connectAttr(f"{soft_start_mul}.output", f"{soft_distance_sum}.input[0]")
        cmds.connectAttr(f"{soft_falloff_mul}.output", f"{soft_distance_sum}.input[1]")

        soft_condition = cmds.createNode("condition", name=f"{self.module_name}Soft_CON", ss=True)
        cmds.setAttr(f"{soft_condition}.operation", 2)  # Greater than
        cmds.connectAttr(distance_plug, f"{soft_condition}.firstTerm")
        cmds.connectAttr(f"{soft_start_mul}.output", f"{soft_condition}.secondTerm")
        cmds.connectAttr(f"{soft_distance_sum}.output", f"{soft_condition}.colorIfTrueR")
        cmds.connectAttr(distance_plug, f"{soft_condition}.colorIfFalseR")

        soft_blend = cmds.createNode("blendTwoAttr", name=f"{self.module_name}Soft_B2A", ss=True)
        cmds.connectAttr(f"{foot_ctl}.Soft", f"{soft_blend}.attributesBlender")
        cmds.connectAttr(distance_plug, f"{soft_blend}.input[0]")
        cmds.connectAttr(f"{soft_condition}.outColorR", f"{soft_blend}.input[1]")

        soft_world_mul = cmds.createNode("multiply", name=f"{self.module_name}SoftWorld_MUL", ss=True)
        cmds.connectAttr(f"{soft_blend}.output", f"{soft_world_mul}.input[0]")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{soft_world_mul}.input[1]")

        absolute_primary = tuple(abs(x) for x in self.primary_axis)
        soft_aim = cmds.createNode("aimMatrix", name=f"{self.module_name}Soft_AIM", ss=True)
        cmds.connectAttr(f"{root_ctl}.worldMatrix[0]", f"{soft_aim}.inputMatrix")
        cmds.connectAttr(ik_target_plug, f"{soft_aim}.primary.primaryTargetMatrix")
        cmds.setAttr(f"{soft_aim}.primaryInputAxis", *absolute_primary, type="double3")
        cmds.setAttr(f"{soft_aim}.secondaryInputAxis", *self.secondary_axis, type="double3")
        cmds.setAttr(f"{soft_aim}.primaryMode", 1)

        soft_cmx = cmds.createNode("composeMatrix", name=f"{self.module_name}Soft_CMX", ss=True)
        cmds.connectAttr(f"{soft_world_mul}.output", f"{soft_cmx}.inputTranslateX")

        soft_mmx = cmds.createNode("multMatrix", name=f"{self.module_name}Soft_MMX", ss=True)
        cmds.connectAttr(f"{soft_cmx}.outputMatrix", f"{soft_mmx}.matrixIn[0]")
        cmds.connectAttr(f"{soft_aim}.outputMatrix", f"{soft_mmx}.matrixIn[1]")

        if self.ik_handles:
            cmds.connectAttr(f"{soft_mmx}.matrixSum", f"{self.main_handle}.offsetParentMatrix", force=True)
        else:
            cmds.connectAttr(f"{soft_mmx}.matrixSum", f"{self.nodes_target_dcm}.inputMatrix", force=True)

    def ik_calibration(self):
        """
        Hornea la corrección para que la cadena IK repose EXACTAMENTE sobre
        las guías, sea cual sea el solver. Sin esto cada solver da un reposo
        distinto y la comparación del experimento no es limpia — medirías la
        diferencia de reposo, no la del solver.

        Calibra el TWIST del handle principal midiendo la deriva de las
        articulaciones interiores contra sus guías (barrido grueso de 360° +
        refinado). Con el ikSpringSolver el plano nace de una captura interna
        que el poleVectorConstraint no siempre corrige; el twist sí lo rota de
        forma determinista y el valor horneado sobrevive a reabrir la escena.

        Criterio de éxito: en reposo, delta IK vs guías = 0 y match FK/IK = 0.
        """
        if not getattr(self, "ik_handles", None):
            return
        hdl = self.main_handle
        pairs = [(self.ik_chain[i], self.leg_chain[i]) for i in range(1, self.leg_end_index)]
        if not pairs:
            return

        def rest_error():
            return max((om.MVector(cmds.xform(ik, q=True, ws=True, t=True))
                        - om.MVector(cmds.xform(g, q=True, ws=True, t=True))).length()
                       for ik, g in pairs)

        best_t, best_e = 0.0, rest_error()

        for t in range(-180, 181, 5):
            cmds.setAttr(f"{hdl}.twist", t)
            e = rest_error()
            if e < best_e:
                best_t, best_e = float(t), e

        for step in (1.0, 0.2, 0.05):
            t = best_t - step * 4
            while t <= best_t + step * 4 + 1e-9:
                cmds.setAttr(f"{hdl}.twist", t)
                e = rest_error()
                if e < best_e:
                    best_t, best_e = t, e
                t += step
        cmds.setAttr(f"{hdl}.twist", best_t)
        if best_e > 0.2:
            cmds.warning(f"[leg_module_self] {self.module_name}: reposo IK no calibra a 0 (err={best_e:.3f} con twist={best_t:.2f})")

    def blend_setup(self):
        """
        Blend FK/IK por joint. NO dirige ninguna cadena: los outputMatrix de los
        blendMatrix son la salida del sistema (matrices world), y los consumidores
        (bendys, skinning, pie) se conectan a esos plugs
        """
        self.blend_matrices = []
        self.blend_plugs = []

        for i, jnt in enumerate(self.leg_joints):
            blend_matrix = cmds.createNode("blendMatrix", name=jnt.replace("_JNT", "Blend_BLM"), ss=True)
            ik_src = getattr(self, "nodes_ik_world", None)
            cmds.connectAttr(ik_src[i] if ik_src else f"{self.ik_chain[i]}.worldMatrix[0]",
                             f"{blend_matrix}.inputMatrix")
            cmds.connectAttr(f"{self.fk_controllers[i]}.worldMatrix[0]", f"{blend_matrix}.target[0].targetMatrix")
            cmds.connectAttr(f"{self.settings_ctl}.switchIkFk", f"{blend_matrix}.target[0].weight")

            self.blend_matrices.append(blend_matrix)
            self.blend_plugs.append(f"{blend_matrix}.outputMatrix")

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
        driver = self.fk_controllers[1]
        driven_anm = self.fk_controllers[2].replace("_CTL", "_ANM")
        lat_letter = "xyz"[max(range(3), key=lambda k: abs(self.lateral_axis[k]))].upper()

        cmds.addAttr(driver, longName="Coupling", attributeType="float", minValue=0, maxValue=1, defaultValue=1, keyable=True)

        # ratio MEDIDO del propio solver (barrido del galope recogido, cap. 8):
        # la babilla recorre 51.8° y el corvejón 55.0° -> 1.062 de conducido por
        # grado de conductor. El signo se mide por comportamiento: ambos ángulos
        # interiores deben CERRAR juntos (en la cadena zigzag con lateral fijo
        # la flexión alterna el sentido local por articulación)
        HOCK_PER_STIFLE = -1.062

        mul = cmds.createNode("multiply", name=f"{self.module_name}Coupling_MUL", ss=True)
        cmds.connectAttr(f"{driver}.rotate{lat_letter}", f"{mul}.input[0]")
        cmds.setAttr(f"{mul}.input[1]", HOCK_PER_STIFLE)
        cmds.connectAttr(f"{driver}.Coupling", f"{mul}.input[2]")
        cmds.connectAttr(f"{mul}.output", f"{driven_anm}.rotate{lat_letter}")

    # ═════════════════════════════════════════════════════════════════════════
    # SALIDA
    # ═════════════════════════════════════════════════════════════════════════
    def roll_and_non_roll_setup(self):
        """
        Frames anti-flip para alimentar los ribbons. Dos piezas:

        - Base NON-ROLL en la raíz: espacio estable que sigue al grupo del root
          IK o al del root FK según el switch (los GRUPOS no twistean con el
          solve), con la rotación alineada a ese espacio y el aim al siguiente
          joint con el lateral FIJO del personaje.
        - Por joint del tramo IK, _roll_cv: aim al siguiente + el twist LIMPIO
          del joint real extraído por swing-twist (cuaternión, neutralizado a 0
          en reposo) — el twist se reintroduce controlado, sin flips.

        Deja para bendys_setup: self.roll_wm (plugs por joint), self.cv_nodes,
        self.raw_hip_blend (con twist, para el bendy ctl), self.hip_ctl_roll y
        self.segment_names.
        """
        self.segment_count = self.leg_end_index
        if self.segment_count == 2:
            segment_names = ["Upper", "Lower"]
        elif self.segment_count == 3:
            segment_names = ["Upper", "Middle", "Lower"]
        else:
            segment_names = [f"Segment0{i}" for i in range(self.segment_count)]
        self.segment_names = segment_names

        blend_wm = list(self.blend_plugs)
        cv_nodes = list(self.blend_matrices)

        non_roll_space = cmds.createNode("blendMatrix", name=f"{self.module_name}NonRollSpace_BLM", ss=True)
        cmds.connectAttr(f"{self.ik_grp['root']}.worldMatrix[0]", f"{non_roll_space}.inputMatrix")
        cmds.connectAttr(f"{self.fk_grps[0]}.worldMatrix[0]", f"{non_roll_space}.target[0].targetMatrix")
        cmds.connectAttr(f"{self.settings_ctl}.switchIkFk", f"{non_roll_space}.target[0].weight")

        non_roll_align = cmds.createNode("blendMatrix", name=f"{self.module_name}NonRollAlign_BLM", ss=True)
        cmds.connectAttr(blend_wm[0], f"{non_roll_align}.inputMatrix")
        cmds.connectAttr(f"{non_roll_space}.outputMatrix", f"{non_roll_align}.target[0].targetMatrix")
        cmds.setAttr(f"{non_roll_align}.target[0].translateWeight", 0)
        cmds.setAttr(f"{non_roll_align}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{non_roll_align}.target[0].shearWeight", 0)

        non_roll_aim = cmds.createNode("aimMatrix", name=f"{self.module_name}NonRollAim_AMX", ss=True)
        cmds.connectAttr(f"{non_roll_align}.outputMatrix", f"{non_roll_aim}.inputMatrix")
        cmds.connectAttr(blend_wm[1], f"{non_roll_aim}.primary.primaryTargetMatrix")
        cmds.setAttr(f"{non_roll_aim}.primaryInputAxis", *self.primary_axis, type="double3")
        cmds.setAttr(f"{non_roll_aim}.secondaryInputAxis", *self.lateral_axis, type="double3")
        cmds.setAttr(f"{non_roll_aim}.secondaryMode", 2)
        cmds.setAttr(f"{non_roll_aim}.secondaryTargetVector", self.lateral_ref.x, self.lateral_ref.y, self.lateral_ref.z, type="double3")

        self.raw_hip_blend = blend_wm[0]  # con twist, para el bendy ctl
        blend_wm[0] = f"{non_roll_aim}.outputMatrix"
        cv_nodes[0] = non_roll_aim

        roll_wm = list(blend_wm)
        roll_wm[0] = f"{non_roll_aim}.outputMatrix"

        up_plug = self._lateral_row_plug(f"{non_roll_aim}.outputMatrix", f"{self.module_name}NonRollAimLat")
        for i in range(1, self.leg_end_index + 1):
            aim_target = blend_wm[i + 1] if i + 1 < len(blend_wm) else blend_wm[i]
            cv_nodes[i] = self._roll_cv(blend_wm[i], aim_target, f"{self.module_name}Roll0{i}", up_plug=up_plug)
            roll_wm[i] = f"{cv_nodes[i]}.matrixSum"
            up_plug = self.last_nonroll_lateral

        self.hip_ctl_roll = f"{self._roll_cv(self.raw_hip_blend, blend_wm[1], f'{self.module_name}RootCtl')}.matrixSum"

        self.roll_wm = roll_wm
        self.cv_nodes = cv_nodes

    def _roll_cv(self, blend_plug, aim_target_plug, name, up_plug=None):
            """
            Frame anti-flip para alimentar el ribbon: aim al siguiente joint con
            el eje lateral alineado a una referencia estable + el twist LIMPIO
            del joint real extraído por swing-twist (cuaternión, sin flip,
            neutralizado a 0 en reposo). Devuelve el multMatrix (.matrixSum).

            up_plug: fila lateral del frame ANTERIOR (encadenado). Con una
            referencia fija de mundo, un hueso que apunte hacia ella degenera
            el aim y el frame gira sobre el hueso (medido: dots 0.15 entre
            frames consecutivos con la pata cruzada hacia delante).
            """
            nonroll = cmds.createNode("aimMatrix", name=f"{name}NonRoll_AMX", ss=True)
            cmds.connectAttr(blend_plug, f"{nonroll}.inputMatrix")
            cmds.connectAttr(aim_target_plug, f"{nonroll}.primary.primaryTargetMatrix")
            cmds.setAttr(f"{nonroll}.primaryInputAxis", *self.primary_axis, type="double3")
            cmds.setAttr(f"{nonroll}.secondaryInputAxis", *self.lateral_axis, type="double3")
            cmds.setAttr(f"{nonroll}.secondaryMode", 2)
            if up_plug:
                cmds.connectAttr(up_plug, f"{nonroll}.secondaryTargetVector")
            else:
                cmds.setAttr(f"{nonroll}.secondaryTargetVector", self.lateral_ref.x, self.lateral_ref.y, self.lateral_ref.z, type="double3")
            self.last_nonroll_lateral = self._lateral_row_plug(f"{nonroll}.outputMatrix", f"{name}NonRollLat")

            twist_qn = matrix_manager.extract_twist(blend_plug, f"{nonroll}.outputMatrix", axis=self.aim_letter, name=name, return_quat=True)
            cmp = cmds.createNode("composeMatrix", name=f"{name}RollTwist_CMP", ss=True)
            cmds.setAttr(f"{cmp}.useEulerRotation", 0)
            cmds.connectAttr(f"{twist_qn}.outputQuat", f"{cmp}.inputQuat")
            roll = cmds.createNode("multMatrix", name=f"{name}Roll_MMX", ss=True)
            cmds.connectAttr(f"{cmp}.outputMatrix", f"{roll}.matrixIn[0]")
            cmds.connectAttr(f"{nonroll}.outputMatrix", f"{roll}.matrixIn[1]")
            return roll
    
    def _lateral_row_plug(self, matrix_plug, name):
            """Fila del eje lateral (con su signo) de un frame, como plug double3."""
            row_index = max(range(3), key=lambda k: abs(self.lateral_axis[k]))
            sign = self.lateral_axis[row_index]
            row = cmds.createNode("rowFromMatrix", name=f"{name}_RFM", ss=True)
            cmds.setAttr(f"{row}.input", row_index)
            cmds.connectAttr(matrix_plug, f"{row}.matrix")
            vec = cmds.createNode("multiplyDivide", name=f"{name}_MDV", ss=True)
            for axis in "XYZ":
                cmds.connectAttr(f"{row}.output{axis}", f"{vec}.input1{axis}")
            cmds.setAttr(f"{vec}.input2", sign, sign, sign)
            return f"{vec}.output"

    def bendys_setup(self):
        """
        Ribbons por segmento para deformación suave (utils/ribbon + de_boor_core).
        Ojo al twist: extráelo por swing-twist (cuaternión) para que no flipee.
        """

        cmds.addAttr(self.settings_ctl, longName="bendys", niceName="Bendy Controllers Visibility", attributeType="bool", dv=1)
        cmds.setAttr(f"{self.settings_ctl}.bendys", lock=False, keyable=False, channelBox=True)

        bendy_grp = cmds.createNode("transform", name=f"{self.module_name}BendyControllers_GRP", ss=True, p=self.controllers_grp)
        cmds.setAttr(f"{bendy_grp}.inheritsTransform", 0)

        self.bendy_ctls = []
        for i in range(self.segment_count):

            name = f"{self.module_name}{self.segment_names[i]}Bendy"

            mid_blm = cmds.createNode("blendMatrix", name=f"{name}_BLM", ss=True)
            cmds.connectAttr(self.hip_ctl_roll if i == 0 else self.roll_wm[i], f"{mid_blm}.inputMatrix")
            cmds.connectAttr(self.roll_wm[i + 1], f"{mid_blm}.target[0].targetMatrix")
            cmds.setAttr(f"{mid_blm}.target[0].translateWeight", 0.5)
            cmds.setAttr(f"{mid_blm}.target[0].rotateWeight", 0)
            cmds.setAttr(f"{mid_blm}.target[0].scaleWeight", 0)
            cmds.setAttr(f"{mid_blm}.target[0].shearWeight", 0)

            if i == 0:
                cmds.connectAttr(self.roll_wm[0], f"{mid_blm}.target[1].targetMatrix")
                cmds.setAttr(f"{mid_blm}.target[1].translateWeight", 0)
                cmds.setAttr(f"{mid_blm}.target[1].rotateWeight", 0.5)
                cmds.setAttr(f"{mid_blm}.target[1].scaleWeight", 0)
                cmds.setAttr(f"{mid_blm}.target[1].shearWeight", 0)

            bendy_nodes, bendy_ctl = curve_tool.create_controller(name=name, offset=["GRP", "ANM"], parent=bendy_grp)
            cmds.connectAttr(f"{self.settings_ctl}.bendys", f"{bendy_nodes[0]}.visibility")
            curve_tool.lock_attributes(bendy_ctl, ["sx", "sy", "sz", "v"])
            cmds.connectAttr(f"{mid_blm}.outputMatrix", f"{bendy_nodes[0]}.offsetParentMatrix")
            self.bendy_ctls.append(bendy_ctl)
        

    def skinning_setup(self):
        """
        Joints de deformación finales.

        Con bendys: un ribbon de Boor por segmento (frame roll inicio, bendy
        ctl del segmento, frame roll fin) genera los joints de skinning bajo
        skeleton_grp; además se añaden LAS QUE FALTAN — el pie: menudillo,
        cuartilla y casco como hojas hermanas dirigidas por matrices (el casco
        con offset horneado desde la cuartilla, que no tiene blend propio) — y
        la cadena guía se oculta como esqueleto interno del módulo.

        Sin bendys: la cadena guía se renombra a *Skinning_JNT bajo
        skeleton_grp y cada joint se conecta a su blend (relativo al padre
        vivo, para no doble-transformar la jerarquía).

        Publica self.foot_skin_drivers [(joint, plug)]: qué joints deforman el
        pie y de qué plug sale su world, para offsets posteriores.
        """
        self.foot_skin_drivers = []

        if self.bendys:

            ribbon_primary = (self.primaryInputAxisRibbon if self.side == "L"
                              else tuple(-v for v in self.primaryInputAxisRibbon))
            aim_idx = max(range(3), key=lambda k: abs(ribbon_primary[k]))
            aim_letter = "xyz"[aim_idx]
            signed_aim = aim_letter if ribbon_primary[aim_idx] > 0 else f"-{aim_letter}"
            up_letter = "xyz"[max(range(3), key=lambda k: abs(self.secondaryInputAxisRibbon[k]))]
            root_m = om.MMatrix(cmds.getAttr(self.guides_matrices[0]))
            k = 4 * "xyz".index(up_letter)
            up_world = om.MVector(root_m[k], root_m[k + 1], root_m[k + 2])
            up_sign = 1.0 if (up_world * self.lateral_ref) >= 0 else -1.0
            up_object_vector = (self.lateral_ref.x * up_sign, self.lateral_ref.y * up_sign, self.lateral_ref.z * up_sign)
            params = [i / (self.skinning_joints_number - 1) for i in range(self.skinning_joints_number)]
            params[-1] = 0.95

            self.skinning_joints = []
            for i in range(self.segment_count):

                name = f"{self.module_name}{self.segment_names[i]}"
                segment_jnts, temp = ribbon.de_boor_ribbon(
                    cvs=(self.cv_nodes[i], self.bendy_ctls[i], self.cv_nodes[i + 1]),
                    aim_axis=signed_aim, up_axis=up_letter, num_joints=self.skinning_joints_number,
                    skeleton_grp=self.skeleton_grp, name=name, custom_parameter=params,
                    up_object=self.masterwalk_ctl, up_object_vector=up_object_vector,
                )
                for t in temp:
                    cmds.delete(t)
                self.skinning_joints.extend(segment_jnts)

            cmds.setAttr(f"{self.leg_chain[0]}.visibility", 0)

            for idx in (self.leg_end_index, self.plant_index):
                jnt = cmds.createNode("joint", name=self.leg_chain[idx].replace("_JNT", "Skinning_JNT"), ss=True, parent=self.skeleton_grp)
                cmds.connectAttr(self.blend_plugs[idx], f"{jnt}.offsetParentMatrix")
                self.foot_skin_drivers.append((jnt, self.blend_plugs[idx]))

            tip_jnt = cmds.createNode("joint", name=self.tip_joint.replace("_JNT", "Skinning_JNT"), ss=True, parent=self.skeleton_grp)
            tip_rest = om.MMatrix(cmds.getAttr(self.guides_matrices[-1]))
            plant_rest = om.MMatrix(cmds.getAttr(self.guides_matrices[self.plant_index]))
            tip_mmx = cmds.createNode("multMatrix", name=f"{self.module_name}TipSkinning_MMX", ss=True)
            cmds.setAttr(f"{tip_mmx}.matrixIn[0]", list(tip_rest * plant_rest.inverse()), type="matrix")
            cmds.connectAttr(self.blend_plugs[self.plant_index], f"{tip_mmx}.matrixIn[1]")
            cmds.connectAttr(f"{tip_mmx}.matrixSum", f"{tip_jnt}.offsetParentMatrix")
            self.foot_skin_drivers.append((tip_jnt, f"{tip_mmx}.matrixSum"))
            return

        # ── sin bendys: cadena guia renombrada y conectada a los blends ──
        cmds.parent(self.leg_chain[0], self.skeleton_grp)
        renamed = [cmds.rename(j, j.replace("_JNT", "Skinning_JNT")) for j in self.leg_chain]
        self.leg_chain, self.leg_joints, self.tip_joint = renamed, renamed[:-1], renamed[-1]

        for i, jnt in enumerate(renamed[:-1]):
            if i == 0:
                cmds.connectAttr(self.blend_plugs[0], f"{jnt}.offsetParentMatrix")
            else:
                mmx = cmds.createNode("multMatrix", name=jnt.replace("Skinning_JNT", "SkinRel_MMT"), ss=True)
                cmds.connectAttr(self.blend_plugs[i], f"{mmx}.matrixIn[0]")
                cmds.connectAttr(f"{renamed[i - 1]}.worldInverseMatrix[0]", f"{mmx}.matrixIn[1]")
                cmds.connectAttr(f"{mmx}.matrixSum", f"{jnt}.offsetParentMatrix")
            cmds.xform(jnt, m=om.MMatrix.kIdentity)

        self.foot_skin_drivers = [
            (renamed[self.leg_end_index], self.blend_plugs[self.leg_end_index]),
            (renamed[self.plant_index], self.blend_plugs[self.plant_index]),
        ]

    def publish(self):
        """
        data_manager.append_data(). Todo lo que otro módulo pueda necesitar:
        controles principales, switch IK/FK, pole vector, y el joint MTP (del que
        cuelgan los dedos en una pata digitígrada).

        Data-driven: los módulos NO se pasan nombres a mano.
        """

        # _______ Delete all unnecesary nodes ___________________
        if self.settings_guide and cmds.objExists(self.settings_guide):
            cmds.delete(self.settings_guide)

        # _______ Write data ___________________
        data_manager.DataExportBiped().append_data(
            f"{self.LEG_PREFIX}_module",
            {
                f"{self.side}_legIk": self.ik_ctl["ankle"],
                f"{self.side}_rootIk": self.ik_ctl["root"],
                f"{self.side}_hipFk": self.fk_controllers[0],
            },
        )

        # _______ Delete chains if the handle is matematical ___________________
        if not self.ik_handles:
            for root in (self.ik_chain[0], self.leg_chain[0]):
                if cmds.objExists(root):
                    cmds.delete(root)

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
    # peroneo tercero TENDINOSO en el équido: el acoplamiento es obligatorio
    RECIPROCAL_COUPLING = True
    # Sobrescribe aquí: FORWARD_AXIS · PV_SIGN · REPOSITION_IK_TO_GUIDES ·
    # FOOT_CLASS


class FrontLegModule(LegModule):
    """
    Tren delantero: escápula -> hombro -> codo -> carpo -> MTP -> …
    El carpo dobla CRANIAL. No hay cadera: hay escápula, y eso es una diferencia
    de TOPOLOGÍA, no de valor -> por eso es subclase y no un flag.
    """
    LEG_PREFIX = "frontLeg"
    ROOT_JOINT = "Shoulder"

    def make(self, side, **kwargs):
        """Llama al padre y monta la escápula encima (necesita orient_guides)."""
        self.side = side
        super().make(side, **kwargs)
        self.scapula_setup()

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
        # ___________________ Load guides ___________________
        scapula_chain = guides_manager.get_guides(f"{self.side}_scapula_JNT")
        if not scapula_chain:
            cmds.warning(f"{self.side}_scapula_JNT no existe: se omite la escápula.")
            return
        self.scapula_guide = scapula_chain[0]
        cmds.parent(self.scapula_guide, self.module_trn)

        # ___________________ Set static matrix ___________________
        scapula_matrices, scapula_point_matrices = guides_manager.orient_guides(
            guides=scapula_chain,
            primaryInputAxis=self.primary_axis,
            secondaryInputAxis=self.secondary_axis,
        )
        self.scapula_wm = scapula_matrices[0]
        self.scapula_point_wm = scapula_point_matrices
        self.scapula_rest = om.MMatrix(cmds.getAttr(self.scapula_wm))
        self.scapula_end_rest = om.MMatrix(cmds.getAttr(self.guides_matrices[0]))
        if len(scapula_chain) > 1:
            cmds.delete(scapula_chain[1])

        # ___________________ Create scapula controls ___________________
        end_pos = om.MVector(self.scapula_end_rest[12], self.scapula_end_rest[13], self.scapula_end_rest[14])
        master_matrix = self.ctl_matrix(guides_manager._with_translation(om.MMatrix.kIdentity, end_pos), world_frame=True)
        scapula_master_grp, scapula_master_ctl = curve_tool.create_controller(
            name=f"{self.side}_scapulaMaster",
            offset=["GRP", "OFF", "ANM"],
            locked_attrs=["v"],
            matrix=master_matrix,
            parent=self.controllers_grp
        )
        self.scapula_master_ctl = scapula_master_ctl
        # Auto scapula
        scapula_auto_grp, scapula_auto_ctl = curve_tool.create_controller(
            name=f"{self.side}_scapula",
            offset=["GRP", "OFF", "ANM"],
            locked_attrs=["v"],
            matrix=self.ctl_matrix(self.scapula_rest),
            parent=scapula_master_ctl
        )
        self.scapula_ctl = scapula_auto_ctl
        # ___________________ Add attributes to the controls ___________________
        cmds.addAttr(scapula_auto_ctl, longName="SCAPULA_ATTRIBUTES", niceName="SCAPULA ATTRIBUTES ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{scapula_auto_ctl}.SCAPULA_ATTRIBUTES", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(scapula_auto_ctl, longName="Auto_Scapula", attributeType="float", defaultValue=1, maxValue=1, minValue=0, keyable=True)
        cmds.addAttr(scapula_auto_ctl, longName="Multiply_Amount", attributeType="float", defaultValue=1, minValue=0.001, keyable=True)

        # ___________________ Auto clavicle setup ___________________
        # Distance mesurement
        leg_distance = cmds.createNode("distanceBetween", name=f"{self.side}_scapulaLegLength_DBT", ss=True)
        cmds.connectAttr(f"{scapula_master_grp[0]}.worldMatrix[0]", f"{leg_distance}.inMatrix1")
        cmds.connectAttr(self.ik_handle_target, f"{leg_distance}.inMatrix2")

        leg_distance_norm = cmds.createNode("floatMath", name=f"{self.side}_scapulaLegLengthNorm_FLM", ss=True)
        cmds.setAttr(f"{leg_distance_norm}.operation", 3)
        cmds.connectAttr(f"{leg_distance}.distance", f"{leg_distance_norm}.floatA")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{leg_distance_norm}.floatB")
        self.scapula_leg_length_plug = f"{leg_distance_norm}.outFloat"

        scapula_aimMatrix = cmds.createNode("aimMatrix", name=f"{self.side}_scapulaAim_AMX", ss=True)
        cmds.setAttr(f"{scapula_aimMatrix}.inputMatrix", list(self.scapula_rest), type="matrix")
        cmds.connectAttr(f"{scapula_master_ctl}.worldMatrix[0]", f"{scapula_aimMatrix}.primary.primaryTargetMatrix")
        cmds.setAttr(f"{scapula_aimMatrix}.primaryInputAxis", *self.primary_axis, type="double3")

        lat_idx = max(range(3), key=lambda k: abs(self.lateral_axis[k]))
        lat_sign = 1.0 if self.lateral_axis[lat_idx] >= 0 else -1.0
        lat_world = [self.scapula_rest[lat_idx * 4 + k] * lat_sign for k in range(3)]
        cmds.setAttr(f"{scapula_aimMatrix}.secondaryInputAxis", *self.lateral_axis, type="double3")
        cmds.setAttr(f"{scapula_aimMatrix}.secondaryTargetVector", *lat_world, type="double3")
        cmds.connectAttr(f"{self.masterwalk_ctl}.worldMatrix[0]", f"{scapula_aimMatrix}.secondary.secondaryTargetMatrix")
        cmds.setAttr(f"{scapula_aimMatrix}.secondaryMode", 2)

        scapula_delta_mmx = cmds.createNode("multMatrix", name=f"{self.side}_scapulaDelta_MMX", ss=True)
        cmds.connectAttr(f"{scapula_aimMatrix}.outputMatrix", f"{scapula_delta_mmx}.matrixIn[0]")
        cmds.setAttr(f"{scapula_delta_mmx}.matrixIn[1]", *self.scapula_rest.inverse(), type="matrix")

        # Attribute activation
        scapula_blm = cmds.createNode("blendMatrix", name=f"{self.side}_autoScapula_BLM", ss=True)
        cmds.connectAttr(f"{scapula_delta_mmx}.matrixSum", f"{scapula_blm}.target[0].targetMatrix")
        cmds.connectAttr(f"{scapula_auto_ctl}.Auto_Scapula", f"{scapula_blm}.target[0].weight")
        cmds.connectAttr(f"{scapula_blm}.outputMatrix", f"{scapula_auto_grp[-1]}.offsetParentMatrix")

        # Movement setup (gate de compresión + elevación del master)
        scapula_pos = om.MVector(self.scapula_rest[12], self.scapula_rest[13], self.scapula_rest[14])
        EXCURSION_MAX = (end_pos - scapula_pos).length() * 0.5 * math.sin(math.radians(20.0))

        # GATE
        GALLOP_COMPRESSION = 0.73  # medido: dist/reposo = 0.732 en la pose (pie +25 arriba, -8 atras)
        rest_len = cmds.getAttr(self.scapula_leg_length_plug)
        remap_compress = cmds.createNode("remapValue", n=f"{self.side}_scapulaCompress_RMV", ss=True)
        cmds.connectAttr(self.scapula_leg_length_plug, f"{remap_compress}.inputValue")
        cmds.setAttr(f"{remap_compress}.inputMin", rest_len * GALLOP_COMPRESSION)
        cmds.setAttr(f"{remap_compress}.inputMax", rest_len)
        cmds.setAttr(f"{remap_compress}.outputMin", 1)
        cmds.setAttr(f"{remap_compress}.outputMax", 0)

        multiply_compress = cmds.createNode("multiply", n=f"{self.side}_scapulaCompress_MUL", ss=True)
        cmds.connectAttr(f"{remap_compress}.outValue", f"{multiply_compress}.input[0]")
        cmds.setAttr(f"{multiply_compress}.input[1]", EXCURSION_MAX)

        multiply_amount = cmds.createNode("multiply", n=f"{self.side}_scapulaCompressAmount_MUL", ss=True)
        cmds.connectAttr(f"{multiply_compress}.output", f"{multiply_amount}.input[0]")
        cmds.connectAttr(f"{self.scapula_ctl}.Multiply_Amount", f"{multiply_amount}.input[1]")
        cmds.connectAttr(f"{self.scapula_ctl}.Auto_Scapula", f"{multiply_amount}.input[2]")
        compose_m_compress = cmds.createNode("composeMatrix", n=f"{self.side}_scapulaLift_CPM", ss=True)
        cmds.connectAttr(f"{multiply_amount}.output", f"{compose_m_compress}.inputTranslateY")
        cmds.connectAttr(f"{compose_m_compress}.outputMatrix", f"{scapula_master_grp[-1]}.offsetParentMatrix")

        # ___________________ NURBS Surface (superficie del tórax) ___________________
        # Derivada de guías
        character = guides_manager.rig_manager.get_character_name_from_build()
        _, all_guides = guides_manager._load_guides_file(character)
        char_guides = all_guides.get(character, {}) if all_guides else {}
        chest_info = char_guides.get("C_localChest_JNT")
        if not chest_info:
            spines = sorted(k for k in char_guides
                            if k.startswith("C_spine") and k.endswith("_JNT"))
            chest_info = char_guides.get(spines[-1]) if spines else None
        if not chest_info:
            cmds.warning("Sin guía de chest ni de spine: la escápula queda sin superficie.")
            return
        chest_wm = om.MMatrix(chest_info["joint_matrix"])
        chest_pos = om.MVector(chest_wm[12], chest_wm[13], chest_wm[14])

        # Frame del aim: x hacia el root de la pierna, up hacia la clavícula
        sphere_aim_m = guides_manager._aim_matrix(chest_pos, end_pos, scapula_pos, (1, 0, 0), (0, 1, 0))

        # Radio y escala en cerrado para pasar por las DOS guías:
        R_ventral = (end_pos - chest_pos).length()
        p_local = scapula_pos - chest_pos
        x_s = p_local * om.MVector(sphere_aim_m[0], sphere_aim_m[1], sphere_aim_m[2])
        y_s = p_local * om.MVector(sphere_aim_m[4], sphere_aim_m[5], sphere_aim_m[6])
        z_s = p_local * om.MVector(sphere_aim_m[8], sphere_aim_m[9], sphere_aim_m[10])
        if abs(x_s) >= R_ventral * 0.999:
            cmds.warning("Guía de clavícula degenerada respecto al chest: esfera simple.")
            r = p_local.length()
            sx = 1.0
        else:
            r = math.sqrt((y_s ** 2 + z_s ** 2) / (1.0 - x_s ** 2 / R_ventral ** 2))
            sx = R_ventral / r

        scapula_surface = cmds.sphere(n=f"{self.side}_scapulaSurface_NURB", r=r, ch=False)[0]
        cmds.parent(scapula_surface, self.module_trn)
        cmds.setAttr(f"{scapula_surface}.visibility", 0)
        cmds.setAttr(f"{scapula_surface}.scaleX", sx)

        # Sigue al chest por matrices
        chest_ctl = data_manager.DataExportBiped().get_data("spine_module", "local_chest_ctl")
        if not chest_ctl or not cmds.objExists(chest_ctl):
            chest_ctl = self.masterwalk_ctl
        chest_ctl_wm = om.MMatrix(cmds.getAttr(f"{chest_ctl}.worldMatrix[0]"))
        mmx_scapula = cmds.createNode("multMatrix", n=f"{self.side}_scapulaSurface_MMX", ss=True)
        cmds.setAttr(f"{mmx_scapula}.matrixIn[0]", list(sphere_aim_m * chest_ctl_wm.inverse()), type="matrix")
        cmds.connectAttr(f"{chest_ctl}.worldMatrix[0]", f"{mmx_scapula}.matrixIn[1]")
        cmds.connectAttr(f"{mmx_scapula}.matrixSum", f"{scapula_surface}.offsetParentMatrix")
        self.scapula_surface = scapula_surface

        # Joint de skinning proyectada a la superficie
        scapula_skinning_jnt = cmds.createNode("joint", n=f"{self.side}_scapulaSkinning_JNT", ss=True, p=self.skeleton_grp)
        surface_shape = cmds.listRelatives(scapula_surface, shapes=True)[0]
        cps_scapula = cmds.createNode("closestPointOnSurface", n=f"{self.side}_scapulaProjected_CPS", ss=True)
        cmds.connectAttr(f"{surface_shape}.worldSpace[0]", f"{cps_scapula}.inputSurface")
        cmds.setAttr(f"{cps_scapula}.inPositionX", scapula_pos[0])
        cmds.setAttr(f"{cps_scapula}.inPositionY", scapula_pos[1])
        cmds.setAttr(f"{cps_scapula}.inPositionZ", scapula_pos[2])

        cps_rest = om.MVector(cmds.getAttr(f"{cps_scapula}.positionX"),
                              cmds.getAttr(f"{cps_scapula}.positionY"),
                              cmds.getAttr(f"{cps_scapula}.positionZ"))
        residual = scapula_pos - cps_rest
        cps_delta = cmds.createNode("plusMinusAverage", n=f"{self.side}_scapulaProjectedDelta_PMA", ss=True)
        cmds.connectAttr(f"{cps_scapula}.position", f"{cps_delta}.input3D[0]")
        cmds.setAttr(f"{cps_delta}.input3D[1]", residual.x, residual.y, residual.z, type="double3")
        fbf_scapula = cmds.createNode("fourByFourMatrix", n=f"{self.side}_scapula_FBF", ss=True)
        cmds.connectAttr(f"{cps_delta}.output3Dx", f"{fbf_scapula}.in30")
        cmds.connectAttr(f"{cps_delta}.output3Dy", f"{fbf_scapula}.in31")
        cmds.connectAttr(f"{cps_delta}.output3Dz", f"{fbf_scapula}.in32")
        jnt_amx = cmds.createNode("aimMatrix", n=f"{self.side}_scapulaJnt_AMX", ss=True)
        cmds.connectAttr(f"{fbf_scapula}.output", f"{jnt_amx}.inputMatrix")
        cmds.connectAttr(f"{scapula_master_ctl}.worldMatrix[0]", f"{jnt_amx}.primary.primaryTargetMatrix")
        cmds.setAttr(f"{jnt_amx}.primaryInputAxis", *self.primary_axis, type="double3")
        cmds.setAttr(f"{jnt_amx}.secondaryInputAxis", *self.lateral_axis, type="double3")
        cmds.setAttr(f"{jnt_amx}.secondaryTargetVector", *lat_world, type="double3")
        cmds.connectAttr(f"{self.masterwalk_ctl}.worldMatrix[0]", f"{jnt_amx}.secondary.secondaryTargetMatrix")
        cmds.setAttr(f"{jnt_amx}.secondaryMode", 2)
        cmds.connectAttr(f"{jnt_amx}.outputMatrix", f"{scapula_skinning_jnt}.offsetParentMatrix", force=True)
        self.scapula_skinning_jnt = scapula_skinning_jnt

        # Crear space switch de chest a clavicula
        matrix_manager.space_switches(
            target=self.scapula_ctl,
            sources=[chest_ctl, self.masterwalk_ctl],
            sources_names=["chest", "world"],
            default_translate=0.5,
            default_rotate=0.5,
            base_ctl=self.scapula_master_ctl,
        )
        ctl_dcm = cmds.createNode("decomposeMatrix", n=f"{self.side}_scapulaCtlPos_DCM", ss=True)
        cmds.connectAttr(f"{self.scapula_ctl}.worldMatrix[0]", f"{ctl_dcm}.inputMatrix")
        cmds.connectAttr(f"{ctl_dcm}.outputTranslate", f"{cps_scapula}.inPosition")

        # Renormalización a la longitud del hueso
        bone_len = (end_pos - scapula_pos).length()
        local_mpm = cmds.createNode("multiplyPointByMatrix", n=f"{self.side}_scapulaLocal_MPM", ss=True)
        cmds.connectAttr(f"{cps_delta}.output3D", f"{local_mpm}.input")
        cmds.connectAttr(f"{self.scapula_master_ctl}.worldInverseMatrix[0]", f"{local_mpm}.matrix")

        dir_nrm = cmds.createNode("normalize", n=f"{self.side}_scapulaDir_NRM", ss=True)
        cmds.connectAttr(f"{local_mpm}.output", f"{dir_nrm}.input")

        len_mmx = cmds.createNode("multMatrix", n=f"{self.side}_scapulaBoneLen_MMX", ss=True)
        cmds.setAttr(f"{len_mmx}.matrixIn[0]",
                     [bone_len, 0, 0, 0, 0, bone_len, 0, 0, 0, 0, bone_len, 0, 0, 0, 0, 1],
                     type="matrix")
        cmds.connectAttr(f"{self.scapula_master_ctl}.worldMatrix[0]", f"{len_mmx}.matrixIn[1]")

        final_mpm = cmds.createNode("multiplyPointByMatrix", n=f"{self.side}_scapulaFinal_MPM", ss=True)
        cmds.connectAttr(f"{dir_nrm}.output", f"{final_mpm}.input")
        cmds.connectAttr(f"{len_mmx}.matrixSum", f"{final_mpm}.matrix")

        for axis, plug in (("X", "in30"), ("Y", "in31"), ("Z", "in32")):
            cmds.connectAttr(f"{final_mpm}.output{axis}", f"{fbf_scapula}.{plug}", force=True)
        self.scapula_master_ctl = scapula_master_ctl
        # _______ Write data ___________________
        data_manager.DataExportBiped().append_data(
            f"{self.LEG_PREFIX}_module",
            {
                f"{self.side}_scapula_master_ctl": self.scapula_master_ctl
            },
        )
        # _______ Delete guides ___________________
        # la lista scapula_chain guarda rutas de antes del reparent: se borra
        # la raiz (el subarbol cae con ella)
        if cmds.objExists(self.scapula_guide):
            cmds.delete(self.scapula_guide)


# ═════════════════════════════════════════════════════════════════════════════
# PIE — COMPUESTO, no heredado
# ═════════════════════════════════════════════════════════════════════════════
class FootBase(object):
    """
    Interfaz común del pie. La pierna COMPONE una de estas, no hereda de ellas.

    Contrato: la pierna entrega el MTP y las matrices de reposo; el pie construye
    sus pivotes y expone sus atributos en el control del pie.
    """

    PIVOT_ORDER = ["bankOut", "bankIn", "heel", "toe", "sole"]

    def build(self, leg):
        """leg = el LegModule que compone este pie (para leer índices y matrices)."""
        self.pivots(leg)
        self.roll_attributes(leg, leg.ik_ctl["ankle"])

    def pivots(self, leg):
        """
        Pila de pivotes del pie reverso bajo el ctl del tobillo:
            ankle -> bankOut -> bankIn -> heel -> toe -> sole -> [GRP del ball]

        Posiciones: guía locator si el personaje la trae; si no, DERIVADAS de
        la anatomía. La derivación vale para el CASCO: la cuartilla está
        elevada, así que proyectarla a la altura de la punta da el talón; los
        bancos van en los bordes de la suela. El digitígrado debe sobreescribir
        esto (trampa del talón — ver PawFoot).

        Frames propios, no de guía: x = avance, y = arriba, z = lateral_ref
        (espejada en R). Así rz = roll, rx = bank, ry = twist, y bank/roll
        salen espejados entre lados sin tablas de signos por pivote.
        """
        up = om.MVector(0, 1, 0)
        lat = om.MVector(leg.lateral_ref).normal()
        fwd = (up ^ lat).normal()

        def _pivot_matrix(pos):
            return om.MMatrix([fwd.x, fwd.y, fwd.z, 0,
                               up.x, up.y, up.z, 0,
                               lat.x, lat.y, lat.z, 0,
                               pos.x, pos.y, pos.z, 1])

        tip_p = om.MVector(leg.world_positions[-1])
        plant_p = leg.world_positions[leg.plant_index]
        heel_p = om.MVector(plant_p.x, tip_p.y, plant_p.z)  # pisada proyectada al suelo
        sole_p = (heel_p + tip_p) * 0.5
        half_w = (tip_p - heel_p).length() * 0.5  # ancho del casco aproximado por su largo
        out_dir = om.MVector(1, 0, 0) if leg.side == "L" else om.MVector(-1, 0, 0)
        positions = {
            "bankOut": sole_p + out_dir * half_w,
            "bankIn":  sole_p - out_dir * half_w,
            "heel":    heel_p,
            "toe":     tip_p,
            "sole":    sole_p,
        }

        self.pivot_ctl = {}
        self.pivot_sdk = {}
        parent = leg.ik_ctl["ankle"]
        for role in self.PIVOT_ORDER:
            loc = guides_manager.get_guides(f"{leg.side}_{leg.LEG_PREFIX}{role}_LOCShape")
            matrix = (cmds.xform(loc, q=True, ws=True, m=True) if loc
                      else _pivot_matrix(positions[role]))
            grps, ctl = curve_tool.create_controller(
                name=f"{leg.side}_{leg.LEG_PREFIX}{role[0].upper()}{role[1:]}",
                offset=["GRP", "SDK", "ANM"],
                locked_attrs=["tx", "ty", "tz", "sx", "sy", "sz", "v"],
                matrix=matrix, parent=parent)
            self.pivot_ctl[role] = ctl
            self.pivot_sdk[role] = grps[1]
            parent = ctl

        ball_grp = leg.ik_grp["ball"]
        cmds.parent(ball_grp, self.pivot_ctl["sole"])

        local = (om.MMatrix(cmds.getAttr(f"{ball_grp}.matrix"))
                 * om.MMatrix(cmds.getAttr(f"{ball_grp}.offsetParentMatrix")))
        cmds.setAttr(f"{ball_grp}.offsetParentMatrix", list(local), type="matrix")
        cmds.xform(ball_grp, m=om.MMatrix.kIdentity)

    def roll_attributes(self, leg, foot_ctl):
        """
        Roll y twist sobre los SDK de los pivotes. Arquitectura en dos tramos:
        hasta Roll_Break_Angle levanta la pisada (sole); del break al straight
        angle rueda la punta. Bank con signo (positivo = borde externo).

        TRAMPA: si construyes el tramo negativo con un remapValue de inputMin=0,
        el roll negativo CLAMPA A CERO y no hace absolutamente nada. Aísla el
        tramo negativo (un min) antes de darle su propio pivote.

        SIGNO: rodar hacia delante es +θ alrededor de
        W = up ^ FORWARD_AXIS en mundo; los pivotes giran en rz alrededor de su
        z local (lateral_ref, espejada en R), así que el signo por lado es el
        de lateral_ref·W. Vale para cualquier FORWARD_AXIS.
        """
        name = f"{leg.side}_{leg.LEG_PREFIX}"

        cmds.addAttr(foot_ctl, longName="FOOT_ATTRIBUTES", niceName="FOOT ATTRIBUTES ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{foot_ctl}.FOOT_ATTRIBUTES", keyable=False, channelBox=True, lock=True)
        for attr in ["Roll", "Bank", "Ankle_Twist", "Ball_Twist", "Heel_Twist", "Toe_Twist"]:
            cmds.addAttr(foot_ctl, longName=attr, attributeType="float", defaultValue=0, keyable=True)
        cmds.addAttr(foot_ctl, longName="Roll_Break_Angle", attributeType="float", defaultValue=35, keyable=True)
        cmds.addAttr(foot_ctl, longName="Roll_Straight_Angle", attributeType="float", defaultValue=75, keyable=True)

        # visibilidad de los pivotes
        cmds.addAttr(foot_ctl, longName="Pivot_Controllers", attributeType="bool", defaultValue=0, keyable=False)
        cmds.setAttr(f"{foot_ctl}.Pivot_Controllers", channelBox=True)
        for role in self.PIVOT_ORDER:
            for shape in cmds.listRelatives(self.pivot_ctl[role], shapes=True) or []:
                cmds.connectAttr(f"{foot_ctl}.Pivot_Controllers", f"{shape}.visibility")

        cmds.connectAttr(f"{foot_ctl}.Ankle_Twist", f"{self.pivot_sdk['bankOut']}.rotateY")
        cmds.connectAttr(f"{foot_ctl}.Ball_Twist", f"{self.pivot_sdk['sole']}.rotateY")
        cmds.connectAttr(f"{foot_ctl}.Heel_Twist", f"{self.pivot_sdk['heel']}.rotateY")
        cmds.connectAttr(f"{foot_ctl}.Toe_Twist", f"{self.pivot_sdk['toe']}.rotateY")

        up = om.MVector(0, 1, 0)
        w_axis = up ^ om.MVector(*leg.FORWARD_AXIS)
        roll_sign = 1 if (om.MVector(leg.lateral_ref) * w_axis) > 0 else -1
        straight_rmv = cmds.createNode("remapValue", name=f"{name}RollStraightAngle_RMV", ss=True)
        cmds.connectAttr(f"{foot_ctl}.Roll", f"{straight_rmv}.inputValue")
        cmds.connectAttr(f"{foot_ctl}.Roll_Break_Angle", f"{straight_rmv}.inputMin")
        cmds.connectAttr(f"{foot_ctl}.Roll_Straight_Angle", f"{straight_rmv}.inputMax")

        break_rmv = cmds.createNode("remapValue", name=f"{name}RollBreakAngle_RMV", ss=True)
        cmds.connectAttr(f"{foot_ctl}.Roll", f"{break_rmv}.inputValue")
        cmds.connectAttr(f"{foot_ctl}.Roll_Break_Angle", f"{break_rmv}.inputMax")

        reverse = cmds.createNode("reverse", name=f"{name}RollBreakAngle_REV", ss=True)
        cmds.connectAttr(f"{straight_rmv}.outValue", f"{reverse}.inputX")

        enable_mul = cmds.createNode("multiply", name=f"{name}RollAngleEnable_MUL", ss=True)
        cmds.connectAttr(f"{reverse}.outputX", f"{enable_mul}.input[0]")
        cmds.connectAttr(f"{foot_ctl}.Roll", f"{enable_mul}.input[1]")

        lift_mul = cmds.createNode("multiply", name=f"{name}RollLift_MUL", ss=True)
        cmds.connectAttr(f"{break_rmv}.outValue", f"{lift_mul}.input[0]")
        cmds.connectAttr(f"{enable_mul}.output", f"{lift_mul}.input[1]")
        lift_sign = cmds.createNode("multiply", name=f"{name}RollLiftSign_MUL", ss=True)
        cmds.connectAttr(f"{lift_mul}.output", f"{lift_sign}.input[0]")
        cmds.setAttr(f"{lift_sign}.input[1]", roll_sign)
        cmds.connectAttr(f"{lift_sign}.output", f"{self.pivot_sdk['sole']}.rotateZ")

        toe_mul = cmds.createNode("multiply", name=f"{name}RollToe_MUL", ss=True)
        cmds.connectAttr(f"{straight_rmv}.outValue", f"{toe_mul}.input[0]")
        cmds.connectAttr(f"{foot_ctl}.Roll", f"{toe_mul}.input[1]")
        toe_sign = cmds.createNode("multiply", name=f"{name}RollToeSign_MUL", ss=True)
        cmds.connectAttr(f"{toe_mul}.output", f"{toe_sign}.input[0]")
        cmds.setAttr(f"{toe_sign}.input[1]", roll_sign)
        cmds.connectAttr(f"{toe_sign}.output", f"{self.pivot_sdk['toe']}.rotateZ")

        # tramo negativo aislado con un min
        heel_min = cmds.createNode("min", name=f"{name}RollHeel_MIN", ss=True)
        cmds.setAttr(f"{heel_min}.input[0]", 0)
        cmds.connectAttr(f"{foot_ctl}.Roll", f"{heel_min}.input[1]")
        heel_sign = cmds.createNode("multiply", name=f"{name}RollHeelSign_MUL", ss=True)
        cmds.connectAttr(f"{heel_min}.output", f"{heel_sign}.input[0]")
        cmds.setAttr(f"{heel_sign}.input[1]", roll_sign)
        cmds.connectAttr(f"{heel_sign}.output", f"{self.pivot_sdk['heel']}.rotateZ")


        bank_neg = cmds.createNode("multiply", name=f"{name}BankNeg_MUL", ss=True)
        cmds.connectAttr(f"{foot_ctl}.Bank", f"{bank_neg}.input[0]")
        cmds.setAttr(f"{bank_neg}.input[1]", -1)

        bank_cnd = cmds.createNode("condition", name=f"{name}Bank_CND", ss=True)
        cmds.connectAttr(f"{foot_ctl}.Bank", f"{bank_cnd}.firstTerm")
        cmds.setAttr(f"{bank_cnd}.operation", 2)  # Bank > 0 -> borde externo
        cmds.connectAttr(f"{bank_neg}.output", f"{bank_cnd}.colorIfTrueR")
        cmds.setAttr(f"{bank_cnd}.colorIfFalseR", 0)
        cmds.setAttr(f"{bank_cnd}.colorIfTrueG", 0)
        cmds.connectAttr(f"{bank_neg}.output", f"{bank_cnd}.colorIfFalseG")
        cmds.connectAttr(f"{bank_cnd}.outColorR", f"{self.pivot_sdk['bankOut']}.rotateX")
        cmds.connectAttr(f"{bank_cnd}.outColorG", f"{self.pivot_sdk['bankIn']}.rotateX")


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

    def build(self, leg):
        super(HoofFoot, self).build(leg)
        self.hoof_attach(leg)
        self.fetlock_spring(leg, leg.ik_ctl["ankle"])

    def hoof_attach(self, leg):
        """
        Casco pegado al ball (Foot) por matrices: el lado IK del blend de la
        pisada (cuartilla) pasa a ser offset horneado × worldMatrix vivo del
        Foot. Como el Foot vive en el punto del fetlock dentro de la pila de
        pivotes, rotarlo gira el casco desde ahí sin mover el objetivo del IK
        (el manager lee su world, y la posición no cambia al rotar sobre sí
        mismo); roll, bank y twist del master le llegan por jerarquía. El Tip
        ya deriva de la pisada en skinning (TipSkinning_MMX). Sin handles
        extra: el joint IK de la cuartilla queda como esqueleto interno.
        """
        ball_ctl = leg.ik_ctl["ball"]
        self.foot_ctl = ball_ctl

        pastern_grps, pastern_ctl = curve_tool.create_controller(
            name=leg.leg_chain[leg.plant_index].replace("_JNT", "Ik"),
            offset=["GRP", "OFF", "ANM"],
            locked_attrs=["tx", "ty", "tz", "sx", "sy", "sz", "v"],
            parent=self.pivot_ctl["sole"],
            matrix=leg.ctl_matrix(cmds.getAttr(leg.point_matrices[leg.plant_index]), world_frame=True),
        )
        leg.ik_ctl["pastern"] = pastern_ctl
        leg.ik_grp["pastern"] = pastern_grps[0]

        # el ball (Foot) pasa a colgar de la cuartilla, sin offset en canales
        ball_grp = leg.ik_grp["ball"]
        cmds.parent(ball_grp, pastern_ctl)
        local = (om.MMatrix(cmds.getAttr(f"{ball_grp}.matrix"))
                 * om.MMatrix(cmds.getAttr(f"{ball_grp}.offsetParentMatrix")))
        cmds.setAttr(f"{ball_grp}.offsetParentMatrix", list(local), type="matrix")
        cmds.xform(ball_grp, m=om.MMatrix.kIdentity)

        # casco pegado al Foot (hereda la cuartilla por jerarquía)
        plant_rest = om.MMatrix(cmds.getAttr(leg.guides_matrices[leg.plant_index]))
        ball_rest_inv = om.MMatrix(cmds.getAttr(f"{ball_ctl}.worldMatrix[0]")).inverse()

        hoof_mmx = cmds.createNode("multMatrix", name=f"{leg.side}_{leg.LEG_PREFIX}HoofFollow_MMX", ss=True)
        cmds.setAttr(f"{hoof_mmx}.matrixIn[0]", list(plant_rest * ball_rest_inv), type="matrix")
        cmds.connectAttr(f"{ball_ctl}.worldMatrix[0]", f"{hoof_mmx}.matrixIn[1]")
        cmds.connectAttr(f"{hoof_mmx}.matrixSum",
                         f"{leg.blend_matrices[leg.plant_index]}.inputMatrix", force=True)


        if getattr(leg, "nodes_ik_world", None):
            end_src = leg.nodes_ik_world[leg.leg_end_index]
        else:
            end_src = f"{leg.ik_chain[leg.leg_end_index]}.worldMatrix[0]"
        fet_aim = cmds.createNode("aimMatrix", name=f"{leg.side}_{leg.LEG_PREFIX}FetlockAim_AMX", ss=True)
        cmds.connectAttr(end_src, f"{fet_aim}.inputMatrix")
        cmds.connectAttr(f"{hoof_mmx}.matrixSum", f"{fet_aim}.primary.primaryTargetMatrix")
        cmds.setAttr(f"{fet_aim}.primaryInputAxis", *leg.primary_axis, type="double3")
        cmds.connectAttr(f"{fet_aim}.outputMatrix",
                         f"{leg.blend_matrices[leg.leg_end_index]}.inputMatrix", force=True)

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
        ball-roll se aplasta (medido en esta config: Roll −20 mueve el fetlock
        1.42u sin carga y 1.13u con carga 1).

        DÓNDE se inyecta: en el MANAGER del ik (entre el offset horneado y el
        world vivo del ball), no en el ball — rotar el ball movería también el
        casco (HoofFollow lee su world) y el casco debe quedarse PLANTADO. La
        rotación actúa sobre el punto de la cuartilla expresado en espacio del
        ball (constante: el ball es hijo del PasternIk), así el pivote es
        correcto en cualquier pose.
        """
        cmds.addAttr(foot_ctl, longName="SPRING", niceName="SPRING ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{foot_ctl}.SPRING", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(foot_ctl, longName="Load", attributeType="float", minValue=0, maxValue=1, defaultValue=0, keyable=True)

        # rango: ~22 grados de excursión del ángulo MCP entre paso y galope
        # (datos de marcha, cap. 8); signo NEGATIVO = hundir (medido por
        # comportamiento: con +22 el fetlock subía; con −22 baja)
        MCP_SINK_DEG = -22.0

        n = f"{leg.side}_{leg.LEG_PREFIX}"
        # muelle que ENDURECE: theta = R·(1 − (1−L)²). Pendiente 2R(1−L):
        # máxima en vacío, nula al tope — incrementos de carga iguales hunden
        # cada vez menos, la forma del aparato suspensor
        u_sub = cmds.createNode("subtract", name=f"{n}FetlockSpringU_SUB", ss=True)
        cmds.setAttr(f"{u_sub}.input1", 1)
        cmds.connectAttr(f"{foot_ctl}.Load", f"{u_sub}.input2")
        u2_mul = cmds.createNode("multiply", name=f"{n}FetlockSpringU2_MUL", ss=True)
        cmds.connectAttr(f"{u_sub}.output", f"{u2_mul}.input[0]")
        cmds.connectAttr(f"{u_sub}.output", f"{u2_mul}.input[1]")
        s_sub = cmds.createNode("subtract", name=f"{n}FetlockSpringS_SUB", ss=True)
        cmds.setAttr(f"{s_sub}.input1", 1)
        cmds.connectAttr(f"{u2_mul}.output", f"{s_sub}.input2")
        theta = cmds.createNode("multiply", name=f"{n}FetlockSpringTheta_MUL", ss=True)
        cmds.connectAttr(f"{s_sub}.output", f"{theta}.input[0]")
        cmds.setAttr(f"{theta}.input[1]", MCP_SINK_DEG)

        spring_cmx = cmds.createNode("composeMatrix", name=f"{n}FetlockSpring_CMX", ss=True)
        cmds.connectAttr(f"{theta}.output", f"{spring_cmx}.inputRotateX")

        # cuartilla en espacio del ball (constante — es su hijo): la rotación
        # se conjuga T(−p)·R·T(p) para pivotar sobre ella
        ball_ctl = leg.ik_ctl["ball"]
        ball_rest = om.MMatrix(cmds.getAttr(f"{ball_ctl}.worldMatrix[0]"))
        pastern_w = om.MVector(cmds.xform(leg.ik_ctl["pastern"], q=True, ws=True, t=True))
        p_l = om.MPoint(pastern_w) * ball_rest.inverse()
        t_neg = om.MMatrix([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -p_l.x, -p_l.y, -p_l.z, 1])
        t_pos = om.MMatrix([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, p_l.x, p_l.y, p_l.z, 1])

        # reinsertar en el manager: offset × T(−p) × R × T(p) × ball_world
        manager = leg.ik_handle_target.split(".")[0]
        ball_conn = cmds.listConnections(f"{manager}.matrixIn[1]", plugs=True, source=True, destination=False)[0]
        cmds.disconnectAttr(ball_conn, f"{manager}.matrixIn[1]")
        cmds.setAttr(f"{manager}.matrixIn[1]", list(t_neg), type="matrix")
        cmds.connectAttr(f"{spring_cmx}.outputMatrix", f"{manager}.matrixIn[2]")
        cmds.setAttr(f"{manager}.matrixIn[3]", list(t_pos), type="matrix")
        cmds.connectAttr(ball_conn, f"{manager}.matrixIn[4]")


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

    # I = espolón (no apoya), II-V = dedos de apoyo. Numeración veterinaria.
    DIGIT_NUMERALS = ["I", "II", "III", "IV", "V"]

    def digits_guides(self, leg):
        """
        Carga las cadenas de guías de los dedos: pide la raíz 00 de cada
        numeral ({side}_{legPrefix}Digit{N}00_JNT) y get_guides trae sus
        falanges. Las ausentes se omiten sin error — así un personaje de 3
        dedos funciona sin tocar código. Deja:
            self.digit_chains[numeral] = {"chain": [falanges...]}
        """
        self.finger_base_name = f"{leg.side}_{leg.LEG_PREFIX}Digit"
        self.digit_chains = {} # Set the dict for all the guides

        for number in self.DIGIT_NUMERALS:

            root = f"{self.finger_base_name}{number}00_JNT" # L_frontLegDigitI00_JNT p.e
            chain = guides_manager.get_guides(root)
            if not chain:
                continue
            self.digit_chains[number] = {"chain": chain}

    def digits_orient_guides(self, leg):
        """
        Frames por dedo con la misma convención de ejes de la pierna. Amplía
        cada self.digit_chains[numeral] con:
            "world"  plugs de matriz world (network horneado)
            "point"  plugs solo-posición
            "local"  MMatrix relativas a la falange anterior (la 00 queda en
                     world: su padre real es el MTP y su offset se compone al
                     colgarla, en digits_fk)
        """
        leg.primary_axis = leg.primaryInputAxis if leg.side == "L" else tuple(-v for v in leg.primaryInputAxis)
        leg.secondary_axis = leg.secondaryInputAxis

        for number, data in self.digit_chains.items():

            world_plugs, point_plugs  = guides_manager.orient_guides(
                guides=data["chain"],
                primaryInputAxis=leg.primary_axis,
                secondaryInputAxis=leg.secondary_axis,
            )

            local_matrices = []
            for i, plug in enumerate(world_plugs):
                w_matrix = om.MMatrix(cmds.getAttr(plug))
                if i == 0:
                    local_matrices.append(w_matrix)
                else:
                    parent_matrix = om.MMatrix(cmds.getAttr(world_plugs[i - 1]))
                    local_matrices.append(w_matrix * parent_matrix.inverse())

            data["local"] = local_matrices
            data["world"] = world_plugs
            data["point"] = point_plugs

            # self.digit_chains["III"]["chain"][0] ------> primera falange del dedo III
            # self.digit_chains["III"]["world"][1] ------> WM de la falange III dedo 01
            # self.digit_chains["III"]["local"][2] ------> LM de la falange III dedo 02
            

    def digits_fk(self, leg):
        """
        Cascada FK por dedo, colgada del MTP SIN DAG (el MTP viene del blend;
        por DAG heredaría su transform dos veces): el grupo raíz de los dedos
        recibe el plug del blend del MTP en su offsetParentMatrix con
        inheritsTransform a 0, la falange 00 lleva su offset estático contra el
        MTP en reposo, y el resto offsets locales horneados. Los controles
        llevan nivel SDK para los drivers de digits_attributes. Deja:
            self.leg_digit_fk_ctls[numeral] = [ctls...]
        """
        parent_plug = leg.blend_plugs[leg.leg_end_index] # Get the last joint blend matrix
        digits_grp = cmds.createNode("transform", name=f"{self.finger_base_name}Fk_GRP") # Create the parent group for all of FK controllers
        cmds.setAttr(f"{digits_grp}.inheritsTransform", 0)
        cmds.connectAttr(parent_plug, f"{digits_grp}.offsetParentMatrix")
        parent_matrix = om.MMatrix(cmds.getAttr(leg.blend_plugs[leg.leg_end_index]))

        self.leg_digit_fk_ctls = {}

        for name, data in self.digit_chains.items():

            fk_ctls = []

            for i, jnt in enumerate(data["chain"]):

                parent = digits_grp if i == 0 else fk_ctls[-1]
                grp, ctl = curve_tool.create_controller(
                    name=jnt.replace("_JNT", "Fk"),
                    offset=["GRP", "SDK", "ANM"],
                    locked_attrs=["tx", "ty", "tz", "sx", "sy", "sz", "v"],
                    parent=parent,
                )

                if i == 0:
                    local = om.MMatrix(cmds.getAttr(data["world"][0])) * parent_matrix.inverse() # Set the local matrix based on the parent
                else:
                    local = data["local"][i]
                cmds.setAttr(f"{grp[0]}.offsetParentMatrix", list(local), type="matrix")
                fk_ctls.append(ctl)
            self.leg_digit_fk_ctls[name] = fk_ctls

    def digits_ik(self, leg):
        """(Pendiente) IK de dedos, si el plano lo pide."""
        pass

    def digits_attributes(self, leg):
        """
        Control de atributos de los dedos con Curl, Spread y Twist (-10..10,
        default 0, convención de mano del repo).

        PENDIENTE: el cableado SDK a los grupos SDK de las falanges (recorrido
        decreciente proximal->distal en el curl, spread solo en la proximal,
        espolón aparte con su propio rango) — ver attributes_setup del
        digits_module de referencia.
        """
        
        self.paw_attributes_grp, self.paw_attributes_ctl = curve_tool.create_controller(
            name=f"{self.finger_base_name}sAttributes",
            offset=["GRP", "OFF", "ANM"],
            locked_attrs=["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"],
            parent=leg.controllers_grp,
        )

        cmds.addAttr(self.paw_attributes_ctl, longName="extraAttr", niceName="EXTRA ATTRIBUTES ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{self.paw_attributes_ctl}.extraAttr", ch=True, lock=True)

        def _f_attr(ln):
            cmds.addAttr(self.paw_attributes_ctl, longName=ln, attributeType="float",
                        minValue=-10, maxValue=10, defaultValue=0, keyable=True)

        _f_attr("Curl")
        _f_attr("Spread")
        _f_attr("Twist")

        

BackLegModule.FOOT_CLASS = HoofFoot
FrontLegModule.FOOT_CLASS = HoofFoot


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