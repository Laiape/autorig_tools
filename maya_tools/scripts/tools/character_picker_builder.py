"""Guide-driven picker planning and assets, usable outside Maya."""
import copy
import html
import json
import math
from pathlib import Path
import re
import uuid

try:
    from utils.module_guides import active_modules
except ImportError:
    from maya_tools.scripts.utils.module_guides import active_modules

ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT/"maya_tools/assets"
FACE_MODULES = {"jaw", "eye", "eyebrow", "nose", "ear", "cheekbone", "teeth", "tongue"}
COLORS = {"L": "#43469b", "R": "#b43d4e", "C": "#ddca32"}
SECONDARY_COLORS = {"L": "#82b9ed", "R": "#ed96b0", "C": "#60ac70"}


def latest(directory, extension):
    files = list(Path(directory).glob("*."+extension))
    if not files:
        raise FileNotFoundError("No .%s source in %s" % (extension, directory))
    return max(files, key=lambda p: (int(re.search(r"_v(\d+)", p.stem).group(1))
                                   if re.search(r"_v(\d+)", p.stem) else 0, p.name))


def character_asset(name):
    candidates = [p for p in ASSETS.iterdir() if p.is_dir() and p.name.lower() == name.lower()]
    if len(candidates) != 1:
        raise ValueError("Expected one character asset: " + name)
    return candidates[0]


def owner(name):
    part = name.split("_", 1)[-1].removesuffix("_CTL")
    if part in ("character", "masterwalk", "settings"):
        return "basic"
    for word, module in [("frontLeg", "front_leg"), ("backLeg", "back_leg"),
                         ("eyebrow", "eyebrow"), ("eyelid", "eye"),
                         ("upperEyelid", "eye"), ("downEyelid", "eye"),
                         ("eye", "eye"), ("ear", "ear"), ("tongue", "tongue"),
                         ("tail", "tail"), ("clavicle", "clavicle"),
                         ("cheek", "cheekbone"), ("spine", "spine"),
                         ("neck", "neck"), ("head", "neck")]:
        if part.startswith(word):
            return module
    if "Socket" in part:
        return "eye"
    if "Teeth" in part:
        return "teeth"
    if "ose" in part:
        return "nose"
    if part == "face":
        return "face"
    if any(word in part.lower() for word in ("lip", "mouth", "jaw")):
        return "jaw"
    if part in ("body", "localHip", "localChest"):
        return "spine"
    if any(part.startswith(f) for f in ("thumb", "index", "middle", "ring", "pinky", "fingers")):
        return "fingers"
    if part.startswith(("arm", "shoulder", "elbow", "wrist")):
        return "arm"
    if part.startswith(("leg", "hip", "knee", "ankle", "ball", "toe", "bank", "heel")):
        return "leg"
    return None


def point(data):
    matrix = data.get("joint_matrix") or data.get("matrix") or data.get("locator_position")
    if matrix:
        return list(matrix[12:15])
    for key in ("curve_data", "surface_data"):
        cvs = data.get(key, {}).get("cvs", [])
        if cvs:
            # Surfaces can store a nested U/V grid.
            while isinstance(cvs[0][0], (list, tuple)):
                cvs = [p for row in cvs for p in row]
            return [sum(p[i] for p in cvs)/len(cvs) for i in range(3)]
    return None


def lerp(a, b, fraction):
    return [x+(y-x)*fraction for x, y in zip(a, b)]


def anchor(name, module, guides, names):
    side, part = name.split("_", 1)
    part = part.removesuffix("_CTL")
    positions = {n: point(d) for n, d in guides.items()}
    positions = {n: p for n, p in positions.items() if p is not None}
    direct = side+"_"+part+"_JNT"
    if module == "fingers" and part != "fingersAttributes":
        digit = re.match(r"(thumb|index|middle|ring|pinky)", part)
        if not digit or side+"_"+digit.group(1)+"00_JNT" not in positions:
            raise ValueError("Missing digit root guide for " + name)
    if direct in positions:
        return positions[direct], direct
    def get(key):
        if key not in positions:
            raise ValueError("No positional guide " + key + " for " + name)
        return positions[key], key
    if module == "fingers" and part != "fingersAttributes":
        # Never add a digit from an old curve export when its guide was removed.
        raise ValueError("Missing digit guide: " + direct)
    if module in ("arm", "leg"):
        keys = ("shoulder", "elbow", "wrist") if module == "arm" else ("hip", "knee", "ankle")
        if "Bendy" in part:
            a, b = (keys[:2] if "Upper" in part else keys[1:])
            fraction = .25 if "Up" in part.replace("Upper", "") else .75 if "Low" in part.replace("Lower", "") else .5
            return lerp(get(side+"_"+a+"_JNT")[0], get(side+"_"+b+"_JNT")[0], fraction), side+"_"+a+"_JNT"
        aliases = {"shoulderFk": "shoulder", "elbowFk": "elbow", "wristFk": "wrist", "armIkRoot": "shoulder",
                   "armIkWrist": "wrist", "armPv": "elbow", "armSettings": "wrist", "legRootIk": "hip",
                   "hipFk": "hip", "kneeFk": "knee", "ankleFk": "ankle", "ankleIk": "ankle",
                   "ballFk": "ball", "ballIk": "ball", "toeIk": "tip", "legPv": "knee", "legSettings": "ankle"}
        if part in ("heel", "bankIn", "bankOut"):
            key = side+"_"+part+"_LOCShape"
            if key in positions:
                return get(key)
        return get(side+"_"+aliases.get(part, keys[-1])+"_JNT")
    if module == "spine":
        chain = sorted(n for n in positions if re.fullmatch(r"C_spine\d+_JNT", n))
        index = re.search(r"spine(\d+)", part)
        fraction = int(index.group(1))/max(1, len(chain)-1) if index else 1 if part == "localChest" else 0
        return lerp(positions[chain[0]], positions[chain[-1]], min(1, fraction)), chain[0]
    if module == "neck":
        chain = sorted(n for n in positions if re.fullmatch(r"C_neck\d+_JNT", n))
        return get(chain[-1] if part == "head" else chain[0])
    if module == "basic":
        return get("C_spine00_JNT" if "C_spine00_JNT" in positions else sorted(positions)[0])
    if module == "fingers":
        return get(side+"_thumb00_JNT")
    if module == "eye":
        band = "Upper" if part.startswith("upperEyelid") or "Up" in part else "Lower"
        curve = side+"_eyelid"+band+"Linear_CRVShape"
        cvs = guides.get(curve, {}).get("curve_data", {}).get("cvs", [])
        if cvs and ("Eyelid" in part or "eyelid" in part):
            group = sorted((n for n in names if n.startswith(side+"_"+("upperEyelid" if band == "Upper" else "downEyelid"))), key=lambda n: int(re.search(r"Eyelid(\d+)", n).group(1)))
            if name in group:
                index = round(group.index(name)/max(1, len(group)-1)*(len(cvs)-1))
            else:
                index = 0 if "In" in part else len(cvs)-1 if "Out" in part else len(cvs)//2
            return list(cvs[index][:3]), curve
        if side == "C":
            keys = [n for n in ("L_eye_JNT", "R_eye_JNT") if n in positions]
            return [sum(positions[n][i] for n in keys)/len(keys) for i in range(3)], keys
        return get(side+"_eye_JNT")
    if module == "eyebrow":
        chain = sorted(n for n in positions if re.fullmatch(side+r"_eyebrow\d+_JNT", n))
        curve = side+"_eyebrow_CRVShape"
        if not chain and curve in guides:
            cvs = guides[curve].get("curve_data", {}).get("cvs", [])
            if cvs:
                ordered = sorted(cvs, key=lambda p: abs(p[0]))
                fraction = 0 if "In" in part and "Tan" not in part else .25 if "InTan" in part else 1 if "Out" in part and "Tan" not in part else .75 if "OutTan" in part else .5
                return list(ordered[round(fraction*(len(ordered)-1))][:3]), curve
        if side == "C":
            return get("C_eyebrowMid_JNT" if "C_eyebrowMid_JNT" in positions else "L_eyebrowMain_JNT")
        if chain and part != "eyebrowMain":
            fraction = .0 if "In" in part and "Tan" not in part else .25 if "InTan" in part else .75 if "OutTan" in part else 1 if "Out" in part else .5
            # Order by distance to the face center, independent of guide numbering.
            chain.sort(key=lambda n: abs(positions[n][0]))
            return lerp(positions[chain[0]], positions[chain[-1]], fraction), chain[0]
        return get(side+"_eyebrowMain_JNT")
    if module == "jaw":
        band = "upper" if "upper" in part.lower() else "lower"
        curve = "C_"+band+"LipLinear_CRVShape"
        cvs = guides.get(curve, {}).get("curve_data", {}).get("cvs", [])
        if cvs and ("Lip" in part or "lip" in part or part == "mainMouth"):
            ordered = sorted(cvs, key=lambda p: p[0])
            fraction = .0 if side == "R" else 1 if side == "L" else .5
            digits = re.search(r"Lip(\d+)", part)
            if digits:
                fraction = .1+min(3, int(digits.group(1)))*.1 if side == "R" else .9-min(3, int(digits.group(1)))*.1 if side == "L" else .5
            return list(ordered[round(fraction*(len(ordered)-1))][:3]), curve
        return get("C_jaw_JNT")
    if module == "nose":
        return get("C_nose_JNT")
    if module == "cheekbone":
        return get(side+"_cheekbone_JNT")
    if module == "face":
        keys = [n for n in ("L_eye_JNT", "R_eye_JNT", "C_jaw_JNT") if n in positions]
        if not keys:
            keys = [n for n in positions if any(word in n.lower() for word in ("ear", "nose", "tongue", "teeth", "cheek", "eyebrow"))]
        if not keys:
            raise ValueError("No positional face guide for " + name)
        return [sum(positions[n][i] for n in keys)/len(keys) for i in range(3)], keys
    # Tail and quadruped controls vary by module; nearest matching root is explicit.
    roots = {"ear": side+"_ear00_JNT", "tongue": "C_tongue00_JNT", "teeth": "C_upperTeeth_JNT",
             "tail": "C_tail00_JNT", "front_leg": side+"_frontLegShoulder_JNT",
             "front_limb": side+"_frontLeg_JNT", "back_leg": side+"_backLegHip_JNT"}
    return get(roots[module])


def fitted_bounds(points, width, height, padding=.16):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    span_x, span_y = max(max(xs)-min(xs), .01), max(max(ys)-min(ys), .01)
    span_x *= 1+padding*2
    span_y *= 1+padding*2
    span_x = max(span_x, span_y*width/height)
    span_y = span_x*height/width
    cx, cy = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2
    return [cx-span_x/2, cy-span_y/2, cx+span_x/2, cy+span_y/2]


def make_shape(name, panel, x, y, w, h, color, layer=None, label="", targets=None):
    return {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, "guide-picker:%s:%s" % (panel, name))),
            "panel": panel, "background": False, "visibility_layer": layer,
            "shape": "rounded_rect" if label else "round", "shape.left": x-w/2, "shape.top": y-h/2,
            "shape.width": w, "shape.height": h, "shape.path": [], "shape.cornersx": h/2,
            "shape.cornersy": h/2, "text.content": label, "text.size": 10, "text.color": "#141414",
            "bgcolor.normal": color, "bordercolor.normal": "#101015",
            "action.targets": targets if targets is not None else [name], "action.commands": [],
            "image.path": "", "children": []}


def plan(character, guides, control_names, settings=None, overrides=None):
    settings, overrides = settings or {}, overrides or {}
    if not guides:
        raise ValueError("Picker requires exported guides for " + character)
    modules = active_modules(guides, settings.get("Rig_Type", 0))
    modules["face"] = any(modules[m] for m in FACE_MODULES)
    controls, skipped = [], []
    names = sorted(set(control_names))
    for name in names:
        module = owner(name)
        if module == "front_leg" and not modules["front_leg"] and modules["front_limb"]:
            module = "front_limb"
        if not module or not modules.get(module):
            skipped.append({"name": name, "reason": "missing module guides" if module else "unclassified control", "module": module})
            continue
        try:
            location, guide = anchor(name, module, guides, names)
        except (ValueError, KeyError, IndexError) as error:
            skipped.append({"name": name, "reason": str(error), "module": module})
            continue
        panel = 1 if module in FACE_MODULES or module == "face" else 0
        controls.append({"name": name, "module": module, "panel": panel, "guide": guide, "world": location})
    panels = []
    for index in range(2):
        options = overrides.get("panels", {}).get("body" if index == 0 else "face", {})
        size = options.get("size", [750, 1000])
        if len(size) != 2 or any(not math.isfinite(v) or v < 100 for v in size):
            raise ValueError("Invalid picker panel dimensions")
        points = [c["world"] for c in controls if c["panel"] == index]
        if index == 0:
            points += [p for d in guides.values() if d.get("isJoint") and (p := point(d)) is not None]
        bounds = options.get("world_bounds") or fitted_bounds(points or [[-.5, 0, 0], [.5, 1, 0]], *size)
        if len(bounds) != 4 or any(not math.isfinite(v) for v in bounds) or bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
            raise ValueError("Invalid picker world bounds")
        panels.append({"size": size, "world_bounds": bounds, "projection": "XY", "background": "backgrounds/%s.svg" % ("body" if index == 0 else "face")})
    shapes = []
    module_measurements = {}
    for module in sorted({c["module"] for c in controls}):
        group = [c for c in controls if c["module"] == module]
        bounds = panels[group[0]["panel"]]["world_bounds"]
        width = panels[group[0]["panel"]]["size"][0]
        span = max(max(c["world"][axis] for c in group)-min(c["world"][axis] for c in group) for axis in (0, 1))
        projected = span/(bounds[2]-bounds[0])*width
        module_measurements[module] = {"guide_span": span, "projected_span": projected,
                                       "primary_size": min(32, max(12, projected*.10))}
    for c in controls:
        panel = panels[c["panel"]]
        width, height = panel["size"]
        xmin, ymin, xmax, ymax = panel["world_bounds"]
        x, y = (c["world"][0]-xmin)/(xmax-xmin)*width, (ymax-c["world"][1])/(ymax-ymin)*height
        name = c["name"]
        layer = "Fine eyelids" if re.search(r"(?:upper|down)Eyelid\d", name) else "Secondary" if any(t in name for t in ("Bendy", "Attatched", "Tan", "Socket")) or re.search(r"(?:Lip|eyebrow|cheekbone|tongue)\d", name) or c["module"] == "fingers" and not name.endswith("00_CTL") else None
        dimension = module_measurements[c["module"]]["primary_size"] if layer is None else min(14, max(7, width*.012))
        if layer == "Fine eyelids":
            dimension = max(5, width*.008)
        label = ""
        h = dimension
        if c["module"] == "basic":
            label = name.split("_")[1].title()
            x = width*.5
            y = height*(.94 if "masterwalk" in name else .97 if "character" in name else .055)
            dimension, h = width*.24, height*.022
        if "Settings" in name:
            label = "IK FK"
            dimension, h = width*.085, height*.024
            x += -40 if name.startswith("R_") else 40
        if name in ("C_face_CTL", "C_head_CTL", "C_jaw_CTL"):
            label = name.split("_")[1].title()
            dimension, h = width*.09, height*.025
            y += -30 if "face" in name else 25
        if "Pv" in name:
            x += -45 if name.startswith("R_") else 45
        if "Ik" in name or "Direct" in name:
            x += -18 if name.startswith("R_") else 18
        if layer == "Secondary" and c["module"] in ("arm", "leg"):
            x += -16 if name.startswith("R_") else 16
        custom = overrides.get("controls", {}).get(name, {})
        x, y = custom.get("position", [x, y])
        if not all(math.isfinite(v) for v in (x, y)):
            raise ValueError("Invalid control position: " + name)
        dimension, h = custom.get("size", [dimension, h])
        if not all(math.isfinite(v) and v > 0 for v in (dimension, h)):
            raise ValueError("Invalid control size: " + name)
        if dimension > width-4 or h > height*.965-2:
            raise ValueError("Control does not fit its panel: " + name)
        color = SECONDARY_COLORS[name[0]] if c["panel"] == 1 and layer else COLORS[name[0]]
        c.update({"x": x, "y": y, "size": [dimension, h], "layer": layer})
        shapes.append(make_shape(name, c["panel"], x, y, dimension, h, color, layer, label))
    # Keep each button clickable, including several controls attached to one guide.
    placed = []
    for shape in sorted(shapes, key=lambda s: -s["shape.width"]*s["shape.height"]):
        width, height = panels[shape["panel"]]["size"]
        def constrain():
            shape["shape.left"] = min(width-shape["shape.width"]-2, max(2, shape["shape.left"]))
            shape["shape.top"] = min(height-shape["shape.height"]-2, max(height*.035, shape["shape.top"]))
        constrain()
        base_x, base_y = shape["shape.left"], shape["shape.top"]
        for attempt in range(4000):
            if not any(s["panel"] == shape["panel"] and
                       shape["shape.left"] < s["shape.left"]+s["shape.width"]+2 and
                       shape["shape.left"]+shape["shape.width"]+2 > s["shape.left"] and
                       shape["shape.top"] < s["shape.top"]+s["shape.height"]+2 and
                       shape["shape.top"]+shape["shape.height"]+2 > s["shape.top"] for s in placed):
                break
            angle = attempt*2.399963229728653
            radius = 4*math.sqrt(attempt+1)
            shape["shape.left"] = base_x+math.cos(angle)*radius
            shape["shape.top"] = base_y+math.sin(angle)*radius
            constrain()
        else:
            raise ValueError("Cannot place control without overlap: " + shape["action.targets"][0])
        placed.append(shape)
    for control, shape in zip(controls, shapes):
        control["pixel_bounds"] = [shape[k] for k in ("shape.left", "shape.top", "shape.width", "shape.height")]
    for panel in range(2):
        targets = [c["name"] for c in controls if c["panel"] == panel]
        if not targets:
            continue
        width, height = panels[panel]["size"]
        for label, selected, x in [("Select Body" if panel == 0 else "Select Face", targets, width*.15),
                                   ("Select All", [c["name"] for c in controls], width*.36)]:
            shapes.append(make_shape(label, panel, x, height*.018, width*.19, height*.025, "#989898", label=label, targets=selected))
    config = {"schema_version": 1, "character": character, "panels": panels, "enabled_modules": modules,
              "module_measurements": module_measurements,
              "size_policy": {"primary": "10% projected module guide span, clamped 12..32 px", "secondary": "1.2% panel width, clamped 7..14 px", "fine": "0.8% panel width, minimum 5 px"}}
    document = {"general": {"name": character+" Picker", "version": [1, 0, 4], "panels.names": ["Body", "Face"],
                            "panels": [[1.0, [1.0]], [1.0, [1.0]]], "hidden_layers": ["Fine eyelids"]}, "shapes": shapes}
    return document, config, {"character": character, "controls": controls, "skipped": skipped,
                              "body": sum(c["panel"] == 0 for c in controls), "face": sum(c["panel"] == 1 for c in controls)}


def build(character, guides=None, control_names=None, output=None):
    asset = character_asset(character)
    guides_file, settings_file = latest(asset/"guides", "guides"), latest(asset/"build", "build")
    guides = guides if guides is not None else json.loads(guides_file.read_text())[asset.name]
    curves_file = latest(asset/"curves", "curves") if control_names is None else None
    names = control_names if control_names is not None else [v["transform"]["name"] for v in json.loads(curves_file.read_text()).values()]
    profile = asset/"picker/picker_profile.json"
    if not profile.exists():
        profile.parent.mkdir(parents=True, exist_ok=True)
        profile.write_text(json.dumps({"schema_version": 1, "panels": {"body": {"size": [750, 1000]},
                                      "face": {"size": [750, 1000]}}, "controls": {}}, indent=2), encoding="utf-8")
    overrides = json.loads(profile.read_text()) if profile.is_file() else {}
    document, config, report = plan(asset.name, guides, names, json.loads(settings_file.read_text()), overrides)
    report["sources"] = {"guides": str(guides_file.relative_to(ROOT)), "curves": str(curves_file.relative_to(ROOT)) if curves_file else "live scene controls", "settings": str(settings_file.relative_to(ROOT))}
    output = Path(output or asset/"picker/generated")
    output.mkdir(parents=True, exist_ok=True)
    for filename, data in [("picker.json", document), ("picker_config.json", config), ("build_report.json", report)]:
        (output/filename).write_text(json.dumps(data, indent=2), encoding="utf-8")
    write_backgrounds(output, config, guides, report)
    return output


def write_backgrounds(output, config, guides, report):
    """Draw actual guide proportions in the same coordinate frame as the controls.

    No model/rig is redistributed. A profile may supply a matching custom image.
    """
    for index, panel in enumerate(config["panels"]):
        width, height = panel["size"]
        xmin, ymin, xmax, ymax = panel["world_bounds"]
        def project(p):
            return ((p[0]-xmin)/(xmax-xmin)*width, (ymax-p[1])/(ymax-ymin)*height)
        coordinates = {}
        for name, data in guides.items():
            p = point(data)
            if p is not None and (index == 0 or ymin <= p[1] <= ymax):
                coordinates[name] = project(p)
        parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="0 0 %s %s">' % (width, height, width, height),
                 '<rect width="100%" height="100%" fill="#989898"/>',
                 '<text x="%s" y="%s" text-anchor="middle" font-family="sans-serif" font-size="16" fill="#333333">%s | Guide layout</text>' % (width/2, height*.09, html.escape(config["character"]))]
        for name, (x, y) in coordinates.items():
            data = guides[name]
            parent = data.get("parent") or data.get("joint_parent")
            if isinstance(parent, list):
                parent = parent[0] if parent else None
            if parent in coordinates:
                px, py = coordinates[parent]
                parts.append('<path d="M %.2f %.2f L %.2f %.2f" stroke="#666666" stroke-width="5"/>' % (x, y, px, py))
            parts.append('<circle cx="%.2f" cy="%.2f" r="3" fill="#777777"/>' % (x, y))
            for curve in (data.get("curve_data"),):
                if curve and curve.get("cvs"):
                    path = ' '.join(('M' if i == 0 else 'L')+' %.2f %.2f' % project(p) for i, p in enumerate(curve["cvs"]))
                    parts.append('<path d="%s" fill="none" stroke="#777777" stroke-width="3"/>' % path)
        parts.append('</svg>')
        path = Path(output)/panel["background"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('\n'.join(parts), encoding="utf-8")


def package(directory):
    """Emit the same portable installer for every character, excluding models."""
    import base64
    import io
    import shutil
    import zipfile
    directory = Path(directory)
    for filename in ("character_picker_runtime.py", "character_picker_scene.py", "install_character_picker.py"):
        shutil.copy2(Path(__file__).parent/filename, directory/filename)
    config = json.loads((directory/"picker_config.json").read_text(encoding="utf-8"))
    files = ["picker.json", "picker_config.json", "build_report.json", "character_picker_runtime.py",
             "install_character_picker.py", "character_picker_scene.py"] + [p["background"] for p in config["panels"]]
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for filename in files:
            bundle.write(directory/filename, filename)
    destination = directory.parent/(config["character"]+"_Picker_Installer.py")
    destination.write_text('''"""Drag into Maya 2024+ to install the character picker. Rig not included."""
import base64
import importlib.util
import io
from pathlib import Path
import tempfile
import zipfile

PAYLOAD = '''+repr(base64.b64encode(archive.getvalue()).decode("ascii"))+'''

def install():
    with tempfile.TemporaryDirectory(prefix="character_picker_") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(PAYLOAD))) as bundle:
            bundle.extractall(root)
        spec = importlib.util.spec_from_file_location("character_picker_installer", str(root/"install_character_picker.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.install(root)

def onMayaDroppedPythonFile(*_):
    return install()

if __name__ == "__main__":
    install()
''', encoding="utf-8")
    return destination


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("character")
    args = parser.parse_args()
    print(package(build(args.character)))
