"""Aspect ratio + one ResizeType rule -> grid-aligned width/height."""

from __future__ import annotations

import math

try:
    from nodes import MAX_RESOLUTION
except ImportError:
    MAX_RESOLUTION = 16384

ASPECT_RATIOS = {
    "1:1": (1, 1),
    "5:4": (5, 4),
    "4:5": (4, 5),
    "4:3": (4, 3),
    "3:4": (3, 4),
    "3:2": (3, 2),
    "2:3": (2, 3),
    "16:10": (16, 10),
    "10:16": (10, 16),
    "16:9": (16, 9),
    "9:16": (9, 16),
    "2:1": (2, 1),
    "1:2": (1, 2),
    "21:9": (21, 9),
    "9:21": (9, 21),
    "32:9": (32, 9),
    "9:32": (9, 32),
    "3:1": (3, 1),
    "1:3": (1, 3),
}

RATIO_NAMES = list(ASPECT_RATIOS)
MULTIPLES = ["disabled", "8", "16", "32", "64"]

# Modes that determine both edges themselves; aspect_ratio plays no part.
EXPLICIT_MODES = {"scale dimensions", "match size", "scale by multiplier"}


def ratio_of(ratio_name: str) -> float:
    try:
        ratio_w, ratio_h = ASPECT_RATIOS[ratio_name]
    except KeyError:
        raise ValueError(
            f"Unknown aspect ratio {ratio_name!r}; expected one of "
            f"{', '.join(RATIO_NAMES)}."
        ) from None
    return ratio_w / ratio_h


def _snap(value: float, multiple: int) -> int:
    if multiple <= 1:
        return max(1, int(round(value)))
    return max(multiple, int(round(value / multiple)) * multiple)


def _best_area_fit(ratio: float, area: float, multiple: int) -> tuple[int, int]:
    """Independent rounding of each edge skews cinematic ratios; score the neighbourhood."""
    base_width = _snap(math.sqrt(area * ratio), multiple)
    base_height = _snap(math.sqrt(area / ratio), multiple)
    step = max(1, multiple)
    best = None
    for width_step in range(-2, 3):
        for height_step in range(-2, 3):
            width = base_width + width_step * step
            height = base_height + height_step * step
            if width < step or height < step:
                continue
            if width > MAX_RESOLUTION or height > MAX_RESOLUTION:
                continue
            error = (abs(width * height - area) / area
                     + abs(width / height - ratio) / ratio)
            if best is None or error < best[0]:
                best = (error, width, height)
    if best is None:
        raise ValueError(
            f"No valid size for area {area:.0f} on a {multiple}px grid within "
            f"MAX_RESOLUTION ({MAX_RESOLUTION})."
        )
    return best[1], best[2]


def _validate(width: int, height: int) -> tuple[int, int]:
    if width < 1 or height < 1:
        raise ValueError("Resolved dimensions must be positive.")
    if width > MAX_RESOLUTION or height > MAX_RESOLUTION:
        raise ValueError(
            f"Resolved dimensions {width}x{height} exceed ComfyUI "
            f"MAX_RESOLUTION ({MAX_RESOLUTION})."
        )
    return width, height


def solve(
    mode: str,
    ratio_name: str,
    multiple: int,
    *,
    megapixels: float = 1.0,
    longer_size: int = 1024,
    shorter_size: int = 768,
    width: int = 1024,
    height: int = 1024,
    multiplier: float = 1.0,
    reference: tuple[int, int] | None = None,
) -> tuple[int, int]:
    """Pinned edges stay snapped; only ``scale total pixels`` trades both edges."""
    if mode in EXPLICIT_MODES:
        if mode == "scale dimensions":
            target_w, target_h = float(width), float(height)
        else:
            if reference is None:
                raise ValueError(
                    f"'{mode}' needs a reference image or mask connected to "
                    "the 'match' input."
                )
            target_w, target_h = float(reference[0]), float(reference[1])
            if mode == "scale by multiplier":
                if multiplier <= 0.0:
                    raise ValueError("multiplier must be positive.")
                target_w *= multiplier
                target_h *= multiplier
        return _validate(_snap(target_w, multiple), _snap(target_h, multiple))

    ratio = ratio_of(ratio_name)

    if mode == "scale total pixels":
        if megapixels <= 0.0:
            raise ValueError("megapixels must be positive.")
        return _validate(*_best_area_fit(ratio, megapixels * 1_000_000, multiple))

    if mode == "scale longer dimension":
        if longer_size < 1:
            raise ValueError("longer_size must be positive.")
        pinned = _snap(longer_size, multiple)
        other = _snap(pinned / ratio if ratio >= 1.0 else pinned * ratio, multiple)
        return _validate(*((pinned, other) if ratio >= 1.0 else (other, pinned)))

    if mode == "scale shorter dimension":
        if shorter_size < 1:
            raise ValueError("shorter_size must be positive.")
        pinned = _snap(shorter_size, multiple)
        other = _snap(pinned * ratio if ratio >= 1.0 else pinned / ratio, multiple)
        return _validate(*((other, pinned) if ratio >= 1.0 else (pinned, other)))

    if mode == "scale width":
        if width < 1:
            raise ValueError("width must be positive.")
        pinned = _snap(width, multiple)
        return _validate(pinned, _snap(pinned / ratio, multiple))

    if mode == "scale height":
        if height < 1:
            raise ValueError("height must be positive.")
        pinned = _snap(height, multiple)
        return _validate(_snap(pinned * ratio, multiple), pinned)

    raise ValueError(f"Unsupported sizing mode: {mode!r}")


def dimensions_for(ratio_name: str, megapixels: float, multiple: int) -> tuple[int, int]:
    """Back-compatible shorthand for the ``scale total pixels`` rule."""
    return solve("scale total pixels", ratio_name, multiple, megapixels=megapixels)
