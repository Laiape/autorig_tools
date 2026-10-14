"""Pure planning tests. These do not certify Maya or real rig selection."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from maya_tools.scripts.tools import character_picker_builder as builder
from maya_tools.scripts.utils import module_guides


class GuidePickerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asset = builder.character_asset("thaiz")
        cls.guides = json.loads(builder.latest(asset/"guides", "guides").read_text())["thaiz"]
        cls.names = [v["transform"]["name"] for v in json.loads(builder.latest(asset/"curves", "curves").read_text()).values()]

    def plan(self, guides=None, **kwargs):
        return builder.plan("thaiz", self.guides if guides is None else guides, self.names, **kwargs)

    def test_thaiz_complete_exports(self):
        document, config, report = self.plan()
        self.assertEqual((report["body"], report["face"], report["skipped"]), (127, 158, []))
        self.assertTrue(config["module_measurements"])
        self.assertEqual(len({c["name"] for c in report["controls"]}), 285)
        controls = [s for s in document["shapes"] if len(s["action.targets"]) == 1]
        for i, a in enumerate(controls):
            for b in controls[i+1:]:
                if a["panel"] == b["panel"]:
                    overlap = (a["shape.left"] < b["shape.left"]+b["shape.width"] and
                               a["shape.left"]+a["shape.width"] > b["shape.left"] and
                               a["shape.top"] < b["shape.top"]+b["shape.height"] and
                               a["shape.top"]+a["shape.height"] > b["shape.top"])
                    self.assertFalse(overlap, (a["action.targets"], b["action.targets"]))

    def test_no_guides_no_picker(self):
        with self.assertRaisesRegex(ValueError, "requires exported guides"):
            self.plan({})

    def test_partial_pair_disables_module(self):
        guides = copy.deepcopy(self.guides)
        del guides["R_shoulder_JNT"]
        _, config, report = self.plan(guides)
        self.assertFalse(config["enabled_modules"]["arm"])
        self.assertFalse(any(c["module"] == "arm" for c in report["controls"]))
        self.assertTrue(any(c["module"] == "arm" for c in report["skipped"]))

    def test_missing_digit_skips_stale_controls(self):
        guides = copy.deepcopy(self.guides)
        del guides["L_index00_JNT"]
        _, _, report = self.plan(guides)
        self.assertFalse(any(c["name"].startswith("L_index") for c in report["controls"]))

    def test_curve_eyebrow_alternative(self):
        guides = {"L_eyebrow_CRVShape": {}, "R_eyebrow_CRVShape": {}}
        self.assertTrue(module_guides.enabled(guides, "eyebrow"))
        del guides["R_eyebrow_CRVShape"]
        self.assertFalse(module_guides.enabled(guides, "eyebrow"))

    def test_dimensions_and_profile(self):
        _, config, report = self.plan(overrides={"panels": {"body": {"size": [900, 1200]}},
                                                 "controls": {"C_head_CTL": {"size": [90, 20]}}})
        self.assertEqual(config["panels"][0]["size"], [900, 1200])
        self.assertEqual(next(c["size"] for c in report["controls"] if c["name"] == "C_head_CTL"), [90, 20])
        with self.assertRaises(ValueError):
            self.plan(overrides={"controls": {"C_head_CTL": {"size": [-1, 20]}}})

    def test_no_facial_guides_no_facial_buttons(self):
        guides = {n: v for n, v in self.guides.items() if not any(n in alternative
                  for module in builder.FACE_MODULES for alternative in module_guides.REQUIREMENTS[module])}
        _, config, report = self.plan(guides)
        self.assertEqual(report["face"], 0)
        self.assertFalse(config["enabled_modules"]["face"])

    def test_version_is_numeric(self):
        with tempfile.TemporaryDirectory() as temporary:
            for filename in ("test_v009.guides", "test_v010.guides", "test_v002.guides"):
                (Path(temporary)/filename).touch()
            self.assertEqual(builder.latest(temporary, "guides").name, "test_v010.guides")


if __name__ == "__main__":
    unittest.main()
