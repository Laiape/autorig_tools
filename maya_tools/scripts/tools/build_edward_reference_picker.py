"""Build Edward's photo picker and independent vector control assets.

Run with ordinary Python; Maya is required only to load the resulting picker.
The source photograph is embedded unchanged in native SVG backgrounds.
"""
import base64
import copy
import html
import json
import math
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[3]
ASSET = ROOT / "maya_tools/assets/Edward"
OUT = ASSET / "picker/reference_workflow"
W, H = 750, 1000
COLORS = {"R": "#b43d4e", "L": "#43469b", "C": "#ddca32"}
FACE_SECONDARY_COLORS = {"R": "#ed96b0", "L": "#82b9ed"}
TEAL, GREEN, GOLD = "#12b4cb", "#60ac70", "#d79f32"
PHOTO = "data:image/png;base64," + base64.b64encode((OUT / "edward_reference_sheet.png").read_bytes()).decode()
FACE_PHOTO = "data:image/png;base64," + base64.b64encode((OUT / "edward_face_front_hd.png").read_bytes()).decode()
CURVES = json.loads((ASSET / "curves/Edward_v001.curves").read_text())
NAMES = {v["transform"]["name"] for v in CURVES.values()}
TEMPLATE = next(s for s in json.loads((ASSET / "picker/Edward_picker.json").read_text())["shapes"] if not s["background"])
CONTROLS = []


def add(name, panel, x, y, width=22, height=None, kind="round", label="", color=None, angle=0, layer=None):
    if name not in NAMES:
        raise ValueError("Unknown Edward controller: " + name)
    height = width if height is None else height
    if panel == 1 and layer in ("Secondary", "Fine eyelids") and name[0] in FACE_SECONDARY_COLORS:
        color = FACE_SECONDARY_COLORS[name[0]]
    c = dict(name=name, panel=panel, x=x, y=y, w=width, h=height,
             kind=kind, label=label, color=color or COLORS[name[0]], angle=angle, layer=layer)
    CONTROLS.append(c)
    return c


def body_point(x, y):
    return 60 + x - 875, 115 + y - 20


def face_point(x, y):
    return 85 + (x - 35) * 4, 115 + (y - 5) * 4


def body():
    def at(name, x, y, **kw):
        return add(name, 0, *body_point(x, y), **kw)
    add("C_character_CTL", 0, 375, 961, 310, 20, "pill", "Global", GOLD)
    add("C_masterwalk_CTL", 0, 375, 932, 220, 15, "pill", "Master", GOLD)
    add("C_settings_CTL", 0, 666, 133, 58, 56, "hex", "Settings", GOLD)
    at("C_head_CTL", 1174, 113, width=46, height=43, kind="hex", label="Head")
    at("C_neck_CTL", 1174, 199, width=65, height=10, kind="pill")
    at("C_localChest_CTL", 1175, 253, width=99, height=17, kind="trapezoid", color=GREEN)
    at("C_body_CTL", 1175, 396, width=155, height=14, kind="pill", label="COG", color=GOLD)
    at("C_localHip_CTL", 1175, 418, width=90, height=20, kind="trapezoid", color=GREEN)
    for name, y, x in [("C_spine00_CTL", 376, 1175), ("C_spine03_CTL", 315, 1175), ("C_spine07_CTL", 265, 1175)]:
        at(name, x, y, width=111, height=9, kind="pill")
    for i in range(1, 9):
        at("C_spine%02dAttatchedFk_CTL" % i, 1175, 393 - i * 16,
           width=11, color=GREEN, layer="Secondary")
    at("C_spine01Tan_CTL", 1175, 350, width=50, height=8, kind="pill", color=GREEN, layer="Secondary")
    at("C_spine06Tan_CTL", 1175, 279, width=50, height=8, kind="pill", color=GREEN, layer="Secondary")
    anchors = {
        "R": {"clavicle": (1138, 235), "shoulderFk": (1112, 265), "elbowFk": (1041, 332),
              "wristFk": (975, 394), "armIkWrist": (946, 420), "armPv": (1012, 300),
              "armIkRoot": (1072, 261), "fingersAttributes": (929, 534),
              "hipFk": (1150, 443), "kneeFk": (1148, 580), "ankleFk": (1143, 738),
              "legRootIk": (1110, 448), "legPv": (1068, 580), "ankleIk": (1137, 762),
              "ballFk": (1131, 773), "ballIk": (1121, 796), "toeIk": (1113, 780),
              "heel": (1146, 760), "bankIn": (1157, 782), "bankOut": (1096, 777)},
        "L": {"clavicle": (1214, 235), "shoulderFk": (1240, 265), "elbowFk": (1302, 331),
              "wristFk": (1367, 393), "armIkWrist": (1392, 420), "armPv": (1329, 300),
              "armIkRoot": (1265, 261), "fingersAttributes": (1417, 534),
              "hipFk": (1197, 443), "kneeFk": (1198, 580), "ankleFk": (1203, 738),
              "legRootIk": (1238, 448), "legPv": (1280, 580), "ankleIk": (1211, 762),
              "ballFk": (1218, 773), "ballIk": (1231, 796), "toeIk": (1233, 780),
              "heel": (1202, 760), "bankIn": (1188, 782), "bankOut": (1250, 777)}
    }
    for side, points in anchors.items():
        for part, (x, y) in points.items():
            name = side + "_" + part + "_CTL"
            if part == "clavicle":
                at(name, x, y, width=30, height=28, kind="triangle")
            elif part in ("shoulderFk", "elbowFk", "wristFk"):
                at(name, x, y, width=48, height=18, kind="pill", angle=-43 if side == "R" else 43)
            elif part in ("armPv", "legPv"):
                at(name, x, y, width=27, height=20, kind="diamond", color=TEAL if side == "L" else "#df8992")
            elif part == "fingersAttributes":
                at(name, x, y, width=68, height=16, kind="pill", label="Scissors", color=GOLD)
            elif part in ("armIkWrist", "ankleIk"):
                at(name, x, y, width=27, color=TEAL if side == "L" else "#ed96a0")
            else:
                at(name, x, y, width=14 if "Fk" in part else 12,
                   color=TEAL if side == "L" and "Ik" in part else None,
                   layer="Secondary" if part in ("bankIn", "bankOut") else None)
        for part, x, y in [("armSettings", 958 if side == "R" else 1395, 555),
                           ("legSettings", 1068 if side == "R" else 1280, 695)]:
            at(side + "_" + part + "_CTL", x, y, width=57, height=24, kind="pill", label="IK FK")
        # Digit roots follow the scissors; extra joints extend toward the body.
        for i, finger in enumerate(("thumb", "index", "middle", "ring", "pinky")):
            x = (930 - i * 10) if side == "R" else (1403 + i * 10)
            y = 437 + i * 14
            at(side + "_" + finger + "00_CTL", x, y, width=22, height=9, kind="pill")
            prefix = side + "_" + finger
            joints = sorted(n for n in NAMES if n.startswith(prefix) and n != prefix + "00_CTL")
            direction = 1 if side == "R" else -1
            for joint, name in enumerate(joints):
                at(name, x + direction * (25 + joint * 14), y,
                   width=9, layer="Secondary")
        for limb in ("arm", "leg"):
            for section in ("Upper", "Lower"):
                if limb == "arm":
                    a, b = points["shoulderFk"], points["elbowFk"]
                    if section == "Lower":
                        a, b = points["elbowFk"], points["wristFk"]
                else:
                    a, b = points["hipFk"], points["kneeFk"]
                    if section == "Lower":
                        a, b = points["kneeFk"], points["ankleFk"]
                for suffix, t in (("Up", .22), ("Main", .5), ("Low", .78)):
                    x, y = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                    at(side + "_" + limb + section + suffix + "Bendy_CTL", x, y,
                       width=9, color=TEAL if side == "L" else "#df8992", layer="Secondary")


def face():
    def at(name, x, y, **kw):
        return add(name, 1, *face_point(x, y), **kw)
    add("C_face_CTL", 1, 375, 140, 58, 58, "diamond", "Face", GOLD)
    add("C_eyeMain_CTL", 1, 573, 250, 95, 26, "pill", "Eyes")
    at("C_eyebrowMid_CTL", 109, 73, width=17, kind="diamond", color=GREEN)
    for side, ex, ey in (("R", 95, 90), ("L", 123, 90)):
        rx, ry = 9, 7.5
        at(side + "_eye_CTL", ex, ey, width=28)
        at(side + "_eyeDirect_CTL", ex, ey + 14, width=37, height=9, kind="pill", layer="Secondary")
        at(side + "_eyebrowMain_CTL", ex, ey - 15, width=76, height=14, kind="pill")
        brow_x = [ex + rx * t for t in (-.9, -.45, 0, .45, .9)]
        brow_parts = ["Out", "OutTan", "Mid", "InTan", "In"] if side == "R" else ["In", "InTan", "Mid", "OutTan", "Out"]
        for x, part in zip(brow_x, brow_parts):
            at(side + "_eyebrow" + part + "_CTL", x, ey - 15, width=8, layer="Secondary")
        offsets = {"In": (rx, 0), "InUp": (rx*.7, -ry*.7), "Up": (0, -ry), "OutUp": (-rx*.7, -ry*.7),
                   "Out": (-rx, 0), "OutDown": (-rx*.7, ry*.7), "Down": (0, ry), "InDown": (rx*.7, ry*.7)}
        for part, (dx, dy) in offsets.items():
            if side == "L":
                dx = -dx
            at(side + "_eyelid" + part + "_CTL", ex + dx, ey + dy, width=10, layer="Secondary")
        for band, sign in (("upper", -1), ("down", 1)):
            for i in range(21):
                theta = math.pi * i / 20
                # These exact spellings, including 010, come from the curve export.
                name = side + "_" + band + "Eyelid0" + str(i) + "_CTL"
                at(name, ex - rx * math.cos(theta), ey + sign * ry * math.sin(theta),
                   width=4, color=TEAL if side == "L" else "#ed96a0", layer="Fine eyelids")
        socket_offsets = {"upperSocket": (0, -ry-4), "lowerSocket": (0, ry+4), "inSocket": (rx+3.5, 0),
                          "outSocket": (-rx-3.5, 0), "upInSocket": (rx+.5, -ry-3), "upOutSocket": (-rx-.5, -ry-3),
                          "downInSocket": (rx+.5, ry+3), "downOutSocket": (-rx-.5, ry+3)}
        for part, (dx, dy) in socket_offsets.items():
            if side == "L":
                dx = -dx
            at(side + "_" + part + "_CTL", ex + dx, ey + dy, width=8, layer="Secondary")
        earx, eary = (78, 101) if side == "R" else (141, 101)
        for i in range(3):
            at(side + "_ear0" + str(i) + "_CTL", earx, eary + 5 * i, width=20, height=14, kind="triangle", color=GOLD)
        cheekx = 94 if side == "R" else 125
        at(side + "_cheek_CTL", cheekx, 124, width=29, height=16, kind="pill")
        at(side + "_cheekbone_CTL", cheekx, 110, width=34, height=13, kind="pill")
        for i in range(3):
            at(side + "_cheekbone0" + str(i) + "_CTL", cheekx + (i - 1) * 3, 117, width=9, layer="Secondary")
        at(side + "_nose_CTL", 103 if side == "R" else 116, 111, width=14)
        at(side + "_nosetril_CTL", 104 if side == "R" else 115, 116, width=10, layer="Secondary")
        at(side + "_lipCorner_CTL", 100 if side == "R" else 118, 127, width=21, kind="diamond")
        for band, y in (("upper", 125), ("lower", 130)):
            for i in range(4):
                x = (102 + i * 1.6) if side == "R" else (116 - i * 1.6)
                at(side + "_" + band + "Lip0" + str(i) + "_CTL", x, y,
                   width=7, layer="Secondary")
    at("C_baseNose_CTL", 109, 103, width=38, height=11, kind="pill")
    at("C_noseMain_CTL", 109, 110, width=25, height=18, kind="diamond")
    at("C_noseTip_CTL", 109, 114, width=15, color=GREEN)
    at("C_upperJaw_CTL", 109, 120, width=64, height=8, kind="pill")
    at("C_mainMouth_CTL", 109, 127, width=70, height=7, kind="pill")
    at("C_upperLip_CTL", 109, 122, width=46, height=8, kind="pill")
    at("C_lowerLip_CTL", 109, 133, width=46, height=8, kind="pill")
    at("C_upperLip00_CTL", 109, 125, width=8, color=GREEN, layer="Secondary")
    at("C_lowerLip00_CTL", 109, 130, width=8, color=GREEN, layer="Secondary")
    at("C_jaw_CTL", 109, 144, width=79, height=27, kind="trapezoid", label="Jaw")


def polygon(c):
    w, h = c["w"], c["h"]
    points = {"diamond": [(-w/2, 0), (0, -h/2), (w/2, 0), (0, h/2)],
              "triangle": [(-w/2, h/2), (0, -h/2), (w/2, h/2)],
              "hex": [(-w/2, 0), (-w/4, -h/2), (w/4, -h/2), (w/2, 0), (w/4, h/2), (-w/4, h/2)],
              "trapezoid": [(-w/2, -h/2), (w/2, -h/2), (w/3, h/2), (-w/3, h/2)]}[c["kind"]]
    a = math.radians(c["angle"])
    return [(x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)) for x, y in points]


def vector(c, x=None, y=None):
    x = c["x"] if x is None else x
    y = c["y"] if y is None else y
    name = html.escape(c["name"])
    fill = c["color"]
    if c["kind"] in ("pill", "round"):
        if c["kind"] == "round":
            primitive = '<ellipse cx="0" cy="0" rx="%s" ry="%s"/>' % (c["w"]/2, c["h"]/2)
        else:
            primitive = '<rect x="%s" y="%s" width="%s" height="%s" rx="%s" transform="rotate(%s)"/>' % (-c["w"]/2, -c["h"]/2, c["w"], c["h"], c["h"]/2, c["angle"])
    else:
        primitive = '<polygon points="%s"/>' % ' '.join('%g,%g' % p for p in polygon(c))
    label = ''
    if c["label"]:
        label = '<text x="0" y="3.5" text-anchor="middle" fill="#141414" stroke="none" font-family="Arial" font-size="10">%s</text>' % html.escape(c["label"])
    return '<g id="%s" transform="translate(%g %g)" fill="%s" stroke="#101015" stroke-width="1.6"><title>%s</title>%s%s</g>' % (name, x, y, fill, name, primitive, label)


def svg(content, width=W, height=H):
    return '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="%s" height="%s" viewBox="0 0 %s %s">%s</svg>' % (width, height, width, height, content)


def photo_background(panel):
    backing = ""
    photo, image_width, image_height = PHOTO, 1920, 830
    if panel == 0:
        transform = "translate(-815 95)"
        # The supplied sheet's adjacent scissor hands reach into the crop.
        # Narrow the upper photo viewport, while keeping the frontal blades.
        clip = '<path d="M 110 115 H 625 V 550 H 660 V 897 Q 660 915 642 915 H 78 Q 60 915 60 897 V 550 H 110 Z"/>'
        backing = ('<defs><linearGradient id="sheet-gray" x1="0" y1="115" x2="0" y2="550" gradientUnits="userSpaceOnUse">'
                   '<stop offset="0" stop-color="#767676"/><stop offset=".42" stop-color="#787878"/>'
                   '<stop offset=".76" stop-color="#7d7d7d"/><stop offset="1" stop-color="#828282"/>'
                   '</linearGradient></defs><rect x="60" y="115" width="600" height="800" rx="18" fill="url(#sheet-gray)"/>')
    else:
        photo, image_width, image_height = FACE_PHOTO, 224, 185
        transform, clip = "translate(-55 95) scale(4)", '<rect x="85" y="115" width="585" height="715" rx="18"/>'
    return '<rect width="750" height="1000" fill="#070909"/>%s<defs><clipPath id="photo-clip-%s">%s</clipPath></defs><g clip-path="url(#photo-clip-%s)"><image xlink:href="%s" width="%s" height="%s" transform="%s"/></g>' % (backing, panel, clip, panel, photo, image_width, image_height, transform)


def decoration(panel):
    title = "BODY" if panel == 0 else "FACE"
    return ('<rect x="1" y="1" width="748" height="998" rx="7" fill="none" stroke="#44484a" stroke-width="2"/>'
            '<text x="25" y="36" fill="#dfdfdf" font-family="Arial" font-size="22">EDWARD</text>'
            '<text x="25" y="59" fill="#8c9695" font-family="Arial" font-size="11">' + title + '</text>'
            '<circle cx="585" cy="34" r="5" fill="#b43d4e"/><text x="598" y="38" fill="#aaa" font-family="Arial" font-size="10">R</text>'
            '<circle cx="625" cy="34" r="5" fill="#ddca32"/><text x="638" y="38" fill="#aaa" font-family="Arial" font-size="10">C</text>'
            '<circle cx="665" cy="34" r="5" fill="#43469b"/><text x="678" y="38" fill="#aaa" font-family="Arial" font-size="10">L</text>'
            '<rect x="25" y="75" width="155" height="27" rx="4" fill="#424748" stroke="#111"/>'
            '<text x="102.5" y="93" text-anchor="middle" fill="#fff" font-family="Arial" font-size="11">Select ' + title.title() + '</text>'
            '<rect x="195" y="75" width="125" height="27" rx="4" fill="#424748" stroke="#111"/>'
            '<text x="257.5" y="93" text-anchor="middle" fill="#fff" font-family="Arial" font-size="11">Select All</text>')


def dwshape(c):
    s = copy.deepcopy(TEMPLATE)
    s.update({"id": str(uuid.uuid5(uuid.NAMESPACE_URL, "edward-photo:" + str(c["panel"]) + c["name"])),
              "panel": c["panel"], "visibility_layer": c["layer"], "shape.left": c["x"]-c["w"]/2,
              "shape.top": c["y"]-c["h"]/2, "shape.width": c["w"], "shape.height": c["h"],
              "shape": "round" if c["kind"] == "round" else "rounded_rect", "shape.path": [],
              "shape.cornersx": c["h"]/2, "shape.cornersy": c["h"]/2,
              "text.content": c["label"], "text.color": "#141414", "text.size": 10,
              "action.targets": [c["name"]], "action.commands": [], "image.path": "",
              "borderwidth.normal": 1.6, "bordercolor.normal": "#101015",
              "bgcolor.normal": c["color"], "bgcolor.hovered": c["color"], "bgcolor.clicked": "#ffffff"})
    if c["kind"] not in ("round", "pill") or c["angle"]:
        # A custom cubic path preserves rotation and rounded capsule geometry.
        if c["kind"] == "pill":
            w, h = c["w"], c["h"]
            r, k = h/2, .55228475
            anchors = [(-w/2+r,-r),(w/2-r,-r),(w/2,0),(w/2-r,r),(-w/2+r,r),(-w/2,0)]
            incoming = [(-w/2+r-k*r,-r),None,(w/2,-k*r),(w/2-r+k*r,r),None,(-w/2,k*r)]
            outgoing = [None,(w/2-r+k*r,-r),(w/2,k*r),None,(-w/2+r-k*r,r),(-w/2,-k*r)]
            def rotate(p):
                if p is None:
                    return None
                a = math.radians(c["angle"])
                return [p[0]*math.cos(a)-p[1]*math.sin(a)+w/2, p[0]*math.sin(a)+p[1]*math.cos(a)+h/2]
            path = [{"point":rotate(p), "tangent_in":rotate(i), "tangent_out":rotate(o)} for p,i,o in zip(anchors,incoming,outgoing)]
        else:
            path = [{"point": [x+c["w"]/2,y+c["h"]/2], "tangent_in":None,"tangent_out":None} for x,y in polygon(c)]
        # Bounds include rotated corners; paths remain relative to their origin.
        xs, ys = [p["point"][0] for p in path], [p["point"][1] for p in path]
        minx, miny = min(xs), min(ys)
        for p in path:
            for key in ("point","tangent_in","tangent_out"):
                if p[key] is not None:
                    p[key] = [p[key][0]-minx,p[key][1]-miny]
        s.update({"shape":"custom", "shape.path":path, "shape.left":s["shape.left"]+minx,
                  "shape.top":s["shape.top"]+miny, "shape.width":max(xs)-minx, "shape.height":max(ys)-miny})
    return s


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    for folder in ("controls/body", "controls/face", "backgrounds"):
        (OUT/folder).mkdir(parents=True, exist_ok=True)
    body()
    face()
    used = {c["name"] for c in CONTROLS}
    if NAMES - used:
        raise ValueError("Unplaced controllers: " + ', '.join(sorted(NAMES-used)))
    if len(used) != len(CONTROLS):
        raise ValueError("Controller asset names must be unique")
    manifest = []
    for c in CONTROLS:
        panel_name = "body" if c["panel"] == 0 else "face"
        relative = "controls/%s/%s.svg" % (panel_name,c["name"])
        edge = int(math.ceil(max(c["w"],c["h"])+12))
        (OUT/relative).write_text(svg(vector(c,edge/2,edge/2),edge,edge),encoding="utf-8")
        manifest.append(dict(c,svg=relative,png=relative.replace('.svg','.png')))
    (OUT/"controls_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    shapes, combined = [], []
    for panel,panel_name in enumerate(("body","face")):
        bg = photo_background(panel)+decoration(panel)
        (OUT/"backgrounds"/(panel_name+".svg")).write_text(svg(bg),encoding="utf-8")
        visible = ''.join(vector(c) for c in CONTROLS if c["panel"]==panel and c["layer"] not in ("Fine eyelids",))
        overlay = ''.join(vector(c) for c in CONTROLS if c["panel"]==panel)
        (OUT/("02_"+panel_name+"_controls.svg")).write_text(svg(overlay),encoding="utf-8")
        (OUT/("03_edward_"+panel_name+".svg")).write_text(svg(bg+visible),encoding="utf-8")
        combined.append('<g transform="translate(%s 0)">%s%s</g>' % (panel*(W+16),bg,visible))
        s = copy.deepcopy(TEMPLATE)
        s.update({"id":str(uuid.uuid5(uuid.NAMESPACE_URL,"edward-photo:bg:"+panel_name)),"panel":panel,"background":True,
                  "shape.ignored_by_focus":True,"shape":"square","shape.left":0.0,"shape.top":0.0,
                  "shape.width":W,"shape.height":H,"shape.path":[],"border":False,
                  "bgcolor.normal":"#070909","text.content":"","action.targets":[],"action.commands":[],
                  "image.path":(OUT/"backgrounds"/(panel_name+".png")).as_posix(),"image.width":W,"image.height":H,
                  "image.fit":True,"image.ratio":False,"visibility_layer":None})
        shapes.append(s)
        for caption,targets,x,width in (("Select "+panel_name.title(),[c["name"] for c in CONTROLS if c["panel"]==panel],25,155),
                                        ("Select All",sorted(NAMES),195,125)):
            button = copy.deepcopy(TEMPLATE)
            button.update({"id":str(uuid.uuid5(uuid.NAMESPACE_URL,"edward-photo:selector:"+str(panel)+caption)),
                           "panel":panel,"shape.left":x,"shape.top":75,"shape.width":width,"shape.height":27,
                           "text.content":caption,"text.size":11,"action.targets":targets,"action.commands":[],
                           "bgcolor.normal":"#424748","bgcolor.hovered":"#606667","visibility_layer":None,"image.path":""})
            shapes.append(button)
        shapes.extend(dwshape(c) for c in CONTROLS if c["panel"]==panel)
    combined_svg = svg('<rect width="1516" height="1000" fill="#070909"/>'+''.join(combined),1516,1000)
    (OUT/"03_edward_picker.svg").write_text(combined_svg,encoding="utf-8")
    doc = {"general":{"name":"Edward - Photo Reference","version":[1,0,4],"panels.as_sub_tab":False,
                       "panels.orientation":"vertical","panels.zoom_locked":[False,False],"panels.colors":["#070909","#070909"],
                       "panels.names":["Body","Face"],"menu_commands":[],"hidden_layers":["Fine eyelids"],
                       "panels":[[1.0,[1.0]],[1.0,[1.0]]]},"shapes":shapes}
    (OUT/"Edward_reference_picker.json").write_text(json.dumps(doc,indent=2),encoding="utf-8")
    # An inspection sheet contains every isolated asset, including fine controls.
    cells=[]
    for i,c in enumerate(CONTROLS):
        x,y=(i%8)*190,(i//8)*85
        scale = min(1, 166/c["w"], 46/c["h"])
        icon = '<g transform="translate(95 34) scale(%g)">%s</g>' % (scale,vector(c,0,0))
        cells.append('<g transform="translate(%s %s)"><rect x="3" y="3" width="184" height="79" rx="5" fill="#15191b"/>%s<text x="95" y="72" fill="#ccc" text-anchor="middle" font-family="Arial" font-size="7.3">%s</text></g>' % (x,y,icon,html.escape(c["name"])))
    (OUT/"02_controls_catalog.svg").write_text(svg(''.join(cells),1520,math.ceil(len(CONTROLS)/8)*85),encoding="utf-8")
    print(json.dumps({"controls":len(CONTROLS),"body":sum(c["panel"]==0 for c in CONTROLS),
                      "face":sum(c["panel"]==1 for c in CONTROLS),"missing":sorted(NAMES-used),"output":str(OUT)}))


if __name__ == "__main__":
    build()
