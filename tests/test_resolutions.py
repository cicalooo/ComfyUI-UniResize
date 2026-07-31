import importlib.util
import pathlib
import sys
import unittest


PACKAGE_ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "comfyui_uniresize_tests",
    PACKAGE_ROOT / "__init__.py",
    submodule_search_locations=[str(PACKAGE_ROOT)],
)
PACKAGE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PACKAGE
SPEC.loader.exec_module(PACKAGE)

from comfyui_uniresize_tests.resolutions import CATALOG, PROFILES, resolve_dimensions, resolve_selection, selection_ids


class ResolutionCatalogTests(unittest.TestCase):
    def test_every_selection_resolves_and_is_aligned(self):
        for selection in selection_ids()[1:]:
            with self.subTest(selection=selection):
                profile_id, _ = selection.split(":", 1)
                width, height = resolve_selection(selection)
                multiple = PROFILES[profile_id]["multiple"]
                self.assertGreater(width, 0)
                self.assertGreater(height, 0)
                self.assertEqual(width % multiple, 0)
                self.assertEqual(height % multiple, 0)

    def test_exact_presets_remain_exact(self):
        self.assertEqual(resolve_selection("sdxl:16-9"), (1344, 768))
        self.assertEqual(resolve_selection("wan_480:16-9"), (832, 480))
        self.assertEqual(resolve_selection("wan_720:16-9"), (1280, 720))

    def test_portrait_translation_is_symmetric(self):
        landscape = resolve_selection("wan_720:4-3")
        portrait = resolve_selection("wan_720:3-4")
        self.assertEqual(landscape, portrait[::-1])

    def test_invalid_selection_has_clear_error(self):
        with self.assertRaisesRegex(ValueError, "Unknown UniRatio selection"):
            resolve_selection("not-a-profile:1-1")

    def test_catalog_keys_are_unique(self):
        profile_ids = [profile["id"] for profile in CATALOG["profiles"]]
        ratio_ids = [ratio["id"] for ratio in CATALOG["ratios"]]
        self.assertEqual(len(profile_ids), len(set(profile_ids)))
        self.assertEqual(len(ratio_ids), len(set(ratio_ids)))

    def test_upscale_preserves_profile_alignment(self):
        width, height = resolve_dimensions("wan_480:16-9", 1.5)
        self.assertEqual((width, height), (1248, 720))
        self.assertEqual(width % 16, 0)
        self.assertEqual(height % 16, 0)

    def test_manual_dimensions_and_upscale(self):
        self.assertEqual(resolve_dimensions("manual", 1.0, 1234, 777), (1234, 777))
        self.assertEqual(resolve_dimensions("manual", 0.5, 1234, 778), (617, 389))


if __name__ == "__main__":
    unittest.main()
