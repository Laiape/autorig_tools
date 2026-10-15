"""Character picker entry point for explicit generation, menu and shelf."""
import json
from pathlib import Path

import maya.cmds as cmds
from tools import character_picker_builder as builder
from tools.install_character_picker import open_bundle


def scene_character():
    assets = {p.name.lower(): p.name for p in builder.ASSETS.iterdir() if p.is_dir()}
    selection = cmds.ls(selection=True, long=True) or []
    for node in selection:
        for part in node.split("|"):
            name = part.rsplit(":", 1)[-1].lower()
            if name in assets:
                return assets[name]
    characters = set()
    for node in cmds.ls("C_character_CTL", "*:C_character_CTL", long=True) or []:
        characters.update(assets[p.rsplit(":", 1)[-1].lower()] for p in node.split("|")
                          if p.rsplit(":", 1)[-1].lower() in assets)
    if len(characters) == 1:
        return characters.pop()
    raise ValueError("Select a controller belonging to the character to open its picker.")


def generate(character=None, load=True):
    from utils import guides_manager
    character = character or scene_character()
    guides_manager.clear_guides_cache()
    guides = guides_manager.read_guides_info(character)
    if not guides:
        raise ValueError("Picker requires exported guides for " + character)
    controls = []
    for node in cmds.ls("*_CTL", "*:*_CTL", type="transform", long=True) or []:
        if any(p.rsplit(":", 1)[-1].lower() == character.lower() for p in node.split("|")):
            controls.append(node.rsplit("|", 1)[-1].rsplit(":", 1)[-1])
    if not controls:
        raise ValueError("No live rig controls found for " + character)
    directory = builder.build(character, guides=guides, control_names=controls)
    builder.package(directory)
    if load:
        from tools import character_picker_scene
        roots = character_picker_scene.matching_roots(character)
        for root in roots:
            character_picker_scene.attach(directory, root)
        if not roots:
            raise ValueError("No character rig root for embedding the picker: " + character)
    return str(directory/"picker.json")


def show(character=None, root_uuid=None):
    character = character or scene_character()
    directory = builder.character_asset(character)/"picker/generated"
    if not (directory/"picker.json").is_file():
        generate(character, load=False)
    return open_bundle(directory, root_uuid=root_uuid)
