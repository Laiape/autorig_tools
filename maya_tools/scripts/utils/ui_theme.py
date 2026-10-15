"""Explicit visual hierarchy for AutoRig's native Maya editors.

Only listed actions receive a colored fill. Labels are presentation metadata;
styling never changes callbacks, enabled state, shortcuts or default actions.
"""

COLORS = {
    "primary": "#356581",
    "success": "#386b56",
    "warning": "#765d32",
    "danger": "#8c4648",
}

# The user prefers Skinning Manager, including its embedded editors, native.
NATIVE_ONLY = {"SkinningManager"}


def profile(title, icon, primary=(), success=(), warning=(), danger=(), header=True):
    return dict(title=title, icon=icon, primary=primary, success=success,
                warning=warning, danger=danger, header=header)


PROFILES = {
    "ToolFramework": profile("AutoRig Tools", "framework", primary=("Open tool", "Run action")),
    "AssetManagerUI": profile("Character Manager", "character", primary=("BUILD RIG",),
        success=("SAVE VERSION",), danger=("DELETE ASSET",)),
    "VersionTab": profile("Asset versions", "character", success=("SAVE VERSION",),
        primary=("IMPORT SELECTED", "QC RUN"), header=False),
    "QuickToolsWidget": profile("Rig workflow", "tools", primary=("Quick Bind (sel jnts + mesh)", "Assign Proxy Locators"),
        success=("Copy Skin Weights",), warning=("Reset All CTLs",),
        danger=("Unbind Skin", "Remove Proxy Locators", "Delete History", "Delete Unused Nodes"), header=False),
    "ModelCheckerWindow": profile("Model Checker", "model", primary=("Run all checks",),
        success=("Repair selected finding", "Export JSON"), warning=("Compare vertex sets",)),
    "SkinningManager": profile("Skinning Manager", "skin", primary=("Bind selected joints + mesh",),
        success=("Normalize weights", "Import skin (.skc)", "Export skin (.skc)")),
    "BrushPanel": profile("Skinning brush", "skin", primary=("PAINT SMOOTH", "PAINT TRANSFER"), header=False),
    "NGPanel": profile("Skin layers", "skin", header=False),
    "LoopRiggerPanel": profile("Loop Rigger", "skin", primary=("3. Create NG group + joint layers", "3. Create / update region layers"),
        warning=("2. Preview complete columns",), header=False),
    "PoseBlendshapesUI": profile("Pose Blendshapes", "corrective", primary=("Add", "Create combination from selected targets..."),
        success=("Save sculpt",), warning=("LIVE",), danger=("Delete", "Cancel sculpt")),
    "TransferDialog": profile("Transfer Corrective Sculpt", "transfer", primary=("Transfer saved sculpt",)),
    "CaptureDialog": profile("Capture Corrective Pose", "pose", primary=("Add and sculpt",)),
    "JointCorrectivesUI": profile("Joint Corrective Targets", "corrective", primary=("Create region", "Add joint at selected vertices", "Add target"),
        success=("Save edit", "Apply driver and range"), warning=("Edit",), danger=("Delete target", "Cancel edit")),
    "CorrectiveCurveUI": profile("Corrective Curve", "curve", primary=("Create / Add pose",),
        success=("Bind curve to selected joints",)),
    "DeBoorToolsUI": profile("De Boor Tools", "curve", primary=("Create De Boor Ribbon", "Split Blendshape Targets", "Split Skin Weights", "Split Skin Weights (Surface)")),
    "SkinTransferUI": profile("Auto Skin Transfer", "transfer", primary=("TRANSFER SKINNING",), warning=("Preview Joint Map...",)),
    "JointMapDialog": profile("Joint Mapping", "transfer"),
    "DeformationBakeUI": profile("Bake Deformation to Skin", "bake", primary=("Bake selection to Skin",)),
    "PoseTesterUI": profile("Rig Pose Tester", "pose", primary=("Full Body ROM", "Combination poses + report"),
        success=("Apply last tested local DQ mask",), danger=("Clear Test Anim",)),
    "GeneralRigPanel": profile("General rig tools", "rig", primary=("Run profile on loaded meshes...", "Measure current pose", "Compare library poses on loaded meshes..."),
        success=("Bind selected node to this role", "Apply selected pose to free controls", "Apply compatible migration to fresh destination"),
        warning=("Preview migration from loaded character",), header=False),
    "WrinkleRegionsUI": profile("Wrinkle Regions / Presets", "wrinkle", primary=("Create empty regions", "Assign selected vertices"),
        success=("Apply preset...", "Export preset..."), danger=("Clear region",)),
    "RigPackageUI": profile("Validated Rig Packages", "package", primary=("Create frozen candidate from current asset", "Validate candidate in isolated Maya", "Rebuild validated package in a fresh scene")),
    "RigToolsUI": profile("Rig Tools", "tools", primary=("TRACE ARC", "TO LOCATORS", "FROM LOCATORS", "PARENT SHAPE (Ctrl+P)"),
        success=("APPLY", "APPLY GRADIENT", "SWITCH ROTATION ORDER"), warning=("RESET SELECTED TO DEFAULTS",), danger=("CLEAR", "CLEAR COLOR OVERRIDES")),
    "CurveLibraryUI": profile("Controller Shape Library", "controller", primary=("APPLY TO SELECTED",),
        success=("SAVE FROM SEL",), danger=("DELETE",)),
    "RigProgressDialog": profile("Rig Build Progress", "rig", header=False),
    "CharacterPicker": profile("Character Picker", "picker", primary=("Use Selection",), header=False),
    "NativeProximityWrap": profile("Proximity Wrap", "wrap", primary=("Aplicar a cinturones seleccionados",)),
    "NativeNewAsset": profile("Create New Asset", "character", primary=("Create Folders",)),
    "NativeAdonisWeights": profile("AdonisFX Copy Weights", "simulation", primary=("COPY WEIGHTS", "COPY", "MIRROR L -> R", "REPLACE MESH IN SETUP"), success=("PASTE",), header=False),
}

# Icons for secondary actions stay neutral. No inferred action receives a fill.
ACTION_ICONS = {
    "refresh": "reload", "load mesh": "import", "from selection": "import",
    "load selected": "import", "load selected meshes": "import", "load channel": "controller",
    "load profile": "import", "save profile": "export", "load library": "import", "save library": "export",
    "copy report": "export", "export json": "export", "load review from json": "import",
    "select in maya": "picker", "compare vertex sets": "model", "run selected checks": "model",
    "favorite": "favorite", "favorited": "favorite", "float dock": "framework",
    "choose package": "package", "choose": "import", "pick": "picker",
    "new": "guide", "add": "corrective", "edit": "corrective", "delete": "tools",
    "save sculpt": "export", "save edit": "export", "live": "pose",
    "import selected": "import", "save version": "export", "run qc": "model",
    "export preset": "export", "apply preset": "import", "neutral pose": "pose",
    "mirror counterpart dependencies": "mirror", "transfer sculpt to mesh lod": "transfer",
}

TAB_ICONS = {
    "automatic checks": "model", "visual review": "model", "vertex comparison": "model", "report": "export",
    "skinning": "skin", "ng": "skin", "layers paint": "skin", "loop rigger preview": "skin",
    "smooth": "skin", "transfer": "transfer", "ramp": "curve", "utilities": "tools",
    "corrective blendshapes": "corrective", "de boor ribbon": "curve", "split blendshape": "corrective",
    "skin curve": "curve", "skin surface": "wrap", "rig roles": "rig", "validation profiles": "model",
    "pose library": "pose", "surface contact": "model", "version migration": "transfer",
    "guides": "guide", "curves": "curve", "models": "model", "skin clusters": "skin", "tools": "tools",
}

# Also protect controls that were already open before a theme reload.
FUNCTIONAL_STYLES = {
    "PoseBlendshapesUI": ("live",),
    "CurveLibraryUI": ("color_btn",),
    "RigToolsUI": ("solid_swatch", "swatch_a", "swatch_b"),
}
VENDOR_BOUNDARIES = {"NGPanel": ("native_ui",), "BrushPanel": ("controls",)}
VENDOR_ACTIONS = {
    "NGPanel": {"Paint": ("primary", "skin"), "Flood": ("success", "skin"),
                "Initialize Skinning Layers": ("primary", "skin")},
    "BrushPanel": {"Flood": ("success", "skin")},
    "RampPanel": {"Apply": ("primary", "curve"), "Create": ("primary", "curve")},
}
