"""Guide-driven character picker; shared native runtime and portable installer."""
from tools import character_picker


def build_picker_data(char_name):
    import json
    from tools import character_picker_builder
    directory = character_picker_builder.build(char_name)
    return json.loads((directory / "picker.json").read_text(encoding="utf-8"))


def generate_and_load(load=True, character=None):
    return character_picker.generate(character=character, load=load)
