"""Shared guide prerequisites for rig modules and character pickers (no Maya)."""

# Each alternative is a tuple of guides that must all exist.
REQUIREMENTS = {
    "spine": [("C_spine00_JNT",)],
    "leg": [("L_hip_JNT", "R_hip_JNT")],
    "front_leg": [("L_frontLegShoulder_JNT", "R_frontLegShoulder_JNT")],
    "front_limb": [("L_frontLeg_JNT", "R_frontLeg_JNT")],
    "back_leg": [("L_backLegHip_JNT", "R_backLegHip_JNT")],
    "clavicle": [("L_clavicle_JNT", "R_clavicle_JNT")],
    "arm": [("L_shoulder_JNT", "R_shoulder_JNT")],
    "fingers": [("L_thumb00_JNT", "R_thumb00_JNT")],
    "tail": [("C_tail00_JNT",)],
    "neck": [("C_neck00_JNT",)],
    "jaw": [("C_jaw_JNT",)],
    "eyebrow": [("L_eyebrowMain_JNT", "R_eyebrowMain_JNT"),
                ("L_eyebrow_CRVShape", "R_eyebrow_CRVShape")],
    "eye": [("L_eye_JNT", "R_eye_JNT")],
    "tongue": [("C_tongue00_JNT",)],
    "teeth": [("C_upperTeeth_JNT",)],
    "ear": [("L_ear00_JNT", "R_ear00_JNT")],
    "nose": [("C_nose_JNT",)],
    "cheekbone": [("L_cheekbone_JNT", "R_cheekbone_JNT")],
}


def enabled(guides, module):
    if module == "basic":
        return bool(guides)
    return any(all(name in guides for name in alternative)
               for alternative in REQUIREMENTS[module])


def active_modules(guides, rig_type=0):
    result = {name: enabled(guides, name) for name in REQUIREMENTS}
    result["basic"] = bool(guides)
    result["leg"] &= rig_type == 0
    for name in ("front_leg", "front_limb", "back_leg"):
        result[name] &= rig_type == 1
    result["front_limb"] &= not result["front_leg"]
    return result
