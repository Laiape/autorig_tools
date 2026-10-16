"""Validate character identities across the shipped asset dependency tree."""
import ast
import base64
import io
import json
from pathlib import Path
import unittest
import zipfile

from maya_tools.scripts.utils.asset_names import normalize_asset_name


ASSETS = Path(__file__).resolve().parents[3] / "assets"


class AssetDependencyTests(unittest.TestCase):
    def test_name_preserves_authored_spelling(self):
        self.assertEqual(normalize_asset_name("  edward  "), "Edward")
        self.assertEqual(normalize_asset_name("maui"), "Maui")
        self.assertEqual(normalize_asset_name("McKenna"), "McKenna")
        self.assertEqual(normalize_asset_name(None), "")

    def test_character_folders_have_one_canonical_identity(self):
        names = [p.name for p in ASSETS.iterdir() if p.is_dir()]
        self.assertEqual(len(names), len({name.casefold() for name in names}))
        for name in names:
            self.assertEqual(name, normalize_asset_name(name))
        self.assertNotIn("Chihuahua_v001", names)

    def test_guide_keys_match_their_character_folder(self):
        paths = list(ASSETS.glob("*/guides/*.guides")) + list(ASSETS.glob("*/skin_clusters/*.weights"))
        for path in paths:
            with self.subTest(path=str(path)):
                self.assertIn(path.parents[1].name, json.loads(path.read_bytes()))

    def test_curve_dag_roots_match_their_character_folder(self):
        for path in ASSETS.glob("*/curves/*.curves"):
            character = path.parents[1].name
            with self.subTest(path=str(path)):
                curves = json.loads(path.read_bytes())
                roots = {name.split("|")[1] for name in curves if name.startswith("|")}
                self.assertEqual(roots, {character})

    def test_generated_picker_inputs_exist_with_exact_case(self):
        repo = ASSETS.parents[1]
        for path in ASSETS.glob("*/picker/generated/build_report.json"):
            with self.subTest(path=str(path)):
                report = json.loads(path.read_bytes())
                self.assertEqual(report["character"], path.parents[2].name)
                for source in report.get("sources", {}).values():
                    if source == "live scene controls":
                        continue
                    current = repo
                    for part in source.replace("\\", "/").split("/"):
                        self.assertIn(part, [p.name for p in current.iterdir()])
                        current = current / part
                    self.assertTrue(current.is_file())

    def test_portable_installers_embed_the_canonical_character(self):
        for path in ASSETS.glob("*/picker/*_Picker_Installer.py"):
            with self.subTest(path=str(path)):
                tree = ast.parse(path.read_bytes())
                payload = next(ast.literal_eval(node.value) for node in tree.body
                               if isinstance(node, ast.Assign) and any(
                                   isinstance(target, ast.Name) and target.id == "PAYLOAD"
                                   for target in node.targets))
                with zipfile.ZipFile(io.BytesIO(base64.b64decode(payload))) as archive:
                    config = json.loads(archive.read("picker_config.json"))
                    picker = json.loads(archive.read("picker.json"))
                    self.assertEqual(config["character"], path.parents[1].name)
                    self.assertTrue(picker["general"]["name"].startswith(path.parents[1].name))


if __name__ == "__main__":
    unittest.main()
