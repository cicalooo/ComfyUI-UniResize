import importlib.util
import pathlib
import sys
import unittest


PACKAGE_ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "comfyui_uniresize_resolutions",
    PACKAGE_ROOT / "resolutions.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

from comfyui_uniresize_resolutions import (  # noqa: E402
    ASPECT_RATIOS,
    EXPLICIT_MODES,
    MULTIPLES,
    RATIO_NAMES,
    dimensions_for,
    ratio_of,
    solve,
)

GRIDS = [int(m) for m in MULTIPLES if m != "disabled"]
RATIO_DRIVEN = [
    ("scale total pixels", {"megapixels": 1.0}),
    ("scale longer dimension", {"longer_size": 1024}),
    ("scale shorter dimension", {"shorter_size": 768}),
    ("scale width", {"width": 1024}),
    ("scale height", {"height": 1024}),
]


class GridTests(unittest.TestCase):
    def test_every_mode_ratio_and_grid_lands_on_the_grid(self):
        for mode, kwargs in RATIO_DRIVEN:
            for ratio in RATIO_NAMES:
                for grid in GRIDS:
                    with self.subTest(mode=mode, ratio=ratio, grid=grid):
                        width, height = solve(mode, ratio, grid, **kwargs)
                        self.assertGreater(width, 0)
                        self.assertGreater(height, 0)
                        self.assertEqual(width % grid, 0)
                        self.assertEqual(height % grid, 0)

    def test_grid_disabled_returns_exact_pixels(self):
        self.assertEqual(
            solve("scale dimensions", "16:9", 1, width=1281, height=723),
            (1281, 723),
        )


class PinnedEdgeTests(unittest.TestCase):
    """The number you type is the number you get, once snapped."""

    def test_longer_dimension_is_honoured_in_both_orientations(self):
        self.assertEqual(solve("scale longer dimension", "16:9", 32, longer_size=1280)[0], 1280)
        self.assertEqual(solve("scale longer dimension", "9:16", 32, longer_size=1280)[1], 1280)

    def test_shorter_dimension_is_honoured_in_both_orientations(self):
        self.assertEqual(solve("scale shorter dimension", "16:9", 32, shorter_size=768)[1], 768)
        self.assertEqual(solve("scale shorter dimension", "9:16", 32, shorter_size=768)[0], 768)

    def test_axis_modes_pin_their_axis(self):
        self.assertEqual(solve("scale width", "16:9", 32, width=1344)[0], 1344)
        self.assertEqual(solve("scale height", "16:9", 32, height=768)[1], 768)

    def test_derived_edge_follows_the_ratio(self):
        for ratio in RATIO_NAMES:
            width, height = solve("scale width", ratio, 8, width=1024)
            with self.subTest(ratio=ratio):
                self.assertLess(abs((width / height) - ratio_of(ratio)) / ratio_of(ratio), 0.05)

    def test_h3_canonical_canvas(self):
        self.assertEqual(solve("scale width", "16:9", 32, width=1344), (1344, 768))


class ExplicitModeTests(unittest.TestCase):
    def test_scale_dimensions_ignores_the_ratio(self):
        for ratio in RATIO_NAMES:
            with self.subTest(ratio=ratio):
                self.assertEqual(
                    solve("scale dimensions", ratio, 32, width=1344, height=768),
                    (1344, 768),
                )

    def test_match_size_takes_the_reference(self):
        self.assertEqual(
            solve("match size", "1:1", 32, reference=(900, 512)), (896, 512))

    def test_multiplier_scales_the_reference(self):
        self.assertEqual(
            solve("scale by multiplier", "1:1", 32, reference=(900, 512), multiplier=2.0),
            (1792, 1024),
        )

    def test_reference_modes_require_a_reference(self):
        for mode in sorted(EXPLICIT_MODES - {"scale dimensions"}):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                solve(mode, "1:1", 32)


class AreaTests(unittest.TestCase):
    def test_area_tracks_the_megapixel_budget(self):
        for megapixels in (0.26, 0.5, 1.0, 2.0):
            width, height = solve("scale total pixels", "16:9", 32, megapixels=megapixels)
            with self.subTest(megapixels=megapixels):
                error = abs(width * height - megapixels * 1e6) / (megapixels * 1e6)
                self.assertLess(error, 0.05)

    def test_aspect_error_stays_small(self):
        for ratio in RATIO_NAMES:
            target = ratio_of(ratio)
            width, height = solve("scale total pixels", ratio, 32, megapixels=1.0)
            with self.subTest(ratio=ratio):
                self.assertLess(abs((width / height) - target) / target, 0.06)

    def test_square_is_square(self):
        width, height = solve("scale total pixels", "1:1", 32, megapixels=1.0)
        self.assertEqual(width, height)

    def test_portrait_is_the_transpose_of_landscape(self):
        for landscape, portrait in (
            ("16:9", "9:16"),
            ("4:3", "3:4"),
            ("3:2", "2:3"),
            ("5:4", "4:5"),
            ("16:10", "10:16"),
            ("2:1", "1:2"),
            ("21:9", "9:21"),
            ("3:1", "1:3"),
        ):
            with self.subTest(pair=(landscape, portrait)):
                self.assertEqual(
                    solve("scale total pixels", landscape, 32, megapixels=1.0),
                    tuple(reversed(solve("scale total pixels", portrait, 32, megapixels=1.0))),
                )

    def test_known_sizes(self):
        self.assertEqual(dimensions_for("1:1", 1.0, 64), (1024, 1024))
        self.assertEqual(dimensions_for("1:1", 0.26, 64), (512, 512))


class ValidationTests(unittest.TestCase):
    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            solve("scale total pixels", "5:7", 32, megapixels=1.0)
        with self.assertRaises(ValueError):
            solve("scale total pixels", "1:1", 32, megapixels=0.0)
        with self.assertRaises(ValueError):
            solve("scale width", "1:1", 32, width=0)
        with self.assertRaises(ValueError):
            solve("no such mode", "1:1", 32)

    def test_every_ratio_name_is_resolvable(self):
        for ratio in RATIO_NAMES:
            self.assertIn(ratio, ASPECT_RATIOS)
            self.assertGreater(ratio_of(ratio), 0)


if __name__ == "__main__":
    unittest.main()
